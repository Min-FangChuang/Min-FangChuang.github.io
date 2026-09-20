from models import QuerySummary, SummaryRow


FIELD_ORDER = ["id", "date", "type", "category", "amount", "note"]
HEADERS = {
    "id": "ID",
    "date": "Date",
    "type": "Type",
    "category": "Category",
    "amount": "Amount",
    "note": "Note",
}
SUMMARY_HEADERS = {
    "category": "Category",
    "type": "Type",
    "count": "Count",
    "total": "Total",
    "percentage": "Percentage",
}


def format_record_table(records: list[dict], summary: QuerySummary) -> str:
    """Render filtered records as a table followed by a summary block."""
    widths = _column_widths(records, FIELD_ORDER, HEADERS)
    lines = [_format_table_header(FIELD_ORDER, HEADERS, widths)]

    for record in records:
        lines.append(_format_table_row(record, FIELD_ORDER, widths))

    lines.append("")
    lines.append("-" * max(len(lines[0]), 47))
    lines.extend(_format_summary_lines(summary))
    return "\n".join(lines)


def format_summary_table(rows: list[SummaryRow], summary: QuerySummary) -> str:
    """Render grouped summary rows and global totals."""
    row_dicts = [row.to_dict() for row in rows]
    fields = ["category", "type", "count", "total", "percentage"]
    widths = _column_widths(row_dicts, fields, SUMMARY_HEADERS)
    lines = [_format_table_header(fields, SUMMARY_HEADERS, widths)]

    for row in row_dicts:
        lines.append(_format_table_row(row, fields, widths))

    lines.append("")
    lines.extend(_format_summary_lines(summary)[1:])
    return "\n".join(lines)


def format_single_record(record: dict) -> str:
    """Render one record as field-per-line details."""
    return "\n".join(f"{HEADERS[field]}: {record.get(field, '')}" for field in FIELD_ORDER)


def format_category_list(categories: list[str]) -> str:
    """Render the allowed category list for CLI output."""
    lines = ["Available categories:"]
    lines.extend(f"- {category}" for category in categories)
    return "\n".join(lines)


def _column_widths(records: list[dict], fields: list[str], headers: dict[str, str]) -> dict[str, int]:
    """Calculate display widths for each table column."""
    widths: dict[str, int] = {}
    for field in fields:
        values = [str(record.get(field, "")) for record in records]
        lengths = [len(headers[field]), *(len(value) for value in values)]
        widths[field] = max(lengths)
    return widths


def _format_table_header(fields: list[str], headers: dict[str, str], widths: dict[str, int]) -> str:
    """Format a single header row."""
    return "  ".join(headers[field].ljust(widths[field]) for field in fields)


def _format_table_row(record: dict, fields: list[str], widths: dict[str, int]) -> str:
    """Format one table row using precomputed widths."""
    return "  ".join(str(record.get(field, "")).ljust(widths[field]) for field in fields)


def _format_summary_lines(summary: QuerySummary) -> list[str]:
    """Format the shared summary lines for list and summary outputs."""
    return [
        f"Count:          {summary.count}",
        f"Total Income:   {summary.total_income}",
        f"Total Expense:  {summary.total_expense}",
        f"Net:            {summary.net}",
    ]
