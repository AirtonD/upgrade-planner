"""Ferramenta: consulta CVEs/GHSAs reais no OSV.dev para um pacote+versão.

Mesma query serve para PyPI e npm (ambos são ecossistemas válidos do OSV) —
é isso que torna o suporte aos dois manifestos barato (ARQUITETURA.md, secao 4).
"""
from __future__ import annotations

import httpx
from pydantic import BaseModel

from .parsers import Ecossistema

_TIMEOUT = httpx.Timeout(10.0)
_HEADERS = {"User-Agent": "planejador-upgrade/0.1 (mini-projeto IA para DEVs)"}
_URL = "https://api.osv.dev/v1/query"


class Vulnerabilidade(BaseModel):
    id: str
    resumo: str
    severidade: str | None = None
    aliases: list[str] = []
    referencias: list[str] = []


def _severidade(vuln: dict) -> str | None:
    for s in vuln.get("severity", []):
        if s.get("type") in ("CVSS_V3", "CVSS_V4"):
            return s["score"]
    return None


def consultar_vulnerabilidades(
    nome: str, versao: str, ecossistema: Ecossistema
) -> list[Vulnerabilidade]:
    if not nome.strip() or not versao.strip():
        raise ValueError("nome e versão são obrigatórios para consultar o OSV")

    resp = httpx.post(
        _URL,
        json={"package": {"name": nome, "ecosystem": ecossistema}, "version": versao},
        timeout=_TIMEOUT,
        headers=_HEADERS,
    )
    resp.raise_for_status()

    vulnerabilidades = []
    for v in resp.json().get("vulns", []):
        vulnerabilidades.append(
            Vulnerabilidade(
                id=v["id"],
                resumo=v.get("summary") or (v.get("details") or "")[:200].strip(),
                severidade=_severidade(v),
                aliases=v.get("aliases", []),
                referencias=[
                    r["url"] for r in v.get("references", []) if "url" in r
                ][:3],
            )
        )
    return vulnerabilidades


def _demo() -> None:
    vulns = consultar_vulnerabilidades("requests", "2.28.1", "PyPI")
    assert vulns, "requests 2.28.1 é conhecidamente vulnerável, esperava >=1 achado"
    ids = {v.id for v in vulns}
    assert any(i.startswith("GHSA-") for i in ids), ids

    sem_vulns = consultar_vulnerabilidades("requests", "2.32.4", "PyPI")
    assert len(sem_vulns) < len(vulns), "versão corrigida devia ter menos achados que a antiga"

    print(f"vulns._demo: ok — requests 2.28.1 tem {len(vulns)} vulnerabilidade(s) conhecida(s)")


if __name__ == "__main__":
    _demo()
