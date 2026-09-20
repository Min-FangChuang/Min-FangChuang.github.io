from datetime import date

from exporter import export_csv, export_json
from filters import apply_filters
from formatter import format_category_list, format_record_table, format_single_record, format_summary_table
from models import Item, item_from_dict
from query_summary import build_query_summary
from storage import Storage, StorageError
from summary_rows import build_summary_rows
from validators import (
    ValidationError,
    ensure_category_exists,
    ensure_category_not_exists,
    normalize_note,
    validate_category_allowed,
    validate_category_name,
    validate_date,
    validate_export_format,
    validate_month,
    validate_positive_int,
    validate_type,
)


class AppError(RuntimeError):
    """Base application error with process exit code semantics."""

    exit_code = 1


class InputError(AppError):
    """Application error for invalid user input."""

    exit_code = 2


def _validated_filters(filters: dict) -> dict:
    """Validate and normalize shared filter arguments."""
    validated = {}

    if filters.get("type") is not None:
        validated["type"] = validate_type(filters["type"])
    if filters.get("category") is not None:
        validated["category"] = validate_category_name(filters["category"])
    if filters.get("date") is not None:
        validated["date"] = validate_date(filters["date"])
    if filters.get("from_date") is not None:
        validated["from_date"] = validate_date(filters["from_date"])
    if filters.get("to_date") is not None:
        validated["to_date"] = validate_date(filters["to_date"])
    if filters.get("month") is not None:
        validated["month"] = validate_month(filters["month"])
    if filters.get("keyword") is not None:
        validated["keyword"] = str(filters["keyword"])

    return validated


