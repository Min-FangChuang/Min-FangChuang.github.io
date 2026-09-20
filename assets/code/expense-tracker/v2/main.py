import sys

from cli import run
from services import AppError


def main() -> int:
    """Run the CLI and translate application errors into exit codes."""
    try:
        output = run()
    except AppError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
