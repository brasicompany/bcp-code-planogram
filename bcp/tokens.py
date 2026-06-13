"""Deterministic, dependency-free token estimator.

A rough ~4-characters-per-token heuristic — good enough to compare *relative*
context sizes (the bench measures a ratio, not an exact billing figure). Swap in
a real tokenizer (tiktoken, the Anthropic SDK counter) if you need exact counts.
"""
from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Estimate token count of ``text`` (~4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)
