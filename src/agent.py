"""O agente: StateGraph que liga parser, ferramentas de consulta e resolvedor,
com o LLM entrando só para julgar risco (ARQUITETURA.md, secao 6).

Fluxo:
    validar_entrada -> [invalido] -> gerar_saida_erro
                     -> [valido]  -> parsear_manifesto
    parsear_manifesto -> [sem dependencias] -> gerar_saida_erro
                       -> [ok]               -> consultar_registry
    consultar_registry -> consultar_osv
    consultar_osv -> [sem achado] -> gerar_saida_ok
                   -> [ha achado] -> resolver_restricoes -> avaliar_risco -> gerar_plano
"""
from __future__ import annotations

import operator
import os
from pathlib import Path
from typing import Annotated, Literal, TypedDict

import httpx
from langchain_groq import ChatGroq
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from langgraph.graph import END, StateGraph

from . import registries, resolver, vulns
from .parsers import Dependencia, Ecossistema, detectar_ecossistema, parse_manifesto
from .prompts import SISTEMA_AVALIACAO_RISCO, AvaliacaoRisco, RiscoItem, montar_prompt_risco
from .registries import InfoPacote, VersaoPacote
from .resolver import GrupoUpgrade, ResultadoResolucao
from .vulns import Vulnerabilidade

_TAMANHO_MAXIMO_BYTES = 1_000_000  # 1MB e generoso para um manifesto de dependencias
_RANK_SALTO = {"patch": 0, "minor": 1, "desconhecido": 1, "major": 2}


class EstadoUpgrade(TypedDict, total=False):
    caminho: str
    ecossistema: Ecossistema
    dependencias: list[Dependencia]
    versoes_atuais: dict[str, VersaoPacote]
    infos: dict[str, InfoPacote]
    vulnerabilidades: dict[str, list[Vulnerabilidade]]
    resolucao: ResultadoResolucao
    riscos: dict[str, RiscoItem]
    saida_md: str
    erros: Annotated[list[str], operator.add]


# --- nós -------------------------------------------------------------------


def validar_entrada(state: EstadoUpgrade) -> dict:
    caminho = state["caminho"]
    p = Path(caminho)
    if not p.exists():
        return {"erros": [f"arquivo não encontrado: {caminho}"]}
    tamanho = p.stat().st_size
    if tamanho == 0:
        return {"erros": [f"arquivo vazio: {caminho}"]}
    if tamanho > _TAMANHO_MAXIMO_BYTES:
        return {"erros": [f"arquivo maior que {_TAMANHO_MAXIMO_BYTES} bytes, recuso processar: {caminho}"]}
    try:
        ecossistema = detectar_ecossistema(caminho)
    except ValueError as exc:
        return {"erros": [str(exc)]}
    return {"ecossistema": ecossistema}


def parsear_manifesto(state: EstadoUpgrade) -> dict:
    manifesto = parse_manifesto(state["caminho"])
    erros = list(manifesto.erros)
    if not manifesto.dependencias:
        erros.append("nenhuma dependência válida encontrada no manifesto")
    return {"dependencias": manifesto.dependencias, "erros": erros}


def _versao_efetiva(dep: Dependencia, info: InfoPacote) -> str | None:
    """A versao que o instalador resolveria hoje dado o que o manifesto declara.

    Cobre tanto pin exato (==) quanto faixa (>=, ~=) ou ausencia de restricao —
    sem isso, so dependencia com == geraria sugestao de upgrade.
    """
    if not info.versoes:
        return None
    if not dep.restricao:
        return info.versoes[-1]
    try:
        spec = SpecifierSet(dep.restricao)
    except InvalidSpecifier:
        return None
    candidatos = [v for v in info.versoes if spec.contains(v, prereleases=False)]
    return candidatos[-1] if candidatos else None


def consultar_registry(state: EstadoUpgrade) -> dict:
    versoes_atuais: dict[str, VersaoPacote] = {}
    infos: dict[str, InfoPacote] = {}
    erros: list[str] = []

    for dep in state.get("dependencias", []):
        try:
            info = registries.consultar_pacote(dep.nome)
        except registries.PacoteNaoEncontrado:
            erros.append(f"{dep.nome}: não encontrado no registry")
            continue
        except (ValueError, httpx.HTTPError) as exc:
            erros.append(f"{dep.nome}: falha ao consultar registry ({exc})")
            continue

        versao_efetiva = _versao_efetiva(dep, info)
        if versao_efetiva is None:
            erros.append(f"{dep.nome}: nenhuma versão publicada satisfaz '{dep.restricao}'")
            continue

        try:
            versoes_atuais[dep.nome] = registries.consultar_versao(dep.nome, versao_efetiva)
        except httpx.HTTPError as exc:
            erros.append(f"{dep.nome}: falha ao consultar versão {versao_efetiva} ({exc})")
            continue
        infos[dep.nome] = info

    return {"versoes_atuais": versoes_atuais, "infos": infos, "erros": erros}


