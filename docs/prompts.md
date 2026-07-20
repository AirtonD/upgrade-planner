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
Certo, arquitetura fechada. Comece o desenvolvimento seguindo o cronograma
do ARQUITETURA.md: setup do repositório primeiro (.gitignore antes de
qualquer .env existir), depois cada ferramenta em sua própria branch, com
commit semântico e self-check antes de avançar para a próxima etapa.
```

### Cobrir manifestos sem pin exato

```
Antes de seguir, uma dúvida de design: a maioria dos requirements.txt reais
tem a versão da lib fixada com ==, ou costuma vir com faixa (>=, ~=) ou sem
versão nenhuma? Se o agente só sugerir upgrade para quem está com pin
exato, ele pode ficar mudo pra maioria dos projetos reais.
```

### Push, segurança e README

```
Faça o push de tudo que temos até agora para
https://github.com/AirtonD/upgrade-planner.git. Antes disso, adicione o PDF
do enunciado ao .gitignore — é material do curso, não faz parte da entrega.
E elabore o README.md completo, cobrindo o que o enunciado pede: problema,
objetivo, fluxo, ferramenta, como executar, exemplos de entrada e saída,
decisões tomadas e limitações.
```

### Revisão final da documentação

```
Quero que você revise toda a documentação do projeto — README, ARQUITETURA
e os demais arquivos em docs/. Confira se cada um está atendendo ao que o
enunciado pede e se o texto está conciso, sem repetição entre seções.
Aproveite para revisar a seção de como executar o projeto no README,
garantindo que os comandos estão corretos e completos.
```


### Segunda leitura do PDF, à procura de lacunas

```
Releia o PDF do enunciado do zero, com atenção, e compare cada requisito —
inclusive os critérios de avaliação e o checklist final — contra o estado
atual do repositório. Quero saber se ficou faltando alguma coisa, mesmo que
pareça pequena, antes da entrega.
```