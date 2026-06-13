# BCP — Code Planogram

[![CI](https://github.com/gab11s/bcp-code-planogram/actions/workflows/ci.yml/badge.svg)](https://github.com/gab11s/bcp-code-planogram/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Give your coding agent a map, not the whole library.**

BCP extracts a *token-efficient map* of your codebase — only the **signatures**
(functions, classes, methods, types, imports) of a target file and its
import-neighborhood — instead of pasting raw files into an LLM prompt. The map
lives in a fast **SQLite index**, queried on demand, always fresh, never committed.

Same family of ideas as Aider's repo-map, Cursor's index and Sourcegraph Cody —
implemented in **sub-1k lines, stdlib-first, 100% local, MIT**.

**BCP has two halves:**
- **for agents** — the token-efficient signature map above (`SignatureIndexer`).
- **for humans** — a **code planogram**: the supermarket metaphor, literal. The
  name comes from retail *planograms* (the shelf map of where every product
  goes). BCP draws a planogram of your repo: each **folder is an aisle**, each
  **file a product**, the **size is shelf space** (lines of code), the **color
  is the category**. See [BCP for humans](#bcp-for-humans--the-code-planogram).

> Originally extracted from [BRACOPED](https://brasico.ai) (Brasico). We built a
> heavier static version first, measured it, found it was dead weight, and
> replaced it with this. The numbers below are why.

**Project status:** early, usable, local-first, and intentionally small.
If you want a public starting point for agent context reduction without a
server-side index, this is the whole point of the repository.

---

## Why

Coding agents fail on context in two ways:
- **Cost & latency** — raw files blow the token budget.
- **Noise** — the model drowns in thousands of irrelevant lines.

Most of a file is *body* the model doesn't need to read — it needs to know the
*shape*: what exists and how it connects. BCP gives it exactly that.

## Telemetry — measured, reproducible

`bench.py` measures the tokens needed to "understand" target file(s), **with**
vs **without** BCP. Real runs (`~4 chars/token` estimator):

| Target set | WITHOUT BCP (raw) | WITH BCP (map) | Savings |
|---|---:|---:|---:|
| 3 mid-size modules | ~34,461 | ~19,281 | **44%** |
| This repo (3 files) | ~5,430 | ~1,255 | **77%** |
| 3 large modules (e.g. a web server) | ~184,781 | ~20,141 | **89%** |

**Savings scale with file size** — the bigger the file, the bigger the win
(signatures grow far slower than bodies). Indexing a whole project is a one-time,
cacheable, incremental cost (~13 ms here; ~0.3 s for ~80 files).

Reproduce on **any** project:

```bash
python3 bench.py <project_root> <target_file> [more_files...]
# e.g.
python3 bench.py . bcp/signature_indexer.py
python3 bench.py ~/code/your-app src/server.py src/router.py
```

## Quickstart

```python
from bcp import SignatureIndexer, estimate_tokens

idx = SignatureIndexer()           # SQLite index in a temp cache (never your repo)
idx.index_project(".")             # walk repo → signatures (incremental by file hash)

nb   = idx.query_neighborhood("src/server.py", depth=2)   # target + 2-hop neighbors
text = idx.format_for_agent(nb)                            # markdown for the prompt

print(f"savings: {100*(1-estimate_tokens(text)/estimate_tokens(open('src/server.py').read())):.0f}%")
idx.close()
```

CLI:

```bash
bcp index .                                 # build the index
bcp map   . src/server.py                   # print the signature neighborhood
bcp find  . MyClass                         # locate a symbol

# no install needed:
python3 -m bcp map . src/server.py
```

## BCP for humans — the code planogram

Same data that feeds the agent, drawn for people. A *planogram* in a supermarket
is the diagram of which product sits on which shelf; BCP makes one for your code.

```bash
# a real SVG treemap (areas ∝ lines of code), open in any browser
bcp planogram /path/to/repo --format html > planogram.html

# or a Mermaid diagram you can paste anywhere Mermaid renders (GitHub, docs, chat)
bcp planogram /path/to/repo --format mermaid
bcp planogram /path/to/repo --format graph             # architecture tree
```

```python
from bcp import planogram_html, planogram_mermaid, scan_folders

open("planogram.html", "w").write(planogram_html("/path/to/repo"))
stats = scan_folders("/path/to/repo")   # {folder: {files, loc, types, critical}}
```

Reading the planogram:
- **aisle (folder)** — a top-level directory.
- **shelf space (area)** — lines of code; the biggest aisles dominate at a glance.
- **color** — file category (Swift/UI, Python, web, config, scripts, docs).
- **red border** — a security-critical file lives there (sandbox / auth / gate).

Pure stdlib, no deps — works on any repo, any language it recognizes. It's the
same metaphor the project is named after: retail keeps a planogram of every
product; BCP keeps a planogram of every folder, file and line.

## How it works

```
  source code ─▶ SignatureIndexer (AST / tree-sitter) ─▶ SQLite index
                                                              │
        target file ─▶ query_neighborhood(file, depth=2) ◀───┘
                                   │  (file signatures + BFS import-neighbors)
                                   ▼
                       format_for_agent() ─▶ compact markdown ─▶ prompt
```

- **Python** → stdlib `ast` (zero extra deps).
- **TS / JS / TSX / JSX** → `tree-sitter` when installed, regex fallback otherwise.
- **Swift** → lightweight regex.
- **Incremental** — unchanged files (by content hash) are skipped on re-index.

## The design lesson (and why we open-sourced it)

We first materialized the map as **static YAML, regenerated on every commit**.
Then we measured: **0 runtime readers**, ~4.3 s tax per commit, and toxic `git`
churn. We deleted it and kept the **live SQLite index queried on demand** →
the savings above, always fresh, out of version control.

**Don't commit your code index.** It's a derived, ephemeral artifact — like
`node_modules` or a `.o` file. Build it on demand; keep it out of `git`.

## Install

```bash
python3 -m pip install git+https://github.com/gab11s/bcp-code-planogram.git

# or clone locally for development:
python3 -m pip install -e .                 # core (Python only) — stdlib, no deps
python3 -m pip install -e ".[treesitter]"   # add TS/JS/TSX parsing
python3 -m pip install -e ".[dev]"          # pytest
python3 -m pytest                           # 16 tests, all local (map + planogram + CLI)
```

GitHub Actions CI runs the same install + CLI smoke test + pytest flow on push and PR.

## Roadmap

- PageRank-style ranking of neighbors (à la Aider) to fit a hard token budget.
- More languages (Go, Rust, Java) via tree-sitter grammars.
- A tiny MCP server so any MCP-capable agent can call `query_neighborhood`.

## Community

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.
- Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) in issues and discussions.
- Report vulnerabilities privately via [SECURITY.md](SECURITY.md).

## License

MIT © Brasico. Contributions welcome.
