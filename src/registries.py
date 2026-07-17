"""Ferramenta: consulta o registry de pacotes (PyPI) para saber quais versões
existem de verdade, quando saíram e quais restrições cada uma declara.

Isso é o que o LLM não sabe fazer sozinho — o conhecimento dele tem corte no
tempo, aqui o dado vem direto da fonte (ver ARQUITETURA.md, secao 3).
"""
from __future__ import annotations

import re
from datetime import datetime

import httpx
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel

_TIMEOUT = httpx.Timeout(10.0)
_HEADERS = {"User-Agent": "planejador-upgrade/0.1 (mini-projeto IA para DEVs)"}

# nome de pacote nunca vai cru para a URL — valida antes (PEP 508 / normalização PyPI)
_NOME_PACOTE_VALIDO = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


class PacoteNaoEncontrado(Exception):
    def __init__(self, nome: str):
        super().__init__(f"pacote {nome!r} não encontrado no PyPI")
        self.nome = nome


class VersaoPacote(BaseModel):
    versao: str
    lancado_em: datetime | None = None
    requer: list[str] = []  # requires_dist bruto, ex: "urllib3 (<1.27,>=1.21.1)"


class InfoPacote(BaseModel):
    nome: str
    versoes: list[str]  # todas as versões publicadas e não retiradas, em ordem crescente
    ultima: VersaoPacote


def _validar_nome(nome: str) -> str:
    if not _NOME_PACOTE_VALIDO.match(nome):
        raise ValueError(f"nome de pacote inválido, recuso montar URL com isso: {nome!r}")
    return nome


def _get_json(url: str, nome: str) -> dict:
    resp = httpx.get(url, timeout=_TIMEOUT, headers=_HEADERS)
    if resp.status_code == 404:
        raise PacoteNaoEncontrado(nome)
    resp.raise_for_status()
    return resp.json()


def _data_lancamento(arquivos: list[dict]) -> datetime | None:
    datas = []
    for arquivo in arquivos:
        bruto = arquivo.get("upload_time_iso_8601")
        if bruto:
            datas.append(datetime.fromisoformat(bruto.replace("Z", "+00:00")))
    return min(datas) if datas else None


def _versao_disponivel(arquivos: list[dict]) -> bool:
    return bool(arquivos) and not all(a.get("yanked", False) for a in arquivos)


def consultar_pacote(nome: str) -> InfoPacote:
    """Todas as versões publicadas de um pacote, mais os detalhes da última."""
    nome = _validar_nome(nome)
    dados = _get_json(f"https://pypi.org/pypi/{nome}/json", nome)

    versoes_validas = []
    for versao, arquivos in dados["releases"].items():
        if not _versao_disponivel(arquivos):
            continue
        try:
            v = Version(versao)  # descarta versões que não seguem PEP 440
        except InvalidVersion:
            continue
        if v.is_prerelease or v.is_devrelease:
            continue  # alpha/beta/rc/dev nunca deve ser "a maior versão" sugerida
        versoes_validas.append(versao)
    versoes_validas.sort(key=Version)

    info = dados["info"]
    ultima = VersaoPacote(
        versao=info["version"],
        lancado_em=_data_lancamento(dados["releases"].get(info["version"], [])),
        requer=info.get("requires_dist") or [],
    )
    return InfoPacote(nome=nome, versoes=versoes_validas, ultima=ultima)


def consultar_versao(nome: str, versao: str) -> VersaoPacote:
    """Detalhes (restrições declaradas, data) de uma versão específica."""
    nome = _validar_nome(nome)
    dados = _get_json(f"https://pypi.org/pypi/{nome}/{versao}/json", nome)
    info = dados["info"]
    # este endpoint (com versão na URL) traz "urls", não "releases" — diferente
    # do endpoint sem versão usado em consultar_pacote()
    return VersaoPacote(
        versao=info["version"],
        lancado_em=_data_lancamento(dados.get("urls") or []),
        requer=info.get("requires_dist") or [],
    )


# --- npm ---------------------------------------------------------------------
#
# npm ganha consulta de versao/data e CVE (via vulns.py), mas fica de fora do
# agrupamento "sobe junto" do resolver.py: o requires_dist do npm vem como
# "nome@range" (nao PEP 508), e a propria estrutura do node_modules torna
# conflito cruzado raro fora de peerDependencies, que nao esta neste escopo
# (ARQUITETURA.md, secao 4 — assimetria pip x npm, decisao deliberada).

_NOME_PACOTE_NPM_VALIDO = re.compile(r"^(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$")
# fullmatch, nao match: com match(), "1.2.3 - 2.3.4" (range hifenizado) casava
# so o prefixo "1.2.3" e ignorava o resto em silencio — bug real encontrado
# no self-check deste modulo. +build (metadado semver) e opcional e ignorado
# na comparacao, como manda a spec.
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")


def _validar_nome_npm(nome: str) -> str:
    if not _NOME_PACOTE_NPM_VALIDO.match(nome):
        raise ValueError(f"nome de pacote npm inválido, recuso montar URL com isso: {nome!r}")
    return nome


