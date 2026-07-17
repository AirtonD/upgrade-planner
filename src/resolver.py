"""Nucleo deterministico: para cada dependencia do manifesto, calcula a maior
versao disponivel e verifica se outra dependencia do MESMO manifesto trava
essa versao. Quando trava, testa se subir as duas juntas resolve; se nem
assim, marca como bloqueado.

É a parte que um LLM não faz de forma confiável — resolução de versão é
satisfação de restrições, não geração de texto (ver ARQUITETURA.md, secao 3).

Função pura: não faz chamada de rede. Quem busca os dados é `registries.py`;
quem orquestra os dois é o nó `resolver_restricoes` do grafo (`agent.py`).

Escopo assumido (ver ARQUITETURA.md, secao 13 — Limitações):
- compara a versão atual (efetiva) contra a última disponível; não varre o
  espaço de versões intermediárias como um solver SAT completo faria.
- só considera restrições ENTRE dependências que aparecem no próprio manifesto
  — não resolve a árvore transitiva inteira.

Invariante: as chaves de `versoes_atuais` e `infos` precisam estar normalizadas
em minúsculas — a mesma convenção que `parsers.Dependencia.nome` já aplica.
`_parseia_restricoes` normaliza os nomes extraídos de requires_dist para
minúsculas; se as chaves dos dicts de entrada não seguirem a mesma convenção,
o cruzamento falha em silêncio (nenhum conflito é encontrado).
"""
from __future__ import annotations

from typing import Literal

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel

from .registries import InfoPacote, VersaoPacote

TipoSalto = Literal["patch", "minor", "major", "desconhecido"]


class Upgrade(BaseModel):
    nome: str
    de: str
    para: str
    salto: TipoSalto


class GrupoUpgrade(BaseModel):
    upgrades: list[Upgrade]
    motivo: str | None = None  # preenchido quando ha mais de 1 upgrade no grupo


class Bloqueio(BaseModel):
    nome: str
    versao_atual: str
    versao_desejada: str
    motivo: str


class ResultadoResolucao(BaseModel):
    grupos: list[GrupoUpgrade]
    bloqueios: list[Bloqueio]
    sem_mudanca: list[str] = []


def _tipo_salto(de: str, para: str) -> TipoSalto:
    try:
        r_de = Version(de).release
        r_para = Version(para).release
    except InvalidVersion:
        return "desconhecido"
    r_de = (r_de + (0, 0, 0))[:3]
    r_para = (r_para + (0, 0, 0))[:3]
    if r_de[0] != r_para[0]:
        return "major"
    if r_de[1] != r_para[1]:
        return "minor"
    return "patch"


def _parseia_restricoes(requires_dist: list[str]) -> dict[str, SpecifierSet]:
    """requires_dist bruto (PEP 508, ex: 'pydantic<2.0.0,>=1.6.2') -> {nome: SpecifierSet}."""
    restricoes: dict[str, SpecifierSet] = {}
    for bruto in requires_dist:
        nome_e_spec, _, marcador = bruto.partition(";")
        if "extra" in marcador:
            continue  # restrição de um extra opcional, fora do escopo desta versão
        try:
            req = Requirement(nome_e_spec.strip())
        except InvalidRequirement:
            continue
        restricoes[req.name.lower().replace("_", "-")] = req.specifier
    return restricoes


def montar_plano(
    versoes_atuais: dict[str, VersaoPacote],
    infos: dict[str, InfoPacote],
) -> ResultadoResolucao:
    # rede de seguranca: sem isso, uma chave fora do padrao lowercase cruza em
    # silencio com nada e o conflito real simplesmente some (ja aconteceu no
    # fixture de teste deste modulo)
    versoes_atuais = {nome.lower(): v for nome, v in versoes_atuais.items()}
    infos = {nome.lower(): i for nome, i in infos.items()}

    restricoes_atuais = {
        nome: _parseia_restricoes(v.requer) for nome, v in versoes_atuais.items()
    }
    restricoes_na_ultima = {
        nome: _parseia_restricoes(info.ultima.requer) for nome, info in infos.items()
    }

    maior: dict[str, str] = {}
    sem_mudanca: list[str] = []
    elegiveis: set[str] = set()
    for nome, v in versoes_atuais.items():
        info = infos.get(nome)
        if info is None or not info.versoes:
            continue
        topo = info.versoes[-1]
        if topo == v.versao:
            sem_mudanca.append(nome)
            continue
        maior[nome] = topo
        elegiveis.add(nome)

    # aresta nao-direcionada X<->D: a versao atual de X rejeita a maior versao de D
    # (nao-direcionada so para agrupar; a checagem de resolubilidade usa a
    # restricao real, direcionada, de restricoes_atuais)
    conflitos: dict[str, set[str]] = {n: set() for n in elegiveis}
    for x_nome, restricoes in restricoes_atuais.items():
        if x_nome not in elegiveis:
            continue
        for d_nome, spec in restricoes.items():
            if d_nome in elegiveis and not spec.contains(maior[d_nome], prereleases=False):
                conflitos[x_nome].add(d_nome)
                conflitos.setdefault(d_nome, set()).add(x_nome)

    visitados: set[str] = set()
    grupos: list[GrupoUpgrade] = []
    bloqueios: list[Bloqueio] = []

    for nome in sorted(elegiveis):
        if nome in visitados:
            continue

        componente = {nome}
        fila = [nome]
        while fila:
            atual_nome = fila.pop()
            for vizinho in conflitos.get(atual_nome, ()):
                if vizinho not in componente:
                    componente.add(vizinho)
                    fila.append(vizinho)
        visitados |= componente

        if len(componente) == 1:
            grupos.append(GrupoUpgrade(upgrades=[
                Upgrade(
                    nome=nome, de=versoes_atuais[nome].versao, para=maior[nome],
                    salto=_tipo_salto(versoes_atuais[nome].versao, maior[nome]),
                )
            ]))
            continue

        motivos: list[str] = []
        resolvivel = True
        for x_nome in componente:
            for d_nome, spec in restricoes_atuais.get(x_nome, {}).items():
                if d_nome not in componente or d_nome not in elegiveis:
                    continue
                if spec.contains(maior[d_nome], prereleases=False):
                    continue
                motivos.append(f"{x_nome}=={versoes_atuais[x_nome].versao} exige {d_nome}{spec}")
                spec_na_ultima = restricoes_na_ultima.get(x_nome, {}).get(d_nome)
                if spec_na_ultima is not None and not spec_na_ultima.contains(maior[d_nome], prereleases=False):
                    resolvivel = False

        motivo_texto = "; ".join(sorted(set(motivos))) or "conflito entre dependências do manifesto"

        if resolvivel:
            grupos.append(GrupoUpgrade(
                upgrades=[
                    Upgrade(
                        nome=n, de=versoes_atuais[n].versao, para=maior[n],
                        salto=_tipo_salto(versoes_atuais[n].versao, maior[n]),
                    )
                    for n in sorted(componente)
                ],
                motivo=motivo_texto,
            ))
        else:
            for n in sorted(componente):
                bloqueios.append(Bloqueio(
                    nome=n, versao_atual=versoes_atuais[n].versao, versao_desejada=maior[n],
                    motivo=motivo_texto,
                ))

    return ResultadoResolucao(grupos=grupos, bloqueios=bloqueios, sem_mudanca=sem_mudanca)


