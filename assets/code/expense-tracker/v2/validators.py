import re
from datetime import datetime


class ValidationError(ValueError):
    """Raised when user input does not satisfy the CLI contract."""

    pass


def validate_type(value: str) -> str:
    """Validate the record type field."""
    if value not in {"income", "expense"}:
        raise ValidationError("Invalid type: must be 'income' or 'expense'.")
    return value


def validate_positive_int(value, field_name: str) -> int:
    """Validate a positive integer argument."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid {field_name}: must be a positive integer.") from exc

    if parsed <= 0:
        raise ValidationError(f"Invalid {field_name}: must be a positive integer.")
    return parsed


def validate_date(value: str) -> str:
    """Validate a date string in YYYY-MM-DD format."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        raise ValidationError("Invalid date: must be in YYYY-MM-DD format.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValidationError("Invalid date: must be in YYYY-MM-DD format.") from exc
    return value


def validate_month(value: str) -> str:
    """Validate a month string in YYYY-MM format."""
    if not re.fullmatch(r"\d{4}-\d{2}", value or ""):
        raise ValidationError("Invalid month: must be in YYYY-MM format.")
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValidationError("Invalid month: must be in YYYY-MM format.") from exc
    return value


def validate_category_name(value: str, field_name: str = "category") -> str:
    """Validate that a category-like string is non-empty."""
    if value is None or value.strip() == "":
        raise ValidationError(f"Invalid {field_name}: {field_name} cannot be empty.")
    return value.strip()


def validate_export_format(value: str) -> str:
    """Validate the export format argument."""
    if value not in {"csv", "json"}:
        raise ValidationError("Invalid format: must be 'csv' or 'json'.")
    return value


def validate_category_allowed(value: str, categories: list[str]) -> str:
    """Ensure a category is present in the allowed category list."""
    category = validate_category_name(value)
    if category not in categories:
        choices = ", ".join(categories)
        raise ValidationError(f"Invalid category: '{category}' is not allowed. Available categories: {choices}")
    return category


def ensure_category_not_exists(value: str, categories: list[str]) -> str:
    """Ensure a category is new before inserting it."""
    category = validate_category_name(value, "category")
    if category in categories:
        raise ValidationError(f"Category already exists: {category}")
    return category


def ensure_category_exists(value: str, categories: list[str]) -> str:
    """Ensure a category exists before deleting it."""
    category = validate_category_name(value, "category")
    if category not in categories:
        raise ValidationError(f"Category not found: {category}")
    return category


def normalize_note(value: str | None) -> str:
    """Normalize the optional note field into a string."""
    if value is None:
        return ""
    return str(value)
