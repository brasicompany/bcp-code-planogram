"""BCP CLI.

For the agent (token-efficient code map):
    bcp index <project_root>
    bcp map   <project_root> <target_file> [--depth 2]
    bcp find  <project_root> <symbol_name>

For humans (code planogram — the supermarket map of your repo):
    bcp planogram <project_root> [--format html|mermaid|graph] > out.html
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="bcp",
        description="BCP — code map for agents, planogram for humans",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="index a project into SQLite")
    p_index.add_argument("root")

    p_map = sub.add_parser("map", help="print a file's signature neighborhood (markdown)")
    p_map.add_argument("root")
    p_map.add_argument("target")
    p_map.add_argument("--depth", type=int, default=2)

    p_find = sub.add_parser("find", help="find a symbol by name")
    p_find.add_argument("root")
    p_find.add_argument("name")

    p_plan = sub.add_parser("planogram", help="render the code planogram (for humans)")
    p_plan.add_argument("root")
    p_plan.add_argument("--format", choices=["html", "mermaid", "graph"], default="html")

    args = ap.parse_args()
    root = str(Path(args.root).resolve())

    if args.cmd == "planogram":
        from bcp import architecture_mermaid, planogram_html, planogram_mermaid

        if args.format == "html":
            print(planogram_html(root))
        elif args.format == "graph":
            print(architecture_mermaid(root))
        else:
            print(planogram_mermaid(root))
        return 0

    from bcp import SignatureIndexer

    idx = SignatureIndexer()
    idx.index_project(root)
    if args.cmd == "index":
        print("indexed.")
    elif args.cmd == "map":
        target_path = Path(args.target)
        target = str((Path(args.root) / target_path) if not target_path.is_absolute() else target_path)
        print(idx.format_for_agent(idx.query_neighborhood(target, depth=args.depth)))
    elif args.cmd == "find":
        for s in idx.query_by_name(args.name):
            loc = f"{s.parent_class}." if s.parent_class else ""
            print(f"{s.file_path}:{s.lineno}  `{s.entity_type}` {loc}{s.name}")
    idx.close()
    return 0
