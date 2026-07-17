# Prompts do desenvolvimento

Registro dos principais prompts usados para planejar, implementar, corrigir e melhorar o agente, conforme item 5 dos Requisitos da Aplicação.

> **Nota:** os prompts abaixo foram consolidados e editados para leitura — a conversa real teve idas e voltas, mensagens curtas e correções de rumo. O conteúdo e a ordem das decisões são fiéis ao processo; a redação foi limpa. As rejeições e mudanças de direção estão preservadas de propósito: elas são a parte mais honesta do registro.

**Ferramenta usada:** Claude (Anthropic) via Claude Code
**Modelo:** Opus 4.8

---

## Fase 1 — Planejamento e leitura do enunciado

### 1.1. Extrair a arquitetura a partir do enunciado

```
Anexei o PDF do mini-projeto avaliativo do módulo. Leia o documento inteiro e
monte um documento de arquitetura em markdown baseado exclusivamente nas regras
e critérios que estão nele.

O documento precisa:
- rastrear cada critério de avaliação até o artefato que o atende, para eu
  conseguir conferir a entrega item a item;
- deixar explícito onde está o peso da nota, não tratar todos os critérios como
  se valessem a mesma coisa;
- propor a estrutura de pastas, o desenho do fluxo em LangGraph, o estado
  compartilhado, os pontos de validação e os cuidados de segurança;
- apontar as divergências ou ambiguidades do próprio enunciado, se houver.

Além disso, sugira projetos que se encaixem nas regras. Não escolha por mim
ainda — quero avaliar as opções.
```

**Resultado:** primeira versão do `ARQUITETURA.md`. Duas descobertas úteis:
- documentação (2,0) + contexto/memória/validação (2,0) = 4 dos 10 pontos, contra 2,0 de "o agente funciona" — isso mudou a prioridade do cronograma;
- o PDF tem divergência de horário na entrega (22h no corpo, 15h no checklist) → adotado o mais conservador.

---

## Fase 2 — Rejeição das primeiras ideias

### 2.1. Recusa das sugestões genéricas de agente

```
Não gostei das ideias de projeto. Revisor de pull request, triador de issues,
analisador de log de pipeline — isso é exatamente o que um assistente de código
já faz de fábrica, sem LangGraph nenhum. Construir isso é reimplementar pior o
que eu já tenho aberto na outra janela.

Quero ideias em que o agente entregue algo que a ferramenta de vibe coding não
entrega sozinha.
```

**Resultado:** o critério de escolha foi reformulado. Diagnóstico: nas ideias rejeitadas a ferramenta só lia um arquivo e passava texto para o modelo — o LLM fazia o trabalho todo e a ferramenta era decoração. Isso também enfraquecia o critério 6, cujo rubric fala em "execução autônoma de ações estruturadas".

**Filtro adotado a partir daqui:**

> A ferramenta precisa fazer algo que o LLM é **incapaz** de fazer sozinho — calcular, resolver, ou consultar um dado que não existe nos pesos do modelo.

### 2.2. Recorte de domínio

```
As novas ideias têm núcleo computacional melhor, mas erraram o domínio: preciso
de algo ligado a desenvolvimento de software.

Uma linha que me interessou foi análise de bibliotecas e versões. Sei que um
agente também faz isso hoje, mas quero explorar essa direção — me mostre o que
existe nela que não seja trivial.
```

**Resultado:** o recorte que sobreviveu ao filtro da 2.1:
- o LLM **não sabe a versão atual de nada** (knowledge cutoff), então todo fato precisa vir de API;
- escolher o que subir **não é lookup, é satisfação de restrições** sobre um grafo — o resolvedor do pip é um SAT solver.

---

## Fase 3 — Fechamento do escopo

### 3.1. Validação da ideia e definição da saída

```
Sobre o planejador de upgrade: quero sua opinião honesta, incluindo o que há de
fraco nele — não só o argumento de venda.

E defina a saída concretamente. "Um relatório" não é resposta: quero ver o
formato do artefato que o usuário recebe no fim.

Além disso, ele deve aceitar qualquer manifesto de dependências, não só o do
Python — o package.json do Node também.
```

**Resultado:**

1. **APIs verificadas antes de assumir** (PyPI JSON API, npm registry, OSV.dev) — todas públicas, sem token. O OSV aceita `PyPI` e `npm` com a mesma query, o que tornou o suporte aos dois manifestos barato e justificou o pedido.
2. **Correção de rota no solver:** a ideia inicial de "menor conjunto de upgrades que zera CVEs" foi descartada — na prática degenera em "suba cada pacote vulnerável" e vira gimmick. O núcleo real virou: maior versão viável por dependência + agrupamento das que precisam se mover juntas.
3. **Assimetria pip × npm identificada:** pip é flat (conflito real existe); npm aninha `node_modules` (conflito quase não existe, só em `peerDependencies`). Decisão: aceitar os dois e **declarar a assimetria** no README em vez de fingir simetria.
4. **Saída definida:** plano em ondas de execução, com etiqueta de procedência por linha (`[PyPI]`, `[OSV]`, `[LLM]`) — todo fato rastreável à fonte, só o julgamento é do modelo.

### 3.2. Estrutura e rastreamento da entrega

```
Fechado nessa linha. Monte a estrutura completa do documento com o projeto
definido e deixe explícito que todos os critérios precisam estar atendidos no
final — quero um rastreador de progresso, marcando o que já foi feito e o que
falta, para consultar até a entrega.

Registre também os prompts em docs/prompts.md.
```

**Resultado:** `ARQUITETURA.md` reescrito com o projeto fechado e a seção 1 (Status da entrega) servindo de checklist vivo; este arquivo criado.

---

## Fase 4 — Implementação

> A preencher conforme o desenvolvimento avança. Registrar aqui os prompts que
> geraram código, os que corrigiram bugs e os que melhoraram a solução.

<!--
Modelo para as próximas entradas:

### 4.x. <o que foi pedido>

```
<prompt>
```

**Resultado:** <o que mudou no projeto, e o que foi descartado ou corrigido>
-->