def consultar_osv(state: EstadoUpgrade) -> dict:
    vulnerabilidades: dict[str, list[Vulnerabilidade]] = {}
    erros: list[str] = []

    for nome, v in state.get("versoes_atuais", {}).items():
        try:
            achados = vulns.consultar_vulnerabilidades(nome, v.versao, state["ecossistema"])
        except httpx.HTTPError as exc:
            erros.append(f"{nome}: falha ao consultar OSV ({exc})")
            continue
        if achados:
            vulnerabilidades[nome] = achados

    return {"vulnerabilidades": vulnerabilidades, "erros": erros}


def resolver_restricoes(state: EstadoUpgrade) -> dict:
    resultado = resolver.montar_plano(state.get("versoes_atuais", {}), state.get("infos", {}))
    return {"resolucao": resultado}


def _itens_para_avaliar(resolucao: ResultadoResolucao) -> list[dict]:
    itens = []
    for grupo in resolucao.grupos:
        for up in grupo.upgrades:
            itens.append({"nome": up.nome, "de": up.de, "para": up.para, "salto": up.salto, "motivo": grupo.motivo})
    for bloq in resolucao.bloqueios:
        itens.append({
            "nome": bloq.nome, "de": bloq.versao_atual, "para": bloq.versao_desejada,
            "salto": "bloqueado", "motivo": bloq.motivo,
        })
    return itens


def avaliar_risco(state: EstadoUpgrade) -> dict:
    resolucao = state["resolucao"]
    itens = _itens_para_avaliar(resolucao)
    if not itens:
        return {"riscos": {}}

    if not os.environ.get("GROQ_API_KEY"):
        riscos = {
            i["nome"]: RiscoItem(nome=i["nome"], risco="desconhecido", explicacao="não avaliado — GROQ_API_KEY ausente")
            for i in itens
        }
        return {"riscos": riscos}

    modelo = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    llm = ChatGroq(model=modelo, temperature=0)
    estruturado = llm.with_structured_output(AvaliacaoRisco)
    resposta: AvaliacaoRisco = estruturado.invoke([
        {"role": "system", "content": SISTEMA_AVALIACAO_RISCO},
        {"role": "user", "content": montar_prompt_risco(itens)},
    ])
    riscos = {item.nome: item for item in resposta.itens}
    return {"riscos": riscos}


def _maior_salto(grupo: GrupoUpgrade) -> str:
    return max((u.salto for u in grupo.upgrades), key=lambda s: _RANK_SALTO.get(s, 1))


def _tem_cve(nomes: list[str], vulnerabilidades: dict[str, list[Vulnerabilidade]]) -> bool:
    return any(vulnerabilidades.get(n) for n in nomes)


def _formata_grupo(
    grupo: GrupoUpgrade,
    vulnerabilidades: dict[str, list[Vulnerabilidade]],
    riscos: dict[str, RiscoItem],
) -> str:
    linhas = []
    for up in grupo.upgrades:
        linhas.append(f"### {up.nome} {up.de} → {up.para}   [{up.salto}]")
        achados = vulnerabilidades.get(up.nome, [])
        if achados:
            ids = ", ".join(v.id for v in achados[:2])
            linhas.append(f"Por quê:     {ids} — {achados[0].resumo}  [OSV]")
        if grupo.motivo and len(grupo.upgrades) > 1:
            linhas.append(f"Move junto:  {grupo.motivo}  [PyPI]")
        risco = riscos.get(up.nome)
        if risco:
            linhas.append(f"Risco:       {risco.explicacao}  [LLM]")
    return "\n".join(linhas)


def gerar_plano(state: EstadoUpgrade) -> dict:
    resolucao = state["resolucao"]
    vulnerabilidades = state.get("vulnerabilidades", {})
    riscos = state.get("riscos", {})

    onda1, onda2, onda3 = [], [], []
    for grupo in resolucao.grupos:
        nomes = [u.nome for u in grupo.upgrades]
        if _tem_cve(nomes, vulnerabilidades):
            onda1.append(grupo)
        elif _maior_salto(grupo) == "major":
            onda3.append(grupo)
        else:
            onda2.append(grupo)

    partes = [
        f"# Plano de Upgrade — {Path(state['caminho']).name} ({state['ecossistema']})",
        f"> {len(state.get('dependencias', []))} dependências diretas · "
        f"{len(vulnerabilidades)} vulnerável(is) · "
        f"{len(resolucao.grupos)} com upgrade sugerido · "
        f"{len(resolucao.bloqueios)} bloqueada(s)",
        "",
    ]

    if onda1:
        partes.append("## Onda 1 — Urgente\n")
        partes += [_formata_grupo(g, vulnerabilidades, riscos) + "\n" for g in onda1]
    if onda2:
        partes.append("## Onda 2 — Seguro (sem CVE, salto pequeno)\n")
        partes += [_formata_grupo(g, vulnerabilidades, riscos) + "\n" for g in onda2]
    if onda3:
        partes.append("## Onda 3 — Exige trabalho (salto major)\n")
        partes += [_formata_grupo(g, vulnerabilidades, riscos) + "\n" for g in onda3]
    if resolucao.bloqueios:
        partes.append("## Bloqueados\n")
        for b in resolucao.bloqueios:
            partes.append(f"- **{b.nome}**: quer {b.versao_desejada}, preso em {b.versao_atual} — {b.motivo}  [PyPI]")

    if resolucao.sem_mudanca:
        partes.append(f"\n## Já em dia\n{', '.join(sorted(resolucao.sem_mudanca))}")

    return {"saida_md": "\n".join(partes)}


