#!/usr/bin/env python3
"""Compatibility wrapper for local development.

Prefer `bcp ...` after installation or `python -m bcp ...` without installation.
"""
from bcp.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
