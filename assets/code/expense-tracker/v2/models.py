from dataclasses import asdict, dataclass


@dataclass
class Item:
    """A single expense or income record."""

    id: int
    date: str
    type: str
    category: str
    amount: int
    note: str = ""

    def to_dict(self) -> dict:
        """Convert the record into a JSON-serializable dictionary."""
        return asdict(self)


@dataclass
class QuerySummary:
    """Aggregate totals for a filtered query result."""

    count: int
    total_income: int
    total_expense: int
    net: int


@dataclass
class SummaryRow:
    """A grouped summary row for one category/type pair."""

    category: str
    type: str
    count: int
    total: int
    percentage: str

    def to_dict(self) -> dict:
        """Convert the grouped row into a dictionary for formatting."""
        return asdict(self)


def item_from_dict(data: dict) -> Item:
    """Build an Item from stored dictionary data."""
    return Item(
        id=int(data["id"]),
        date=str(data["date"]),
        type=str(data["type"]),
        category=str(data["category"]),
        amount=int(data["amount"]),
        note=str(data.get("note", "")),
    )