def _semver_tuple(versao: str) -> tuple[int, int, int] | None:
    m = _SEMVER_RE.fullmatch(versao.strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _semver_eh_prerelease(versao: str) -> bool:
    m = _SEMVER_RE.fullmatch(versao.strip())
    return bool(m and m.group(4))


def satisfaz_range_npm(restricao: str, versao: str) -> bool | None:
    """Cobre o subconjunto que aparece na maioria esmagadora dos package.json:
    versão exata, `^`, `~`, e comparadores simples (`>=`, `<=`, `>`, `<`, `=`).

    NÃO cobre `||`, ranges hifenizados ('1.2.3 - 2.3.4') nem `x`/`*` parciais
    em minor/patch. Nesses casos devolve None (não avaliado) em vez de
    arriscar um resultado errado — quem chama trata None como "não deu pra
    saber a partir da faixa declarada".

    # ponytail: subconjunto deliberado, não um motor semver completo.
    # Upgrade path se um dia precisar do resto: node-semver via subprocess
    # do Node (se disponível) ou uma lib Python dedicada — não vale reescrever
    # a gramática inteira à mão para os poucos manifestos que usam o restante.
    """
    restricao = restricao.strip()
    v = _semver_tuple(versao)
    if v is None:
        return None
    if restricao in ("", "*", "latest", "x"):
        return True
    if restricao.startswith("^"):
        base = _semver_tuple(restricao[1:])
        if base is None:
            return None
        if base[0] > 0:
            return v[0] == base[0] and v >= base
        if base[1] > 0:
            return v[0] == 0 and v[1] == base[1] and v >= base
        return v == base
    if restricao.startswith("~"):
        base = _semver_tuple(restricao[1:])
        if base is None:
            return None
        return v[0] == base[0] and v[1] == base[1] and v >= base
    for prefixo, cmp in (
        (">=", lambda a, b: a >= b), ("<=", lambda a, b: a <= b),
        (">", lambda a, b: a > b), ("<", lambda a, b: a < b), ("=", lambda a, b: a == b),
    ):
        if restricao.startswith(prefixo):
            alvo = _semver_tuple(restricao[len(prefixo):])
            return None if alvo is None else cmp(v, alvo)
    alvo = _semver_tuple(restricao)  # versão exata, sem operador
    return None if alvo is None else v == alvo


def _data_lancamento_npm(tempos: dict, versao: str) -> datetime | None:
    bruto = tempos.get(versao) if versao else None
    return datetime.fromisoformat(bruto.replace("Z", "+00:00")) if bruto else None


def consultar_pacote_npm(nome: str) -> InfoPacote:
    """Todas as versões publicadas (estáveis, não descontinuadas) + a 'latest' do npm."""
    nome = _validar_nome_npm(nome)
    dados = _get_json(f"https://registry.npmjs.org/{nome}", nome)

    versoes_validas = []
    for versao, manifesto in dados.get("versions", {}).items():
        if manifesto.get("deprecated"):
            continue
        if _semver_tuple(versao) is None or _semver_eh_prerelease(versao):
            continue
        versoes_validas.append(versao)
    versoes_validas.sort(key=_semver_tuple)

    tempos = dados.get("time", {})
    ultima_tag = dados.get("dist-tags", {}).get("latest") or (versoes_validas[-1] if versoes_validas else "")
    ultima = VersaoPacote(
        versao=ultima_tag,
        lancado_em=_data_lancamento_npm(tempos, ultima_tag),
        requer=[],
    )
    return InfoPacote(nome=nome, versoes=versoes_validas, ultima=ultima)


def consultar_versao_npm(nome: str, versao: str) -> VersaoPacote:
    nome = _validar_nome_npm(nome)
    dados = _get_json(f"https://registry.npmjs.org/{nome}/{versao}", nome)
    return VersaoPacote(versao=dados.get("version", versao), lancado_em=None, requer=[])


def _demo() -> None:
    info = consultar_pacote("requests")
    assert info.nome == "requests"
    assert "2.28.1" in info.versoes, "esperava achar a versão 2.28.1 no histórico"
    assert Version(info.versoes[-1]) >= Version("2.28.1"), "última versão não pode ser mais antiga que a fixada no exemplo"
    assert info.ultima.requer, "última versão do requests declara dependências"

    v = consultar_versao("requests", "2.28.1")
    assert v.versao == "2.28.1"
    assert any("urllib3" in r for r in v.requer), v.requer

    try:
        _validar_nome("requests; DROP TABLE x")
    except ValueError:
        pass
    else:
        raise AssertionError("nome de pacote malicioso deveria ter sido rejeitado")

    # semver npm: subconjunto suportado, sem rede
    assert satisfaz_range_npm("^4.17.1", "4.18.2") is True
    assert satisfaz_range_npm("^4.17.1", "5.0.0") is False
    assert satisfaz_range_npm("~1.19.0", "1.19.5") is True
    assert satisfaz_range_npm("~1.19.0", "1.20.0") is False
    assert satisfaz_range_npm(">=2.0.0", "1.9.9") is False
    assert satisfaz_range_npm("1.2.3 - 2.3.4", "2.0.0") is None, "hifenizado nao e suportado, deve devolver None"

    info_npm = consultar_pacote_npm("express")
    assert info_npm.nome == "express"
    assert "4.18.2" in info_npm.versoes, "esperava achar 4.18.2 no histórico do express"
    assert not info_npm.ultima.requer, "npm nao alimenta requer — decisao de escopo (ver docstring)"

    v_npm = consultar_versao_npm("express", "4.18.2")
    assert v_npm.versao == "4.18.2"

    print(
        f"registries._demo: ok — requests tem {len(info.versoes)} versões (PyPI) | "
        f"express tem {len(info_npm.versoes)} versões (npm)"
    )


if __name__ == "__main__":
    _demo()
