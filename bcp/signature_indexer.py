"""SignatureIndexer — an AST-based, queryable code map for LLM agents.

Give your coding agent a *map*, not the whole library. Instead of pasting raw
files into the prompt, extract only the signatures (functions, classes, methods,
types, imports) of the target file and its import-neighborhood, persisted in a
fast SQLite index.

- Python: parsed via the stdlib ``ast`` (zero extra deps).
- TS/JS/TSX/JSX: parsed via ``tree-sitter`` when installed, regex fallback otherwise.
- Swift: lightweight regex extraction.

Public API:
    idx = SignatureIndexer()                 # or SignatureIndexer(db_path=..., excluded_dirs=...)
    idx.index_project(".")                    # walk repo -> SQLite (incremental by file hash)
    nb = idx.query_neighborhood("a.py", 2)    # target + BFS import-neighbors
    text = idx.format_for_agent(nb)           # markdown ready for a prompt
    idx.close()

MIT-licensed. Originally extracted from BRACOPED (Brasico).
"""
from __future__ import annotations

import ast
import hashlib
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:  # Optional multi-language parser; a regex fallback stays available.
    from tree_sitter import Language, Parser
    import tree_sitter_javascript
    import tree_sitter_typescript
except Exception:  # pragma: no cover
    Language = None  # type: ignore[assignment]
    Parser = None  # type: ignore[assignment]
    tree_sitter_javascript = None  # type: ignore[assignment]
    tree_sitter_typescript = None  # type: ignore[assignment]


DEFAULT_EXTENSIONS: Tuple[str, ...] = (".py", ".ts", ".tsx", ".js", ".jsx", ".swift")
DEFAULT_EXCLUDED_DIRS: Set[str] = {
    ".git", ".hg", ".svn",
    ".venv", "venv", "env",
    "node_modules", "bower_components",
    "dist", "build", "out", "target",
    "coverage", ".pytest_cache", "__pycache__",
    ".mypy_cache", ".ruff_cache", ".tox",
    "vendor", ".next", ".nuxt",
}


@dataclass
class Signature:
    """One extracted code entity."""
    file_path: str
    entity_type: str  # function | class | method | import | interface | type_alias | struct | ...
    name: str
    lineno: int
    col_offset: int
    docstring: Optional[str] = None
    parent_class: Optional[str] = None
    parameters: str = ""
    file_hash: str = ""


