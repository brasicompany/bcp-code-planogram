#!/usr/bin/env python3
"""BCP telemetry bench — measure context tokens WITH vs WITHOUT the code map.

WITHOUT BCP : feed the raw target file(s) to the model.
WITH BCP    : feed only the SignatureIndexer neighborhood (signatures + 2-hop
              import neighbors).

Usage:
    python bench.py <project_root> <target_file> [<target_file> ...] [--depth 2]

Example:
    python bench.py . bcp/signature_indexer.py
    python bench.py ~/code/fastapi fastapi/applications.py fastapi/routing.py
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from bcp import SignatureIndexer, estimate_tokens


def main() -> int:
    ap = argparse.ArgumentParser(description="BCP telemetry: raw files vs signature map")
    ap.add_argument("project_root")
    ap.add_argument("targets", nargs="+", help="target file(s), relative to project_root or absolute")
    ap.add_argument("--depth", type=int, default=2, help="import-neighborhood BFS depth (default 2)")
    ap.add_argument("--db", default=None, help="optional SQLite index path (default: temp cache)")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    targets = [str((root / t) if not Path(t).is_absolute() else Path(t)) for t in args.targets]

    # WITHOUT BCP: raw target files
    raw_tokens = 0
    for t in targets:
        try:
            raw_tokens += estimate_tokens(Path(t).read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            print(f"  ! could not read {t}")

    # WITH BCP: index once, then query each target's neighborhood
    idx = SignatureIndexer(db_path=args.db)
    t0 = time.perf_counter()
    n_files = idx.index_project(str(root))
    index_ms = (time.perf_counter() - t0) * 1000

    map_tokens = 0
    for t in targets:
        nb = idx.query_neighborhood(t, depth=args.depth)
        map_tokens += estimate_tokens(idx.format_for_agent(nb, max_lines=1800))
    idx.close()

    saving = (1 - map_tokens / raw_tokens) * 100 if raw_tokens else 0.0

    print("=" * 60)
    print("BCP telemetry — context tokens to understand the target(s)")
    print("=" * 60)
    print(f"  targets            : {len(targets)} file(s)")
    print(f"  indexed            : {n_files} files in {index_ms:.0f} ms (cacheable, incremental)")
    print(f"  WITHOUT BCP (raw)  : ~{raw_tokens:,} tokens")
    print(f"  WITH BCP (map)     : ~{map_tokens:,} tokens")
    print(f"  >>> savings        : {saving:.0f}%")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
