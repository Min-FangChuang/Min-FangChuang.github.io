import csv
import json
from pathlib import Path

from storage import StorageError


FIELD_ORDER = ["id", "date", "type", "category", "amount", "note"]


def export_csv(records: list[dict], output_path: str) -> Path:
    """Export records to a CSV file."""
    destination = Path(output_path)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=FIELD_ORDER)
            writer.writeheader()
            for record in records:
                writer.writerow({field: record.get(field, "") for field in FIELD_ORDER})
    except OSError as exc:
        raise StorageError(f"Failed to export CSV: {exc}") from exc

    return destination


def export_json(records: list[dict], output_path: str) -> Path:
    """Export records to an external-facing JSON array."""
    destination = Path(output_path)
    visible_records = [{field: record.get(field, "") for field in FIELD_ORDER} for record in records]

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as jsonfile:
            json.dump(visible_records, jsonfile, ensure_ascii=False, indent=2)
            jsonfile.write("\n")
    except OSError as exc:
        raise StorageError(f"Failed to export JSON: {exc}") from exc

    return destination
