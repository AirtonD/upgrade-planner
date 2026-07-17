"""Le manifestos de dependencias (requirements.txt, package.json) e normaliza
para um modelo comum, independente de ecossistema.

Linha malformada nao derruba a execucao: vai para `erros` e o resto segue
(ver ARQUITETURA.md, secao 8 — Validacao).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from packaging.requirements import InvalidRequirement, Requirement
from pydantic import BaseModel

Ecossistema = Literal["PyPI", "npm"]


class Dependencia(BaseModel):
    nome: str
    restricao: str
    extras: tuple[str, ...] = ()


class ManifestoParseado(BaseModel):
    ecossistema: Ecossistema
    dependencias: list[Dependencia]
    erros: list[str] = []


_PREFIXOS_IGNORADOS = (
    "-r ", "--requirement",
    "-e ", "--editable",
    "-c ", "--constraint",
    "-i ", "--index-url", "--extra-index-url",
    "-f ", "--find-links",
)


def detectar_ecossistema(caminho: str | Path) -> Ecossistema:
    nome = Path(caminho).name.lower()
    if nome == "package.json":
        return "npm"
    if nome.endswith(".txt") or "requirements" in nome:
        return "PyPI"
    raise ValueError(
        f"não reconheço o formato de {caminho!r} — "
        "esperado requirements.txt (suporte a package.json vem na próxima etapa)"
    )


def parse_requirements_txt(caminho: str | Path) -> ManifestoParseado:
    texto = Path(caminho).read_text(encoding="utf-8")
    dependencias: list[Dependencia] = []
    erros: list[str] = []

    for numero, linha_bruta in enumerate(texto.splitlines(), start=1):
        linha = linha_bruta.split("#", 1)[0].strip()
        if not linha or linha.startswith(_PREFIXOS_IGNORADOS):
            continue

        try:
            req = Requirement(linha)
        except InvalidRequirement as exc:
            erros.append(f"linha {numero}: {linha_bruta.strip()!r} inválida — {exc}")
            continue

        dependencias.append(
            Dependencia(
                nome=req.name.lower().replace("_", "-"),
                restricao=str(req.specifier),
                extras=tuple(sorted(req.extras)),
            )
        )

    return ManifestoParseado(ecossistema="PyPI", dependencias=dependencias, erros=erros)


_CAMPOS_DEPENDENCIA = ("dependencies", "devDependencies")


def parse_package_json(caminho: str | Path) -> ManifestoParseado:
    texto = Path(caminho).read_text(encoding="utf-8")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc:
        return ManifestoParseado(ecossistema="npm", dependencias=[], erros=[f"JSON inválido: {exc}"])

    dependencias: list[Dependencia] = []
    erros: list[str] = []

    for campo in _CAMPOS_DEPENDENCIA:
        bloco = dados.get(campo)
        if bloco is None:
            continue
        if not isinstance(bloco, dict):
            erros.append(f"{campo}: esperava um objeto {{nome: versão}}, achei {type(bloco).__name__}")
            continue
        for nome, restricao in bloco.items():
            if not isinstance(restricao, str):
                erros.append(f"{campo}.{nome}: valor não é uma string de versão")
                continue
            dependencias.append(Dependencia(nome=nome.strip(), restricao=restricao.strip()))

    return ManifestoParseado(ecossistema="npm", dependencias=dependencias, erros=erros)


def parse_manifesto(caminho: str | Path) -> ManifestoParseado:
    ecossistema = detectar_ecossistema(caminho)
    if ecossistema == "npm":
        return parse_package_json(caminho)
    return parse_requirements_txt(caminho)


def _demo() -> None:
    m = parse_manifesto("exemplos/requirements.txt")
    assert m.ecossistema == "PyPI"
    assert len(m.erros) == 1, f"esperava 1 linha inválida, achei {m.erros}"
    nomes = {d.nome for d in m.dependencias}
    assert nomes == {
        "fastapi", "pydantic", "requests", "urllib3",
        "python-dotenv", "uvicorn", "boto3", "botocore",
    }, nomes
    fastapi = next(d for d in m.dependencias if d.nome == "fastapi")
    assert fastapi.restricao == "==0.85.0"
    uvicorn = next(d for d in m.dependencias if d.nome == "uvicorn")
    assert uvicorn.extras == ("standard",)

    m2 = parse_manifesto("exemplos/package.json")
    assert m2.ecossistema == "npm"
    assert not m2.erros, m2.erros
    nomes2 = {d.nome for d in m2.dependencias}
    assert nomes2 == {"express", "lodash", "axios", "body-parser", "nodemon"}, nomes2
    express = next(d for d in m2.dependencias if d.nome == "express")
    assert express.restricao == "^4.17.1"

    print(
        f"parsers._demo: ok — PyPI: {len(m.dependencias)} dependências, {len(m.erros)} erro(s) | "
        f"npm: {len(m2.dependencias)} dependências, {len(m2.erros)} erro(s)"
    )


if __name__ == "__main__":
    _demo()
