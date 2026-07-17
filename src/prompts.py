"""Prompts do LLM, isolados do código de fluxo (ARQUITETURA.md, secao 3).

O LLM aqui só julga risco de quebra — nunca inventa versão, CVE ou nome de
pacote; esses fatos vêm sempre do estado, montado pelas ferramentas.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SISTEMA_AVALIACAO_RISCO = """\
Você avalia o risco de QUEBRA (não de segurança) ao aplicar upgrades de \
dependências em um projeto de software.

Para cada item da lista, classifique o risco de o upgrade quebrar o projeto, \
considerando o tamanho do salto de versão (patch/minor/major) e, se houver, \
o motivo pelo qual duas dependências precisam subir juntas.

Responda em português, direto, em 1 a 2 frases por item. Baseie-se apenas nos \
dados fornecidos na lista — não invente número de versão, CVE ou nome de \
pacote que não apareça nela."""


class RiscoItem(BaseModel):
    nome: str
    risco: Literal["baixo", "medio", "alto", "desconhecido"]
    explicacao: str


class AvaliacaoRisco(BaseModel):
    itens: list[RiscoItem]


def montar_prompt_risco(itens: list[dict]) -> str:
    linhas = []
    for item in itens:
        linha = f"- {item['nome']}: {item['de']} → {item['para']} [{item['salto']}]"
        if item.get("motivo"):
            linha += f" — motivo do agrupamento: {item['motivo']}"
        linhas.append(linha)
    return "Avalie o risco de quebra de cada upgrade abaixo:\n\n" + "\n".join(linhas)