def gerar_saida_ok(state: EstadoUpgrade) -> dict:
    total = len(state.get("dependencias", []))
    md = (
        f"# Plano de Upgrade — {Path(state['caminho']).name} ({state.get('ecossistema', '?')})\n\n"
        f"Todas as {total} dependências diretas estão na última versão publicada, "
        f"sem vulnerabilidade conhecida no OSV.dev. Nada a fazer.\n"
    )
    return {"saida_md": md}


def gerar_saida_erro(state: EstadoUpgrade) -> dict:
    erros = state.get("erros", [])
    md = "# Plano de Upgrade — erro\n\n" + "\n".join(f"- {e}" for e in erros) + "\n"
    return {"saida_md": md}


# --- roteamento condicional -------------------------------------------------


def _apos_validar(state: EstadoUpgrade) -> Literal["erro", "ok"]:
    return "erro" if state.get("erros") else "ok"


def _apos_parsear(state: EstadoUpgrade) -> Literal["erro", "ok"]:
    return "erro" if not state.get("dependencias") else "ok"


def tem_achado(state: EstadoUpgrade) -> Literal["resolver", "ok"]:
    if state.get("vulnerabilidades"):
        return "resolver"
    infos = state.get("infos", {})
    for nome, v in state.get("versoes_atuais", {}).items():
        info = infos.get(nome)
        if info and info.versoes and info.versoes[-1] != v.versao:
            return "resolver"
    return "ok"


# --- montagem do grafo -------------------------------------------------------


def construir_grafo():
    g = StateGraph(EstadoUpgrade)
    g.add_node("validar_entrada", validar_entrada)
    g.add_node("parsear_manifesto", parsear_manifesto)
    g.add_node("consultar_registry", consultar_registry)
    g.add_node("consultar_osv", consultar_osv)
    g.add_node("resolver_restricoes", resolver_restricoes)
    g.add_node("avaliar_risco", avaliar_risco)
    g.add_node("gerar_plano", gerar_plano)
    g.add_node("gerar_saida_ok", gerar_saida_ok)
    g.add_node("gerar_saida_erro", gerar_saida_erro)

    g.set_entry_point("validar_entrada")
    g.add_conditional_edges(
        "validar_entrada", _apos_validar,
        {"erro": "gerar_saida_erro", "ok": "parsear_manifesto"},
    )
    g.add_conditional_edges(
        "parsear_manifesto", _apos_parsear,
        {"erro": "gerar_saida_erro", "ok": "consultar_registry"},
    )
    g.add_edge("consultar_registry", "consultar_osv")
    g.add_conditional_edges(
        "consultar_osv", tem_achado,
        {"resolver": "resolver_restricoes", "ok": "gerar_saida_ok"},
    )
    g.add_edge("resolver_restricoes", "avaliar_risco")
    g.add_edge("avaliar_risco", "gerar_plano")
    g.add_edge("gerar_plano", END)
    g.add_edge("gerar_saida_ok", END)
    g.add_edge("gerar_saida_erro", END)
    return g.compile()


def executar(caminho: str) -> str:
    grafo = construir_grafo()
    estado_final = grafo.invoke({"caminho": caminho, "erros": []})
    return estado_final["saida_md"]


def _demo() -> None:
    # entrada inexistente -> deve ir direto para gerar_saida_erro, sem rede
    saida = executar("exemplos/nao-existe.txt")
    assert "não encontrado" in saida, saida

    # manifesto vazio de verdade -> mesmo caminho de erro, motivo diferente
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix="_requirements.txt", delete=False) as f:
        caminho_vazio = f.name
    try:
        saida_vazia = executar(caminho_vazio)
        assert "vazio" in saida_vazia, saida_vazia
    finally:
        os.unlink(caminho_vazio)

    print("agent._demo: ok — caminhos de erro (sem rede) validados")


if __name__ == "__main__":
    _demo()
