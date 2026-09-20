import argparse
from typing import NoReturn

from services import ExpenseTrackerService, InputError


class CLIArgumentError(InputError):
    """Argument parsing error mapped to the input-error exit code."""

    pass


class Parser(argparse.ArgumentParser):
    """Argument parser that raises exceptions instead of exiting directly."""

    def error(self, message: str) -> NoReturn:
        usage = self.format_usage().strip()
        raise CLIArgumentError(f"{message}\n{usage}")


def build_parser() -> Parser:
    """Construct the CLI parser for all supported commands."""
    parser = Parser(prog="python main.py", description="Expense Tracker CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--type")
    add_parser.add_argument("--amount", required=True)
    add_parser.add_argument("--category", required=True)
    add_parser.add_argument("--date")
    add_parser.add_argument("--note")

    list_parser = subparsers.add_parser("list")
    _add_filter_arguments(list_parser)

    summary_parser = subparsers.add_parser("summary")
    _add_filter_arguments(summary_parser)

    edit_parser = subparsers.add_parser("edit")
    edit_parser.add_argument("--id", required=True)
    edit_parser.add_argument("--date")
    edit_parser.add_argument("--type")
    edit_parser.add_argument("--category")
    edit_parser.add_argument("--amount")
    edit_parser.add_argument("--note")

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("--id", required=True)

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--format", required=True)
    export_parser.add_argument("--output")
    _add_filter_arguments(export_parser)

    category_parser = subparsers.add_parser("category")
    category_group = category_parser.add_mutually_exclusive_group(required=True)
    category_group.add_argument("--list", action="store_true", dest="list_categories")
    category_group.add_argument("--add")
    category_group.add_argument("--delete")

    return parser


def _add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach shared filter arguments to a subcommand parser."""
    parser.add_argument("--type")
    parser.add_argument("--category")
    parser.add_argument("--date")
    parser.add_argument("--from", dest="from_date")
    parser.add_argument("--to", dest="to_date")
    parser.add_argument("--month")
    parser.add_argument("--keyword")


def run(argv: list[str] | None = None) -> str:
    """Parse CLI arguments and dispatch to the service layer."""
    parser = build_parser()
    args = parser.parse_args(argv)
    service = ExpenseTrackerService()

    if args.command == "add":
        message, details = service.add_record(args.type, args.amount, args.category, args.date, args.note)
        return f"{message}\n{details}"

    if args.command == "list":
        return service.list_records(_filter_args(args))

    if args.command == "summary":
        return service.summary_records(_filter_args(args))

    if args.command == "edit":
        updates = {
            key: value
            for key, value in {
                "date": args.date,
                "type": args.type,
                "category": args.category,
                "amount": args.amount,
                "note": args.note,
            }.items()
            if value is not None
        }
        message, details = service.edit_record(args.id, updates)
        return f"{message}\n{details}"

    if args.command == "delete":
        message, details = service.delete_record(args.id)
        return f"{message}\n{details}"

    if args.command == "export":
        return service.export_records(args.format, args.output, _filter_args(args))

    if args.command == "category":
        if args.list_categories:
            return service.list_categories()
        if args.add is not None:
            return service.add_category(args.add)
        if args.delete is not None:
            return service.delete_category(args.delete)

    raise CLIArgumentError("Unknown command.")


def _filter_args(args: argparse.Namespace) -> dict:
    """Extract shared filter arguments from parsed CLI namespace."""
    return {
        "type": args.type,
        "category": args.category,
        "date": args.date,
        "from_date": args.from_date,
        "to_date": args.to_date,
        "month": args.month,
        "keyword": args.keyword,
    }
