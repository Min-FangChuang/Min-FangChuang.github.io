def apply_filters(records: list[dict], filters: dict) -> list[dict]:
    """Apply all supported query filters using intersection semantics."""
    filtered = records

    record_type = filters.get("type")
    category = filters.get("category")
    exact_date = filters.get("date")
    date_from = filters.get("from_date")
    date_to = filters.get("to_date")
    month = filters.get("month")
    keyword = filters.get("keyword")

    if record_type:
        filtered = [record for record in filtered if record["type"] == record_type]
    if category:
        filtered = [record for record in filtered if record["category"] == category]
    if exact_date:
        filtered = [record for record in filtered if record["date"] == exact_date]
    if date_from:
        filtered = [record for record in filtered if record["date"] >= date_from]
    if date_to:
        filtered = [record for record in filtered if record["date"] <= date_to]
    if month:
        filtered = [record for record in filtered if record["date"].startswith(month + "-")]
    if keyword:
        keyword_lower = keyword.lower()
        filtered = [
            record
            for record in filtered
            if keyword_lower in record["category"].lower() or keyword_lower in record.get("note", "").lower()
        ]

    return filtered
