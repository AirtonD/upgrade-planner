"""CLI: python -m src.main <manifesto>

Roda o agente ponta a ponta e escreve saidas/plano-upgrade.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

from .agent import executar


def main() -> int:
    if len(sys.argv) != 2:
        print("uso: python -m src.main <caminho-do-manifesto>", file=sys.stderr)
        return 2

    load_dotenv()
    caminho = sys.argv[1]

    plano_md = executar(caminho)

    destino = Path("saidas")
    destino.mkdir(exist_ok=True)
    arquivo_saida = destino / "plano-upgrade.md"
    arquivo_saida.write_text(plano_md, encoding="utf-8")

    print(plano_md)
    print(f"\n[gravado em {arquivo_saida}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
