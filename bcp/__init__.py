"""BCP — a token-efficient code map for LLM agents, plus a code planogram for humans.

    from bcp import SignatureIndexer, estimate_tokens          # for the agent
    from bcp import planogram_html, planogram_mermaid          # for humans
"""
from .signature_indexer import Signature, SignatureIndexer
from .tokens import estimate_tokens
from .planogram import (
    architecture_mermaid,
    planogram_html,
    planogram_mermaid,
    scan as scan_folders,
)

__all__ = [
    "SignatureIndexer",
    "Signature",
    "estimate_tokens",
    "planogram_html",
    "planogram_mermaid",
    "architecture_mermaid",
    "scan_folders",
]
__version__ = "0.1.0"
