"""BCP for humans — turn the code planogram into a picture.

The supermarket metaphor, literal: each FOLDER is an aisle, each FILE a product,
the SIZE is shelf space (lines of code), the COLOR is the category. This module
walks a repo with the stdlib and emits:

  * architecture_mermaid()  — Level 0: a flow/graph of the top folders (renders
                              in any Mermaid surface, e.g. BRACOPED chat).
  * planogram_mermaid()     — Level 1: the folder planogram as a labeled, colored
                              Mermaid graph (size + type + critical flag).
  * planogram_html()        — Level 1+: a real SVG treemap (areas ∝ LOC), for the
                              web / open-source presentation.

stdlib-only, self-contained (no project imports), so it is portable to the
open-source BCP package.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict
from typing import Dict, List, Tuple

EXCLUDED = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "bower_components",
    "dist", "build", "out", "target", "coverage", ".pytest_cache", "__pycache__",
    ".mypy_cache", ".ruff_cache", ".tox", "vendor", ".next", ".nuxt", ".ops",
    ".derivedDataDesktop", ".derivedDataDesktopRelease", ".derivedDataDesktopValidation",
    ".derivedDataDesktopValidationRelease", ".derivedDataMobile", "Build",
    "Intermediates.noindex", "Products", "logs",
}

# category -> (label, mermaid hex)
_CATS = {
    "swift":  ("Swift/UI",     "#378ADD"),
    "python": ("Python/motor", "#1D9E75"),
    "web":    ("Web",          "#D85A30"),
    "config": ("Config",       "#7F77DD"),
    "script": ("Scripts",      "#BA7517"),
    "docs":   ("Docs",         "#888780"),
    "other":  ("Outros",       "#B4B2A9"),
}


def classify(filename: str) -> str:
    f = filename.lower()
    if f.endswith(".py"):
        return "python"
    if f.endswith(".swift"):
        return "swift"
    if f.endswith((".html", ".css", ".js", ".jsx", ".ts", ".tsx")):
        return "web"
    if f.endswith((".yaml", ".yml", ".json", ".toml", ".plist")):
        return "config"
    if f.endswith((".sh", ".bash", ".zsh")):
        return "script"
    if f.endswith((".md", ".rst", ".txt")):
        return "docs"
    return "other"


def scan(root: str) -> Dict[str, Dict]:
    """Per-top-folder stats: {folder: {files, loc, types{cat:count}, critical}}."""
    stats: Dict[str, Dict] = defaultdict(lambda: {"files": 0, "loc": 0, "types": defaultdict(int), "critical": False})
    root = os.path.abspath(root)
    for cur, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED and not d.startswith(".")]
        rel = os.path.relpath(cur, root)
        bucket = rel.split(os.sep)[0] if rel != "." else "(raiz)"
        for fn in files:
            if fn.startswith("."):
                continue
            cat = classify(fn)
            if cat == "other":
                continue
            path = os.path.join(cur, fn)
            try:
                loc = sum(1 for _ in open(path, encoding="utf-8", errors="ignore"))
            except OSError:
                loc = 0
            s = stats[bucket]
            s["files"] += 1
            s["loc"] += loc
            s["types"][cat] += 1
            # "critical": only the real security chokepoints (kept tight so the
            # flag stays meaningful — not every folder lights up).
            low = fn.lower()
            if any(k in low for k in ("sandbox", "writegate", "rasputin", "sentinel", "_profile.sb")):
                s["critical"] = True
    return dict(stats)


def _dominant(types: Dict[str, int]) -> str:
    return max(types, key=types.get) if types else "other"


def _human_loc(n: int) -> str:
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


# ── Level 0: architecture / folder graph ─────────────────────────────────────
def architecture_mermaid(root: str) -> str:
    stats = scan(root)
    order = sorted(stats, key=lambda b: -stats[b]["loc"])
    lines = ["graph TD", '  REPO["📦 repositório"]']
    classdefs = set()
    for i, b in enumerate(order):
        s = stats[b]
        cat = _dominant(s["types"])
        nid = f"N{i}"
        label = f'{b}<br/>{s["files"]} arq · {_human_loc(s["loc"])}'
        lines.append(f'  REPO --> {nid}["{label}"]')
        lines.append(f"  class {nid} c{cat};")
        classdefs.add(cat)
    for cat in classdefs:
        _, hexc = _CATS[cat]
        lines.append(f"  classDef c{cat} fill:{hexc}22,stroke:{hexc},stroke-width:1px;")
    return "\n".join(lines)


# ── Level 1: the planogram (folders as colored, sized nodes) ──────────────────
def planogram_mermaid(root: str) -> str:
    stats = scan(root)
    order = sorted(stats, key=lambda b: -stats[b]["loc"])
    lines = ["graph LR"]
    classdefs = set()
    for i, b in enumerate(order):
        s = stats[b]
        cat = _dominant(s["types"])
        nid = f"P{i}"
        crit = " ⚠️" if s["critical"] else ""
        label = f'{b}{crit}<br/>{s["files"]} arq · {_human_loc(s["loc"])} linhas'
        lines.append(f'  {nid}["{label}"]')
        lines.append(f"  class {nid} c{cat};")
        classdefs.add(cat)
    for cat in classdefs:
        _, hexc = _CATS[cat]
        lines.append(f"  classDef c{cat} fill:{hexc}22,stroke:{hexc},stroke-width:1.5px;")
    return "\n".join(lines)


def legend_text() -> str:
    return " · ".join(f"{lbl}" for _, (lbl, _) in _CATS.items() if lbl != "Outros")


# ── Level 1+: a real SVG treemap (areas ∝ LOC) — for web/open-source ──────────
def _squarify(items: List[Tuple[str, int, str, bool]], x: float, y: float, w: float, h: float) -> List[Dict]:
    """Tiny slice-and-dice treemap (good enough; no deps). items: (name, value, cat, critical)."""
    total = sum(v for _, v, _, _ in items) or 1
    out: List[Dict] = []
    horizontal = w >= h
    cursor = x if horizontal else y
    for name, val, cat, crit in items:
        frac = val / total
        if horizontal:
            tw = w * frac
            out.append({"name": name, "val": val, "cat": cat, "crit": crit, "x": cursor, "y": y, "w": tw, "h": h})
            cursor += tw
        else:
            th = h * frac
            out.append({"name": name, "val": val, "cat": cat, "crit": crit, "x": x, "y": cursor, "w": w, "h": th})
            cursor += th
    return out


def planogram_html(root: str, width: int = 900, height: int = 520) -> str:
    """Self-contained HTML+SVG treemap of the repo. Open in any browser."""
    stats = scan(root)
    items = sorted(
        [(b, s["loc"] or 1, _dominant(s["types"]), s["critical"]) for b, s in stats.items()],
        key=lambda t: -t[1],
    )
    # two-row split for a treemap feel: biggest aisle on top.
    half = max(1, len(items) // 2)
    big = items[:half]
    small = items[half:]
    big_total = sum(v for _, v, _, _ in big) or 1
    small_total = sum(v for _, v, _, _ in small) or 1
    split = big_total / (big_total + small_total)
    pad = 40
    iw, ih = width - pad, height - pad - 30
    tiles = _squarify(big, pad / 2, 40, iw, ih * split) + _squarify(small, pad / 2, 40 + ih * split, iw, ih * (1 - split))

    rects = []
    for t in tiles:
        _, hexc = _CATS[t["cat"]]
        stroke = "#E24B4A" if t["crit"] else "rgba(0,0,0,.25)"
        sw = 2 if t["crit"] else 0.6
        rects.append(
            f'<g><rect x="{t["x"]:.1f}" y="{t["y"]:.1f}" width="{t["w"]:.1f}" height="{t["h"]:.1f}" '
            f'rx="4" fill="{hexc}33" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<text x="{t["x"]+8:.1f}" y="{t["y"]+22:.1f}" font-size="14" font-weight="600" fill="{hexc}">'
            f'{html.escape(t["name"])}</text>'
            f'<text x="{t["x"]+8:.1f}" y="{t["y"]+40:.1f}" font-size="11" fill="{hexc}">'
            f'{_human_loc(t["val"])} linhas</text></g>'
        )
    legend = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px">'
        f'<span style="width:11px;height:11px;border-radius:2px;background:{hexc}"></span>{lbl}</span>'
        for cat, (lbl, hexc) in _CATS.items() if lbl != "Outros"
    )
    return (
        '<!doctype html><meta charset="utf-8">'
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:'
        f'{width}px;margin:24px auto;color:#1a1a1a">'
        '<h2 style="font-weight:500;margin:0 0 4px">BCP — planograma do código</h2>'
        '<p style="color:#666;margin:0 0 12px;font-size:13px">cada corredor é uma pasta · '
        'área = linhas de código · cor = tipo · borda vermelha = arquivo crítico</p>'
        f'<div style="font-size:12px;color:#555;margin-bottom:10px">{legend}</div>'
        f'<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg">'
        f'{"".join(rects)}</svg></div>'
    )


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    mode = sys.argv[2] if len(sys.argv) > 2 else "map"
    if mode == "html":
        print(planogram_html(root))
    elif mode == "graph":
        print(architecture_mermaid(root))
    else:
        print(planogram_mermaid(root))