class SignatureIndexer:
    """Index project signatures in SQLite and query neighborhoods efficiently."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        excluded_dirs: Optional[Set[str]] = None,
    ) -> None:
        # Default DB lives in a local cache dir, NOT the working tree — the index
        # is a derived, ephemeral artifact (never commit it).
        if db_path is None:
            cache = Path(tempfile.gettempdir()) / "bcp_cache"
            cache.mkdir(parents=True, exist_ok=True)
            db_path = str(cache / "signatures.db")
        self.db_path = db_path
        self.excluded_dirs = set(excluded_dirs) if excluded_dirs is not None else set(DEFAULT_EXCLUDED_DIRS)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._init_schema()
        self._parsers: Dict[str, Any] = {}

    # ── schema ────────────────────────────────────────────────────────────────
    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                lineno INTEGER NOT NULL,
                col_offset INTEGER NOT NULL,
                docstring TEXT,
                parent_class TEXT,
                parameters TEXT,
                file_hash TEXT,
                UNIQUE(file_path, entity_type, name, lineno)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS file_metadata (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sig_file ON signatures(file_path)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sig_name ON signatures(name)")
        self.conn.commit()

    # ── hashing / exclusion ─────────────────────────────────────────────────────
    def _file_hash(self, file_path: str) -> str:
        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except OSError:
            return ""

    def _is_excluded(self, path: Path) -> bool:
        return bool(set(path.parts) & self.excluded_dirs)

    # ── Python (stdlib ast) ─────────────────────────────────────────────────────
    def _extract_python(self, file_path: str) -> List[Signature]:
        sigs: List[Signature] = []
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError, OSError):
            return sigs

        def add(entity_type: str, name: str, node: ast.AST, *, parent: Optional[str] = None, params: str = "", doc: str = "") -> None:
            sigs.append(Signature(
                file_path=file_path, entity_type=entity_type, name=name,
                lineno=getattr(node, "lineno", 0), col_offset=getattr(node, "col_offset", 0),
                docstring=(doc or "")[:200], parent_class=parent, parameters=params,
            ))

        class V(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                params = ", ".join(a.arg for a in node.args.args[:4])
                add("function", node.name, node, params=params, doc=ast.get_docstring(node) or "")
                self.generic_visit(node)

            visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                add("class", node.name, node, doc=ast.get_docstring(node) or "")
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        params = ", ".join(a.arg for a in child.args.args[1:5])  # skip self
                        add("method", child.name, child, parent=node.name, params=params)
                self.generic_visit(node)

            def visit_Import(self, node: ast.Import) -> None:
                for alias in node.names:
                    add("import", alias.name, node)

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                for alias in node.names:
                    add("import", f"from {node.module} import {alias.name}", node)

        V().visit(tree)
        return sigs

    # ── TS / JS (tree-sitter, regex fallback) ───────────────────────────────────
    def _language(self, suffix: str) -> Optional[Any]:
        if Parser is None or Language is None:
            return None
        try:
            if suffix == ".tsx":
                return Language(tree_sitter_typescript.language_tsx())
            if suffix == ".ts":
                return Language(tree_sitter_typescript.language_typescript())
            if suffix in {".js", ".jsx"}:
                return Language(tree_sitter_javascript.language())
        except Exception:
            return None
        return None

    def _parser(self, suffix: str) -> Optional[Any]:
        if suffix in self._parsers:
            return self._parsers[suffix]
        lang = self._language(suffix)
        if lang is None or Parser is None:
            return None
        p = Parser()
        p.language = lang
        self._parsers[suffix] = p
        return p

    def _node_text(self, content: bytes, node: Any, max_chars: int = 200) -> str:
        try:
            raw = content[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
        except Exception:
            return ""
        clean = " ".join(raw.strip().split())
        return (clean[:max_chars].rsplit(" ", 1)[0] + "...") if len(clean) > max_chars else clean

    def _node_name(self, content: bytes, node: Any) -> str:
        try:
            nn = node.child_by_field_name("name")
        except Exception:
            nn = None
        if nn is not None:
            return self._node_text(content, nn, 120)
        for child in getattr(node, "children", []):
            if child.type in {"identifier", "type_identifier", "property_identifier"}:
                return self._node_text(content, child, 120)
        return ""

    def _extract_ts_js(self, file_path: str) -> List[Signature]:
        suffix = Path(file_path).suffix.lower()
        parser = self._parser(suffix)
        if parser is None:
            return self._extract_ts_js_regex(file_path)
        try:
            content = Path(file_path).read_bytes()
            tree = parser.parse(content)
        except Exception:
            return self._extract_ts_js_regex(file_path)

        sigs: List[Signature] = []
        seen: Set[Tuple[str, str, int]] = set()

        def add(entity_type: str, name: str, node: Any, parent: Optional[str] = None) -> None:
            if not name:
                return
            row, col = node.start_point
            key = (entity_type, name, int(row) + 1)
            if key in seen:
                return
            seen.add(key)
            sigs.append(Signature(file_path=file_path, entity_type=entity_type, name=name,
                                  lineno=int(row) + 1, col_offset=int(col), parent_class=parent))

        def walk(node: Any, parent: Optional[str] = None) -> None:
            t = node.type
            if t == "import_statement":
                add("import", self._node_text(content, node), node)
            elif t == "function_declaration":
                add("function", self._node_name(content, node), node, parent)
            elif t == "class_declaration":
                name = self._node_name(content, node)
                add("class", name, node)
                parent = name or parent
            elif t == "method_definition":
                add("method", self._node_name(content, node), node, parent)
            elif t == "interface_declaration":
                add("interface", self._node_name(content, node), node)
            elif t == "type_alias_declaration":
                add("type_alias", self._node_name(content, node), node)
            for child in getattr(node, "children", []):
                walk(child, parent)

        walk(tree.root_node)
        return sigs or self._extract_ts_js_regex(file_path)

    def _extract_ts_js_regex(self, file_path: str) -> List[Signature]:
        sigs: List[Signature] = []
        try:
            lines = Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return sigs
        patterns = [
            ("import", re.compile(r"^\s*import\s+(.+)$")),
            ("function", re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")),
            ("class", re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")),
            ("interface", re.compile(r"\binterface\s+([A-Za-z_$][\w$]*)")),
            ("type_alias", re.compile(r"\btype\s+([A-Za-z_$][\w$]*)\s*=")),
            ("component", re.compile(r"\b(?:const|let|var)\s+([A-Z][A-Za-z0-9_$]*)\s*=")),
        ]
        for lineno, line in enumerate(lines, start=1):
            for entity_type, pattern in patterns:
                m = pattern.search(line)
                if m:
                    sigs.append(Signature(file_path=file_path, entity_type=entity_type,
                                          name=m.group(1).strip()[:160], lineno=lineno,
                                          col_offset=max(0, m.start(1)), docstring=line.strip()[:200]))
        return sigs

    # ── Swift (regex) ────────────────────────────────────────────────────────────
    def _extract_swift(self, file_path: str) -> List[Signature]:
        sigs: List[Signature] = []
        try:
            lines = Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return sigs
        patterns = [
            ("import", re.compile(r"^\s*import\s+([A-Za-z0-9_]+)")),
            ("class", re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("struct", re.compile(r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("protocol", re.compile(r"\bprotocol\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("function", re.compile(r"\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")),
        ]
        for lineno, line in enumerate(lines, start=1):
            for entity_type, pattern in patterns:
                m = pattern.search(line)
                if m:
                    sigs.append(Signature(file_path=file_path, entity_type=entity_type, name=m.group(1),
                                          lineno=lineno, col_offset=max(0, m.start(1)), docstring=line.strip()[:200]))
        return sigs

    def _extract(self, file_path: str) -> List[Signature]:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".py":
            return self._extract_python(file_path)
        if suffix in {".ts", ".tsx", ".js", ".jsx"}:
            return self._extract_ts_js(file_path)
        if suffix == ".swift":
            return self._extract_swift(file_path)
        return []

    # ── indexing ─────────────────────────────────────────────────────────────────
    def index_project(self, root_path: str, extensions: Tuple[str, ...] = DEFAULT_EXTENSIONS) -> int:
        """Walk the project and (re)index changed files. Returns #files indexed."""
        root = Path(root_path)
        indexed = 0
        cur = self.conn.cursor()
        for src in root.rglob("*"):
            if not src.is_file() or src.suffix.lower() not in extensions or self._is_excluded(src):
                continue
            fp = str(src)
            fh = self._file_hash(fp)
            cur.execute("SELECT file_hash FROM file_metadata WHERE file_path = ?", (fp,))
            row = cur.fetchone()
            if row and row[0] == fh:
                continue  # unchanged → incremental skip
            cur.execute("DELETE FROM signatures WHERE file_path = ?", (fp,))
            for sig in self._extract(fp):
                sig.file_hash = fh
                cur.execute(
                    """INSERT OR REPLACE INTO signatures
                       (file_path, entity_type, name, lineno, col_offset, docstring, parent_class, parameters, file_hash)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (sig.file_path, sig.entity_type, sig.name, sig.lineno, sig.col_offset,
                     sig.docstring, sig.parent_class, sig.parameters, sig.file_hash),
                )
            cur.execute("INSERT OR REPLACE INTO file_metadata (file_path, file_hash) VALUES (?,?)", (fp, fh))
            indexed += 1
        self.conn.commit()
        return indexed

    # ── query ────────────────────────────────────────────────────────────────────
    def _path_variants(self, file_path: str) -> List[str]:
        variants = [file_path]
        raw = Path(file_path)
        for cand in (raw, Path.cwd() / raw):
            try:
                variants.append(str(cand.resolve()))
            except Exception:
                pass
        return list(dict.fromkeys(variants))

    def query_neighborhood(self, file_path: str, depth: int = 2) -> Dict[str, List[Signature]]:
        """Return the target file's signatures plus its import-neighborhood (BFS)."""
        neighborhood: Dict[str, List[Signature]] = {}
        visited: Set[str] = set()
        queue: List[Tuple[str, int]] = [(file_path, 0)]
        cur = self.conn.cursor()

        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)

            variants = self._path_variants(current)
            placeholders = ",".join("?" for _ in variants)
            cur.execute(
                f"""SELECT entity_type, name, lineno, col_offset, docstring, parent_class, parameters
                    FROM signatures WHERE file_path IN ({placeholders}) ORDER BY lineno""",
                tuple(variants),
            )
            rows = cur.fetchall()
            if not rows:
                cur.execute(
                    """SELECT entity_type, name, lineno, col_offset, docstring, parent_class, parameters
                       FROM signatures WHERE file_path LIKE ? ORDER BY lineno""",
                    (f"%{current}",),
                )
                rows = cur.fetchall()

            neighborhood[current] = [
                Signature(file_path=current, entity_type=r[0], name=r[1], lineno=r[2],
                          col_offset=r[3], docstring=r[4], parent_class=r[5], parameters=r[6])
                for r in rows
            ]

            # forward imports → enqueue neighbors
            cur.execute("SELECT DISTINCT name FROM signatures WHERE file_path LIKE ? AND entity_type='import'", (f"%{current}",))
            for (imp,) in cur.fetchall():
                module = imp.split()[1] if imp.startswith("from ") else imp.split()[0]
                module = module.split(".")[-1]
                cur.execute("SELECT DISTINCT file_path FROM signatures WHERE file_path LIKE ?", (f"%/{module}.py",))
                for (neighbor,) in cur.fetchall():
                    if neighbor not in visited:
                        queue.append((neighbor, d + 1))
        return neighborhood

    def query_by_name(self, name: str) -> List[Signature]:
        cur = self.conn.cursor()
        cur.execute(
            """SELECT file_path, entity_type, name, lineno, col_offset, docstring, parent_class, parameters
               FROM signatures WHERE name LIKE ? OR parent_class LIKE ? ORDER BY file_path, lineno""",
            (f"%{name}%", f"%{name}%"),
        )
        return [
            Signature(file_path=r[0], entity_type=r[1], name=r[2], lineno=r[3], col_offset=r[4],
                      docstring=r[5], parent_class=r[6], parameters=r[7])
            for r in cur.fetchall()
        ]

    # ── formatting ───────────────────────────────────────────────────────────────
    def format_for_agent(self, neighborhood: Dict[str, List[Signature]], max_lines: int = 2000) -> str:
        """Render a neighborhood as compact markdown ready to drop into a prompt."""
        out: List[str] = []
        total = 0
        for file_path in sorted(neighborhood):
            sigs = neighborhood[file_path]
            if not sigs:
                continue
            out.append(f"\n### {file_path}")
            for sig in sigs:
                head = f"  - `{sig.entity_type}` **{sig.parent_class + '.' if sig.parent_class else ''}{sig.name}**"
                if sig.parameters:
                    head += f"({sig.parameters})"
                head += f" (line {sig.lineno})"
                out.append(head)
                if sig.docstring:
                    out.append(f"    > {sig.docstring[:100]}")
                total += 2
                if total > max_lines:
                    out.append("\n... (truncated)")
                    return "\n".join(out)
        return "\n".join(out)

    def close(self) -> None:
        self.conn.close()
