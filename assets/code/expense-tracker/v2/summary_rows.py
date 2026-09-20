from collections import defaultdict

from models import QuerySummary, SummaryRow


def build_summary_rows(records: list[dict], summary: QuerySummary) -> list[SummaryRow]:
    """Group filtered records by category and type for summary output."""
    grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"count": 0, "total": 0})

    for record in records:
        key = (record["category"], record["type"])
        grouped[key]["count"] += 1
        grouped[key]["total"] += record["amount"]

    rows: list[SummaryRow] = []
    for (category, record_type), values in grouped.items():
        percentage = "-"
        if record_type == "expense":
            if summary.total_expense == 0:
                percentage = "0%"
            else:
                percentage = f"{(values['total'] / summary.total_expense) * 100:.2f}%"
        rows.append(
            SummaryRow(
                category=category,
                type=record_type,
                count=values["count"],
                total=values["total"],
                percentage=percentage,
            )
        )

    return sorted(rows, key=lambda row: (-row.total, row.category, row.type))
