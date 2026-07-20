"""Testes formais do agente (ARQUITETURA.md, secao 8).

Poucos testes, cobrindo exatamente os casos que o documento de arquitetura
promete: manifesto vazio, linha malformada, pacote inexistente, conflito
real. Nao e suite exaustiva — cada modulo ja tem seu proprio self-check
via `python -m src.<modulo>`; isto aqui formaliza os casos citados no
documento num arquivo que `python -m unittest` (ou pytest, se instalado)
descobre sozinho.

Roda com: python -m unittest discover -s tests
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import httpx
from dotenv import load_dotenv

from src.agent import avaliar_risco, executar
from src.parsers import parse_manifesto
from src.registries import InfoPacote, PacoteNaoEncontrado, VersaoPacote, consultar_pacote
from src.resolver import GrupoUpgrade, ResultadoResolucao, Upgrade, montar_plano

load_dotenv()  # pega GROQ_API_KEY do .env local, se existir — inofensivo se nao existir


class TestParserEEntradaInvalida(unittest.TestCase):
    def test_manifesto_vazio_nao_quebra_e_gera_saida_de_erro(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix="_requirements.txt", delete=False) as f:
            caminho = f.name
        try:
            manifesto = parse_manifesto(caminho)
            self.assertEqual(manifesto.dependencias, [])

            saida = executar(caminho)  # nao deve levantar excecao
            self.assertIn("vazio", saida)
        finally:
            Path(caminho).unlink()

    def test_linha_malformada_vai_para_erros_sem_derrubar_o_resto(self):
        manifesto = parse_manifesto("exemplos/requirements.txt")
        self.assertEqual(len(manifesto.erros), 1, manifesto.erros)
        self.assertGreater(len(manifesto.dependencias), 0)


class TestRegistryReal(unittest.TestCase):
    """Único teste que precisa de rede — pula (não falha) se ela não existir."""

    def test_pacote_inexistente_levanta_erro_claro(self):
        try:
            consultar_pacote("pacote-que-com-certeza-nao-existe-8f3k2j9z")
        except PacoteNaoEncontrado:
            return  # comportamento esperado
        except httpx.HTTPError as exc:
            self.skipTest(f"sem rede para consultar o PyPI real: {exc}")
        else:
            self.fail("esperava PacoteNaoEncontrado para um pacote que não existe")


class TestResolverConflitoReal(unittest.TestCase):
    """Mesma fixture do self-check de resolver.py, formalizada como teste.

    Inspirada no caso real fastapi 0.85.0 / pydantic 1.x -> 2.x, verificado
    contra a API do PyPI em 2026-07-17 (ver docs/prompts.md).
    """

    def test_fastapi_e_pydantic_resolvem_no_mesmo_grupo(self):
        versoes_atuais = {
            "fastapi": VersaoPacote(versao="0.85.0", requer=["pydantic<2.0.0,>=1.6.2"]),
            "pydantic": VersaoPacote(versao="1.10.2", requer=[]),
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
        }
        resultado = montar_plano(versoes_atuais, infos)
        self.assertEqual(resultado.bloqueios, [])
        self.assertEqual(len(resultado.grupos), 1)
        self.assertEqual({u.nome for u in resultado.grupos[0].upgrades}, {"fastapi", "pydantic"})

    def test_conflito_sem_saida_fica_bloqueado(self):
        versoes_atuais = {
            "pacote-a": VersaoPacote(versao="1.0.0", requer=["pacote-b<2.0.0"]),
            "pacote-b": VersaoPacote(versao="1.9.0", requer=[]),
        }
        infos = {
            "pacote-a": InfoPacote(
                nome="pacote-a", versoes=["1.0.0", "1.1.0"],
                ultima=VersaoPacote(versao="1.1.0", requer=["pacote-b<2.0.0"]),  # nao relaxou
            ),
            "pacote-b": InfoPacote(
                nome="pacote-b", versoes=["1.9.0", "2.5.0"],
                ultima=VersaoPacote(versao="2.5.0", requer=[]),
            ),
        }
        resultado = montar_plano(versoes_atuais, infos)
        self.assertEqual(resultado.grupos, [])
        self.assertEqual({b.nome for b in resultado.bloqueios}, {"pacote-a", "pacote-b"})


class TestAvaliarRiscoFalhaDoProvedor(unittest.TestCase):
    """Sem GROQ_API_KEY não é a única forma de o LLM falhar — a chamada em si
    pode dar rate limit, timeout, ou modelo inexistente. avaliar_risco precisa
    degradar (fallback "não avaliado"), nunca derrubar o agente inteiro.
    """

    def test_modelo_invalido_cai_no_fallback_em_vez_de_quebrar(self):
        if not os.environ.get("GROQ_API_KEY"):
            self.skipTest("sem GROQ_API_KEY para exercitar a chamada real ao provedor")

        estado = {
            "resolucao": ResultadoResolucao(
                grupos=[GrupoUpgrade(upgrades=[Upgrade(nome="requests", de="2.28.1", para="2.32.4", salto="minor")])],
                bloqueios=[],
            )
        }
        antigo = os.environ.get("GROQ_MODEL")
        os.environ["GROQ_MODEL"] = "modelo-que-nao-existe-8f3k2j9z"
        try:
            resultado = avaliar_risco(estado)  # nao deve levantar excecao
        finally:
            if antigo is None:
                os.environ.pop("GROQ_MODEL", None)
            else:
                os.environ["GROQ_MODEL"] = antigo

        self.assertIn("requests", resultado["riscos"])
        self.assertEqual(resultado["riscos"]["requests"].risco, "desconhecido")
        self.assertIn("erros", resultado)


if __name__ == "__main__":
    unittest.main()
