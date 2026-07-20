### Extrair a arquitetura a partir do enunciado

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

### Recusa das sugestões genéricas de agente

```
Não gostei das ideias de projeto. Revisor de pull request, triador de issues,
analisador de log de pipeline — isso é exatamente o que um assistente de código
já faz de fábrica, sem LangGraph nenhum. Construir isso é reimplementar pior o
que eu já tenho aberto na outra janela.

Quero ideias em que o agente entregue algo que a ferramenta de vibe coding não
entrega sozinha.
```

### Recorte de domínio

```
As novas ideias têm núcleo computacional melhor, mas erraram o domínio: preciso
de algo ligado a desenvolvimento de software.

Uma linha que me interessou foi análise de bibliotecas e versões. Sei que um
agente também faz isso hoje, mas quero explorar essa direção — me mostre o que
existe nela que não seja trivial.
```

---

### Validação da ideia e definição da saída

```
Sobre o planejador de upgrade: quero sua opinião honesta, incluindo o que há de
fraco nele — não só o argumento de venda.

E defina a saída concretamente. "Um relatório" não é resposta: quero ver o
formato do artefato que o usuário recebe no fim.

Além disso, ele deve aceitar qualquer manifesto de dependências, não só o do
Python — o package.json do Node também.
```

### Estrutura e rastreamento da entrega

```
Fechado nessa linha. Monte a estrutura completa do documento com o projeto
definido e deixe explícito que todos os critérios precisam estar atendidos no
final — quero um rastreador de progresso, marcando o que já foi feito e o que
falta, para consultar até a entrega.
```

---

### Início da implementação

```
Certo, comece o desenvolvimento.
```

### Cobrir manifestos sem pin exato

```
Uma dúvida antes: a maioria dos requirements.txt tem a versão da lib fixada?
```

Levou à correção de `_versao_efetiva`/`_versao_efetiva_npm` em `agent.py`: a versão comparada passou a ser calculada a partir de qualquer restrição do manifesto (`==`, `>=`, `~=`, `^`, `~` ou ausência de restrição), não só pin exato. Sem isso, o agente ficaria mudo para a maioria dos `requirements.txt` reais, que não são gerados por `pip freeze`.

### Push, segurança e README

```
Faça push do que fizemos, mas coloque o pdf no gitignore também, e elabore
o readme. https://github.com/AirtonD/upgrade-planner.git
```

### Revisão final da documentação

```
Quero que revise toda a documentação, readme, veja se está tudo atendendo e
conciso, e atualize também a forma de rodar no readme.
```

Encontrada e corrigida uma inconsistência real durante a revisão: `ARQUITETURA.md` recomendava `python src/main.py` para rodar o agente — comando que quebraria, já que `main.py` usa import relativo (`from .agent import executar`) e só funciona com `python -m src.main`.

### Segunda leitura do PDF, à procura de lacunas

```
Analise novamente o pdf e veja se está faltando alguma coisa.
```

Reler o critério 8 ("validações... evitando o processamento de dados malformados") contra o código expôs uma lacuna real, não só de documentação: `avaliar_risco` tratava a ausência de `GROQ_API_KEY`, mas não tratava falha da chamada em si — rate limit, timeout, ou o modelo devolvendo algo que não valida contra `AvaliacaoRisco`. Sem captura, isso derrubava o agente inteiro no meio de uma demonstração. Corrigido com `try/except` ao redor do `invoke`, caindo no mesmo fallback "não avaliado" do caso sem chave. Testado forçando um `GROQ_MODEL` inválido contra a API real (confirma que degrada, não quebra) e formalizado em `tests/test_agent.py`.