class ExpenseTrackerService:
    """Coordinate validation, storage, formatting, and export workflows."""

    def __init__(self, storage: Storage | None = None) -> None:
        self.storage = storage or Storage()

    def add_record(self, record_type: str | None, amount, category: str, record_date: str | None, note: str | None) -> tuple[str, str]:
        """Validate and insert a new record."""
        data = self._load_data()
        categories = self._sorted_categories(data)

        try:
            validated_record = Item(
                id=0,
                date=validate_date(record_date) if record_date else date.today().isoformat(),
                type=validate_type(record_type or "expense"),
                category=validate_category_allowed(category, categories),
                amount=validate_positive_int(amount, "amount"),
                note=normalize_note(note),
            )
        except ValidationError as exc:
            raise InputError(str(exc)) from exc

        validated_record.id = int(data["next_id"])
        data["records"].append(validated_record.to_dict())
        data["next_id"] = validated_record.id + 1
        self._save_data(data)

        return "Record added successfully.", format_single_record(validated_record.to_dict())

    def list_records(self, filters: dict) -> str:
        """Return the filtered record table with summary totals."""
        filtered = self._filtered_records(filters)
        summary = build_query_summary(filtered)
        return format_record_table(filtered, summary)

    def summary_records(self, filters: dict) -> str:
        """Return grouped summary output for filtered records."""
        filtered = self._filtered_records(filters)
        summary = build_query_summary(filtered)
        rows = build_summary_rows(filtered, summary)
        return format_summary_table(rows, summary)

    def edit_record(self, record_id, updates: dict) -> tuple[str, str]:
        """Update selected fields on an existing record."""
        try:
            validated_id = validate_positive_int(record_id, "id")
        except ValidationError as exc:
            raise InputError(str(exc)) from exc

        if not updates:
            raise InputError("Edit requires at least one field to update.")

        data = self._load_data()
        categories = self._sorted_categories(data)

        try:
            validated_updates = self._validate_updates(updates, categories)
        except ValidationError as exc:
            raise InputError(str(exc)) from exc

        for index, record in enumerate(data["records"]):
            if int(record["id"]) == validated_id:
                updated_record = {**record, **validated_updates}
                data["records"][index] = item_from_dict(updated_record).to_dict()
                self._save_data(data)
                return "Record updated successfully.", format_single_record(data["records"][index])

        raise AppError(f"Record not found: id={validated_id}")

    def delete_record(self, record_id) -> tuple[str, str]:
        """Delete a record by id and return its details."""
        try:
            validated_id = validate_positive_int(record_id, "id")
        except ValidationError as exc:
            raise InputError(str(exc)) from exc

        data = self._load_data()

        for index, record in enumerate(data["records"]):
            if int(record["id"]) == validated_id:
                deleted = data["records"].pop(index)
                self._save_data(data)
                return "Record deleted successfully.", format_single_record(deleted)

        raise AppError(f"Record not found: id={validated_id}")

    def export_records(self, export_format: str, output: str | None, filters: dict) -> str:
        """Export filtered records to CSV or JSON."""
        try:
            validated_format = validate_export_format(export_format)
        except ValidationError as exc:
            raise InputError(str(exc)) from exc

        filtered = self._filtered_records(filters)

        if validated_format == "csv":
            destination = export_csv(filtered, output or "records.csv")
        else:
            destination = export_json(filtered, output or "records_export.json")

        return f"Exported to {destination}"

    def list_categories(self) -> str:
        """Return the allowed category list."""
        data = self._load_data()
        return format_category_list(self._sorted_categories(data))

    def add_category(self, category: str) -> str:
        """Add a new allowed category and persist it."""
        data = self._load_data()
        categories = self._sorted_categories(data)

        try:
            validated_category = ensure_category_not_exists(category, categories)
        except ValidationError as exc:
            raise InputError(str(exc)) from exc

        data["categories"] = sorted(categories + [validated_category])
        self._save_data(data)
        return f"Category added successfully: {validated_category}\n\n{format_category_list(data['categories'])}"

    def delete_category(self, category: str) -> str:
        """Delete one allowed category without touching history records."""
        data = self._load_data()
        categories = self._sorted_categories(data)

        try:
            validated_category = ensure_category_exists(category, categories)
        except ValidationError as exc:
            raise AppError(str(exc)) from exc

        data["categories"] = [item for item in categories if item != validated_category]
        self._save_data(data)
        return f"Category deleted successfully: {validated_category}\n\n{format_category_list(data['categories'])}"

    def _filtered_records(self, filters: dict) -> list[dict]:
        """Load, validate, and filter records for read-only workflows."""
        try:
            validated_filters = _validated_filters(filters)
        except ValidationError as exc:
            raise InputError(str(exc)) from exc

        data = self._load_data()
        records = self._normalized_records(data["records"])
        return apply_filters(records, validated_filters)

    def _validate_updates(self, updates: dict, categories: list[str]) -> dict:
        """Validate edit payload fields."""
        validated = {}

        if "date" in updates and updates["date"] is not None:
            validated["date"] = validate_date(updates["date"])
        if "type" in updates and updates["type"] is not None:
            validated["type"] = validate_type(updates["type"])
        if "category" in updates and updates["category"] is not None:
            validated["category"] = validate_category_allowed(updates["category"], categories)
        if "amount" in updates and updates["amount"] is not None:
            validated["amount"] = validate_positive_int(updates["amount"], "amount")
        if "note" in updates and updates["note"] is not None:
            validated["note"] = normalize_note(updates["note"])

        return validated

    def _load_data(self) -> dict:
        """Load persistent data and translate storage failures."""
        try:
            return self.storage.load()
        except StorageError as exc:
            raise AppError(str(exc)) from exc

    def _normalized_records(self, records: list[dict]) -> list[dict]:
        """Normalize raw record dictionaries into validated item dicts."""
        try:
            return [item_from_dict(record).to_dict() for record in records]
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError("Data file is corrupted: invalid record structure.") from exc

    def _save_data(self, data: dict) -> None:
        """Persist data and translate storage failures."""
        try:
            self.storage.save(data)
        except StorageError as exc:
            raise AppError(str(exc)) from exc

    def _sorted_categories(self, data: dict) -> list[str]:
        """Return categories in stable sorted order for output and checks."""
        return sorted(data["categories"])
