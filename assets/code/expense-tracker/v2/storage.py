import json
from pathlib import Path


DEFAULT_CATEGORIES = ["entertainment", "food", "other", "salary", "transport"]


def empty_data() -> dict:
    """Return the initial v2 storage structure."""
    return {"next_id": 1, "categories": list(DEFAULT_CATEGORIES), "records": []}


class StorageError(RuntimeError):
    """Raised when the persistent data file cannot be read or written."""

    pass


class Storage:
    """Read and write the JSON data store used by the CLI."""

    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or Path(__file__).with_name("records.json")

    def load(self) -> dict:
        """Load the data file and apply lightweight v1-to-v2 migration."""
        if not self.file_path.exists():
            data = empty_data()
            self.save(data)
            return data

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise StorageError("Data file is corrupted: invalid JSON in records.json.") from exc
        except OSError as exc:
            raise StorageError(f"Failed to read data file: {exc}") from exc

        if not isinstance(data, dict) or "next_id" not in data or "records" not in data:
            raise StorageError("Data file is corrupted: missing required keys.")
        if not isinstance(data["records"], list):
            raise StorageError("Data file is corrupted: 'records' must be a list.")

        categories = data.get("categories")
        if categories is None:
            data["categories"] = list(DEFAULT_CATEGORIES)
            self.save(data)
        elif not isinstance(categories, list) or any(not isinstance(category, str) for category in categories):
            raise StorageError("Data file is corrupted: 'categories' must be a list of strings.")

        return data

    def save(self, data: dict) -> None:
        """Persist the complete data structure to disk."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.file_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.write("\n")
        except OSError as exc:
            raise StorageError(f"Failed to write data file: {exc}") from exc
