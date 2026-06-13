"""Allow `python -m bcp ...` as a no-install entrypoint."""
from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
