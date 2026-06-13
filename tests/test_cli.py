"""CLI smoke tests for installed and module entrypoints."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_python_module_help_runs():
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "bcp", "--help"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "planogram" in result.stdout


def test_python_module_map_outputs_signatures(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("def hello(name):\n    return name\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "bcp", "map", str(tmp_path), "sample.py", "--depth", "1"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "**hello**" in result.stdout
