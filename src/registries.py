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

    print(f"registries._demo: ok — requests tem {len(info.versoes)} versões publicadas")


if __name__ == "__main__":
    _demo()
