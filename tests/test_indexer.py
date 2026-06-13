"""Tests for the BCP SignatureIndexer (pure, no network)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bcp import SignatureIndexer, estimate_tokens  # noqa: E402


SAMPLE = '''
"""module docstring"""
import os
from pathlib import Path


def top_level(a, b):
    """adds two numbers"""
    return a + b


class Widget:
    """a widget"""

    def render(self, theme):
        return theme


async def fetch(url):
    return url
'''


def _project(tmp_path: Path) -> SignatureIndexer:
    (tmp_path / "mod.py").write_text(SAMPLE, encoding="utf-8")
    idx = SignatureIndexer(db_path=str(tmp_path / "idx.db"))
    idx.index_project(str(tmp_path))
    return idx


def test_index_extracts_python_entities(tmp_path):
    idx = _project(tmp_path)
    nb = idx.query_neighborhood(str(tmp_path / "mod.py"), depth=1)
    names = {s.name for sigs in nb.values() for s in sigs}
    assert "top_level" in names
    assert "Widget" in names
    assert "render" in names           # method
    assert "fetch" in names            # async function
    idx.close()


def test_method_carries_parent_class(tmp_path):
    idx = _project(tmp_path)
    nb = idx.query_neighborhood(str(tmp_path / "mod.py"), depth=1)
    methods = [s for sigs in nb.values() for s in sigs if s.entity_type == "method"]
    assert any(m.name == "render" and m.parent_class == "Widget" for m in methods)
    idx.close()


def test_format_for_agent_is_markdown(tmp_path):
    idx = _project(tmp_path)
    text = idx.format_for_agent(idx.query_neighborhood(str(tmp_path / "mod.py"), depth=1))
    assert "### " in text and "`function`" in text and "**top_level**" in text
    idx.close()


def test_incremental_skip_unchanged(tmp_path):
    idx = _project(tmp_path)
    second = idx.index_project(str(tmp_path))   # nothing changed
    assert second == 0
    idx.close()


def test_map_beats_raw_on_a_large_file(tmp_path):
    # The win shows up on real files: many functions with bodies. The map keeps
    # only signatures, so it grows far slower than the source. (On tiny files the
    # markdown overhead can exceed the file — that's expected and not the use case.)
    big = "\n\n".join(
        f'def fn_{i}(arg_a, arg_b, arg_c):\n'
        f'    """does work number {i}"""\n'
        + "\n".join(f"    x{j} = arg_a + arg_b * {j}  # filler body line" for j in range(20))
        + f"\n    return x0 + {i}"
        for i in range(60)
    )
    (tmp_path / "big.py").write_text(big, encoding="utf-8")
    idx = SignatureIndexer(db_path=str(tmp_path / "idx.db"))
    idx.index_project(str(tmp_path))
    raw = estimate_tokens(big)
    mapped = estimate_tokens(idx.format_for_agent(idx.query_neighborhood(str(tmp_path / "big.py"), depth=1)))
    assert mapped < raw * 0.5     # at least 50% savings on a realistically-sized file
    idx.close()


def test_query_by_name(tmp_path):
    idx = _project(tmp_path)
    hits = idx.query_by_name("Widget")
    assert any(h.name == "Widget" for h in hits)
    idx.close()


def test_excluded_dirs_are_skipped(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.py").write_text("def should_not_index(): pass", encoding="utf-8")
    (tmp_path / "real.py").write_text("def real_fn(): pass", encoding="utf-8")
    idx = SignatureIndexer(db_path=str(tmp_path / "idx.db"))
    idx.index_project(str(tmp_path))
    assert not idx.query_by_name("should_not_index")
    assert idx.query_by_name("real_fn")
    idx.close()