def _demo() -> None:
    # fixture sintetica (nao e chamada de rede) inspirada no caso real
    # fastapi 0.85.0 / pydantic 1.x -> 2.x, verificado contra a API do PyPI
    # em 2026-07-17 (ver docs/prompts.md)
    versoes_atuais = {
        "fastapi": VersaoPacote(versao="0.85.0", requer=["pydantic<2.0.0,>=1.6.2"]),
        "pydantic": VersaoPacote(versao="1.10.2", requer=[]),
        "requests": VersaoPacote(versao="2.28.1", requer=["urllib3<1.27,>=1.21.1"]),
        "urllib3": VersaoPacote(versao="1.26.12", requer=[]),
    }
    infos = {
        "fastapi": InfoPacote(
            nome="fastapi", versoes=["0.85.0", "0.115.0"],
            ultima=VersaoPacote(versao="0.115.0", requer=["pydantic>=1.7.4,<3.0.0"]),
        ),
        "pydantic": InfoPacote(
            nome="pydantic", versoes=["1.10.2", "2.9.0"],
            ultima=VersaoPacote(versao="2.9.0", requer=[]),
        ),
        "requests": InfoPacote(
            nome="requests", versoes=["2.28.1", "2.32.4"],
            ultima=VersaoPacote(versao="2.32.4", requer=["urllib3<3,>=1.21.1"]),
        ),
        "urllib3": InfoPacote(
            nome="urllib3", versoes=["1.26.12", "2.2.3"],
            ultima=VersaoPacote(versao="2.2.3", requer=[]),
        ),
    }

    resultado = montar_plano(versoes_atuais, infos)

    grupo_fastapi = next(g for g in resultado.grupos if any(u.nome == "fastapi" for u in g.upgrades))
    nomes_no_grupo = {u.nome for u in grupo_fastapi.upgrades}
    assert nomes_no_grupo == {"fastapi", "pydantic"}, nomes_no_grupo
    assert grupo_fastapi.motivo and "pydantic" in grupo_fastapi.motivo

    # requests 2.28.1 trava urllib3<1.27 (nao aceita 2.2.3) — mas a ULTIMA
    # versao do requests (2.32.4) relaxa para <3, entao o grupo se resolve
    grupo_requests = next(g for g in resultado.grupos if any(u.nome == "requests" for u in g.upgrades))
    assert {u.nome for u in grupo_requests.upgrades} == {"requests", "urllib3"}, grupo_requests.upgrades

    assert not resultado.bloqueios, resultado.bloqueios

    # agora um caso genuinamente bloqueado: pacoteA nunca relaxa a restricao
    versoes_atuais2 = {
        "pacote-a": VersaoPacote(versao="1.0.0", requer=["pacote-b<2.0.0"]),
        "pacote-b": VersaoPacote(versao="1.9.0", requer=[]),
    }
    infos2 = {
        "pacote-a": InfoPacote(
            nome="pacote-a", versoes=["1.0.0", "1.1.0"],
            ultima=VersaoPacote(versao="1.1.0", requer=["pacote-b<2.0.0"]),  # nao relaxou
        ),
        "pacote-b": InfoPacote(
            nome="pacote-b", versoes=["1.9.0", "2.5.0"],
            ultima=VersaoPacote(versao="2.5.0", requer=[]),
        ),
    }
    resultado2 = montar_plano(versoes_atuais2, infos2)
    assert not resultado2.grupos, resultado2.grupos
    assert {b.nome for b in resultado2.bloqueios} == {"pacote-a", "pacote-b"}

    print(
        f"resolver._demo: ok — {len(resultado.grupos)} grupo(s), "
        f"{len(resultado.sem_mudanca)} sem mudança | caso bloqueado: "
        f"{len(resultado2.bloqueios)} dependência(s) travada(s)"
    )


if __name__ == "__main__":
    _demo()
