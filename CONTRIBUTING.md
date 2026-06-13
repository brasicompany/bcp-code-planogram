# Contributing to BCP

Thanks for contributing.

BCP is intentionally small, local-first, and evidence-driven. Changes are more
likely to be accepted when they preserve those properties.

## Ground rules

- Keep the core stdlib-first unless an optional dependency unlocks clear value.
- Do not commit generated indexes, caches, or derived artifacts.
- Keep tests local and deterministic. No network calls in the test suite.
- If you change benchmark claims in the docs, rerun `bench.py` and update the
  numbers in the same PR.
- Prefer small, reviewable pull requests over large rewrites.

## Development setup

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
python3 -m bcp --help
python3 bench.py . bcp/signature_indexer.py
```

Optional TypeScript/JavaScript parsing support:

```bash
python3 -m pip install -e ".[treesitter]"
```

## Pull requests

For substantial changes, open an issue first so the direction is explicit.

Every PR should include:

- a short problem statement
- the behavior change
- tests or a reason tests are not needed
- updated docs when user-facing behavior changes

## Style

- Default to ASCII unless the file already uses Unicode.
- Keep public copy precise. Avoid inflated claims.
- Preserve the current design principle: give the model shape, not bodies.
