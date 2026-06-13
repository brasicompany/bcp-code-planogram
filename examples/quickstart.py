#!/usr/bin/env python3
"""Minimal end-to-end example: index this repo, map a file, print the savings.

    python examples/quickstart.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bcp import SignatureIndexer, estimate_tokens

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "bcp" / "signature_indexer.py"

idx = SignatureIndexer()
n = idx.index_project(str(ROOT))
print(f"indexed {n} files")

neighborhood = idx.query_neighborhood(str(TARGET), depth=2)
context = idx.format_for_agent(neighborhood, max_lines=1800)

raw = estimate_tokens(TARGET.read_text())
lean = estimate_tokens(context)
print(f"raw file : ~{raw:,} tokens")
print(f"BCP map  : ~{lean:,} tokens   ({100*(1-lean/raw):.0f}% smaller)")
print("\n--- what the agent actually sees (truncated) ---")
print(context[:800])
idx.close()
