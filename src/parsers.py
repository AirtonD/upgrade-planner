"""Le manifestos de dependencias (requirements.txt, package.json) e normaliza
para um modelo comum, independente de ecossistema.

Linha malformada nao derruba a execucao: vai para `erros` e o resto segue
(ver ARQUITETURA.md, secao 8 — Validacao).
"""
from __future__ import annotations

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


def parse_manifesto(caminho: str | Path) -> ManifestoParseado:
    # ecossistema "npm" chega aqui na etapa feat/parser-package-json
    ecossistema = detectar_ecossistema(caminho)
    if ecossistema == "npm":
        raise NotImplementedError("suporte a package.json vem na próxima etapa")
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
    print("parsers._demo: ok —", len(m.dependencias), "dependências,", len(m.erros), "erro(s)")


if __name__ == "__main__":
    _demo()
