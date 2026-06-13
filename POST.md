# Material de lançamento — BCP (Brasico open-source)

Rascunhos prontos para virar post de blog, thread no X, post no LinkedIn e
release no GitHub. Todos os números são medições reais e reprodutíveis
(`python bench.py`). Tom: engenharia honesta, orientada a dados — não hype.

---

## 1) Tweet/X — thread (PT)

**1/**
A gente construiu um "mapa de código" pra agentes de IA. Materializamos ele do
jeito errado primeiro. Medimos. Era peso morto. Reescrevemos.

Resultado: até **89% menos tokens** de contexto. 100% local. MIT.

Abrindo o código → 🧵

**2/**
O problema: agente de código falha por contexto.
• arquivo cru estoura o orçamento de tokens (= caro + lento)
• o modelo se perde em milhares de linhas que não importam

80–90% de um arquivo é *corpo* que o modelo não precisa ler. Ele precisa da
*forma*: o que existe e como conecta.

**3/**
A ideia (mesma família do repo-map do Aider, do índice do Cursor):
extrair só as **assinaturas** — funções, classes, tipos, imports — do arquivo-alvo
+ a vizinhança de imports (BFS 2 hops). Guardar num índice **SQLite** consultável.

**4/**
Telemetria real (medida, reproduzível):

| contexto | tokens |
|---|---|
| arquivo cru → modelo | ~184.781 |
| mapa BCP → modelo | ~20.141 |

**−89%.** E escala com o tamanho do arquivo: quanto maior, maior o ganho.

**5/**
O erro que cometemos primeiro (e a parte mais útil pra você):
materializamos o mapa como **YAML estático, regenerado a cada commit**.

Medimos:
• 0 leitores em runtime
• ~4,3s de imposto por commit
• churn tóxico no git

**6/**
Lição: **não commite seu índice de código.** Ele é um artefato derivado e
efêmero — igual `node_modules` ou um `.o`. Construa sob demanda, mantenha fora
do git, sempre fresco.

Trocamos o YAML estático por um índice SQLite vivo. Foi isso que destravou os 89%.

**7/**
O BCP é stdlib-first (Python via `ast`, TS/JS via tree-sitter), sub-1k linhas,
roda offline, MIT.

Reproduz em qualquer repo:
`python3 bench.py <projeto> <arquivo-alvo>`

GitHub: github.com/gab11s/bcp-code-planogram
Feito pela @brasico 🇧🇷

---

## 2) LinkedIn (PT) — versão profissional

**Abrimos o código de uma peça que reduz até 89% dos tokens de contexto de agentes de IA — e da nossa decisão de engenharia mais útil no caminho.**

Construindo o BRACOPED (nosso IDE com agentes), enfrentamos o gargalo de todo
agente de código: contexto. Mandar arquivos crus para o modelo é caro, lento e
ruidoso — 80 a 90% de um arquivo é corpo que o modelo não precisa ler.

A solução é dar ao agente um **mapa**: só as assinaturas (funções, classes,
tipos) do arquivo-alvo e da sua vizinhança de imports. É a mesma família de
ideias do repo-map do Aider e do índice do Cursor.

O que vale compartilhar não é só o ganho — é o **erro no meio do caminho**.
Materializamos esse mapa como YAML estático, regenerado a cada commit. Quando
medimos, descobrimos: zero leitores em runtime, ~4,3s de imposto por commit e
poluição constante do histórico do git. Substituímos por um índice SQLite vivo,
consultado sob demanda. Foi isso que entregou os números:

• Contexto sem o mapa: ~184.781 tokens
• Contexto com o mapa: ~20.141 tokens
• **Economia: 89%** (e cresce com o tamanho do arquivo)

A lição que levamos — e que está no README — é simples: **não versione seu
índice de código.** Ele é derivado e efêmero. Construa sob demanda, fora do git.

Liberamos tudo sob licença MIT: sub-1k linhas, stdlib-first, 100% local,
reproduzível em qualquer repositório com um comando.

👉 github.com/gab11s/bcp-code-planogram

#AI #LLM #DeveloperTools #OpenSource #Engineering

---

## 3) GitHub Release notes — v0.1.0

**BCP v0.1.0 — a token-efficient code map for LLM agents**

Give your coding agent a map, not the whole library.

BCP extracts only the *signatures* of a target file and its import-neighborhood
into a queryable SQLite index — instead of pasting raw files into the prompt.

**Highlights**
- 📉 Up to **89% fewer context tokens** (measured, reproducible via `bench.py`).
- 🐍 Stdlib-first: Python via `ast`, TS/JS/TSX via tree-sitter (optional), Swift via regex.
- ⚡ Local SQLite index, incremental by file hash. No service, no GPU.
- 🧪 16 tests, MIT-licensed, sub-1k lines.

**Why it exists / the design lesson**
We first shipped this as static YAML regenerated on every commit. We measured:
0 runtime readers, ~4.3s/commit tax, toxic git churn. We deleted it and kept a
live, on-demand SQLite index. Don't commit your code index — it's a derived,
ephemeral artifact.

**Try it**
```bash
python3 -m pip install -e .
python3 bench.py . bcp/signature_indexer.py
```

---

## 4) Hacker News / Reddit (EN) — "Show HN" style title + body

**Title:** Show HN: BCP — a code map that cuts LLM agent context by up to 89% (and why we deleted our first version)

**Body:**
We build an agent IDE and kept hitting the context wall: raw files are expensive,
slow, and noisy for the model. BCP extracts only the signatures (functions,
classes, types, imports) of a target file plus its import-neighborhood into a
SQLite index, queried on demand. Same idea family as Aider's repo-map.

The honest part: we first materialized this as static YAML regenerated on every
commit. Measured it: zero runtime readers, ~4.3s/commit, constant git churn. We
deleted it and kept the live index. That's what got us the savings.

Numbers are reproducible on any repo with `python3 bench.py <root> <file>`.
Stdlib-first, sub-1k lines, MIT.

Would love feedback on the neighborhood-ranking next step (PageRank-style, to fit
a hard token budget like Aider does).

---

## 5) Ângulo "BCP for humans" — thread (PT) [muito visual, ótimo p/ engajar]

**1/**
"BCP" vem de *planograma* — aquele mapa de supermercado que diz em qual
prateleira cada produto fica.

A gente fez um planograma do CÓDIGO. Pasta = corredor. Arquivo = produto.
Tamanho = linhas. Cor = tipo.

Uma linha de comando, qualquer repo → 🧵

**2/**
```bash
bcp planogram ./meu-repo --format html > planograma.html
```
Abre no navegador: o repo inteiro como uma loja. O corredor gigante azul? A UI.
A borda vermelha? Arquivo crítico de segurança.

[anexe o screenshot do treemap aqui]

**3/**
Por que importa: onboarding, code review, "onde diabos fica X", dívida técnica —
fica óbvio quando você VÊ a proporção. 80k linhas num corredor e 300 noutro
conta uma história na hora.

**4/**
Bônus: o MESMO scan que desenha pra humanos alimenta o mapa pra agentes de IA
(−89% de tokens de contexto). Um dado, dois consumidores: gente e modelo.

Mermaid também sai pronto pra colar no GitHub/docs:
`bcp planogram . --format mermaid`

**5/**
stdlib puro, sem deps, MIT. github.com/gab11s/bcp-code-planogram · @brasico 🇧🇷

---

## Notas de uso
- URL final do repo: `github.com/gab11s/bcp-code-planogram`.
- Para o "for humans": anexe um **screenshot do treemap** (planograma.html) — é o
  visual que mais engaja. O Mermaid (`--format mermaid`) renderiza direto no README/GitHub.
- Os números 89% / 184.781 / 20.141 vieram de arquivos grandes (servidor). Para
  alvos menores o ganho é 40–77% — use a faixa "**40–89%, escala com o tamanho do
  arquivo**" para ser preciso e não prometer demais.
- Sempre que possível, anexe um GIF do `bench.py` rodando — prova social honesta.
