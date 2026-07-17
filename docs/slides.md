<!--
Apresentação da ideia do projeto — Mini-Projeto Avaliativo, Módulo 2,
IA para Desenvolvedores [T1]. Até 2 slides, conforme exigido.

Compatível com Marp (marp-cli / extensão do VS Code): cada "---" abaixo é
uma quebra de slide. Sem a ferramenta, o arquivo se lê normalmente como
markdown — os "---" viram apenas linhas horizontais.
-->

---

# Planejador de Upgrade de Dependências

**O problema**
Manter dependências é sempre adiado até virar incidente. `pip list --outdated` diz o que está velho; `pip-audit` diz o que é vulnerável. Nenhuma ferramenta responde a pergunta real: *por onde eu começo, o que sobe sem quebrar, e o que vai dar trabalho?*

**Processo automatizado**
Priorizar upgrade de dependências (`requirements.txt` / `package.json`) num plano executável, cruzando versão real, CVE real e conflito real entre as próprias dependências do projeto.

**Proposta do agente**
Um agente LangGraph que decide — não só consulta — o que fazer com cada dependência: quando não há achado, encerra sem gastar LLM; quando há conflito entre dependências do manifesto, resolve antes de julgar risco.

| | |
|---|---|
| **Entrada** | Caminho de um `requirements.txt` ou `package.json` |
| **Saída** | `plano-upgrade.md` — upgrades agrupados em ondas, cada linha marcada com a fonte do fato (`[PyPI]`/`[OSV]`) ou o julgamento (`[LLM]`) |

---

## Fluxo e ferramentas

```
manifesto → validar → parsear → consultar registry → consultar OSV.dev
                                        │
                          há CVE ou versão desatualizada?
                                 não ↓        ↓ sim
                          "tudo em dia"   resolver conflitos → LLM avalia risco
                                              │
                                     plano-upgrade.md (ondas)
```

**Ferramentas integradas** (ações reais, não simuladas):
- **Cliente PyPI / npm** — versões publicadas, datas, `requires_dist` de cada uma
- **Cliente OSV.dev** — CVEs/GHSAs reais por pacote+versão
- **Resolvedor de restrições** — detecta quando uma dependência do manifesto trava a versão de outra, e testa se subir as duas juntas resolve (ex.: `fastapi==0.85.0` trava `pydantic<2.0.0` — o agente descobre isso consultando a API real, não é regra escrita à mão)

**Por que é um agente, não um script**: o LLM nunca inventa versão ou CVE — só julga risco de quebra, e só quando há algo real para julgar. O conhecimento do modelo tem corte no tempo; toda versão e vulnerabilidade vêm de consulta ao vivo.
