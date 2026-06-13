"""Tests for the BCP planogram (for humans) — pure, no network."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bcp import planogram_html, planogram_mermaid, architecture_mermaid, scan_folders  # noqa: E402


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("def run():\n    return 1\n" * 10, encoding="utf-8")
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "View.swift").write_text("struct V {}\n" * 20, encoding="utf-8")
    (tmp_path / "ui" / "sandbox.swift").write_text("// security\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.py").write_text("x=1\n", encoding="utf-8")
    return tmp_path


def test_scan_groups_by_top_folder(tmp_path):
    s = scan_folders(str(_make_repo(tmp_path)))
    assert "app" in s and "ui" in s
    assert s["app"]["loc"] > 0 and s["ui"]["files"] == 2


def test_scan_skips_excluded_dirs(tmp_path):
    s = scan_folders(str(_make_repo(tmp_path)))
    assert "node_modules" not in s


def test_critical_flag_only_on_security_files(tmp_path):
    s = scan_folders(str(_make_repo(tmp_path)))
    assert s["ui"]["critical"] is True       # has sandbox.swift
    assert s["app"]["critical"] is False


def test_planogram_html_is_valid_svg(tmp_path):
    out = planogram_html(str(_make_repo(tmp_path)))
    assert out.startswith("<!doctype html>") and "<svg" in out and "planograma" in out


def test_planogram_mermaid_has_nodes_and_classdefs(tmp_path):
    out = planogram_mermaid(str(_make_repo(tmp_path)))
    assert out.startswith("graph LR")
    assert "classDef" in out and "app" in out and "ui" in out


def test_architecture_mermaid_is_a_tree(tmp_path):
    out = architecture_mermaid(str(_make_repo(tmp_path)))
    assert out.startswith("graph TD") and "REPO" in out and "-->" in out


def test_empty_repo_does_not_crash(tmp_path):
    assert "svg" in planogram_html(str(tmp_path))
    assert planogram_mermaid(str(tmp_path)).startswith("graph LR")
