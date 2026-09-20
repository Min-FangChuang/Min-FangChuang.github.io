from models import QuerySummary


def build_query_summary(records: list[dict]) -> QuerySummary:
    """Compute query-level totals from filtered records."""
    total_income = sum(record["amount"] for record in records if record["type"] == "income")
    total_expense = sum(record["amount"] for record in records if record["type"] == "expense")
    return QuerySummary(
        count=len(records),
        total_income=total_income,
        total_expense=total_expense,
        net=total_income - total_expense,
    )
