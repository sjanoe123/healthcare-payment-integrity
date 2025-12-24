"""CSV and JSON parsers for healthcare data files.

Provides parsing capabilities for:
- CSV files with configurable delimiters and headers
- JSON files (arrays and newline-delimited JSON)
"""

from __future__ import annotations

import csv
import json
import logging
from typing import Any, Iterator

logger = logging.getLogger(__name__)


class CSVParser:
    """Parser for CSV files with healthcare data.

    Handles:
    - Configurable delimiters
    - Header row detection
    - Field name normalization
    - Type inference for common fields
    """

    def __init__(
        self,
        delimiter: str = ",",
        has_header: bool = True,
        encoding: str = "utf-8",
        quotechar: str = '"',
        field_names: list[str] | None = None,
    ) -> None:
        """Initialize the CSV parser.

        Args:
            delimiter: Field delimiter character
            has_header: Whether first row is header
            encoding: File encoding
            quotechar: Quote character
            field_names: Override field names (if no header)
        """
        self.delimiter = delimiter
        self.has_header = has_header
        self.encoding = encoding
        self.quotechar = quotechar
        self.field_names = field_names

    def parse(
        self, file_path: str, limit: int | None = None
    ) -> Iterator[dict[str, Any]]:
        """Parse a CSV file.

        Args:
            file_path: Path to CSV file
            limit: Optional limit on number of records

        Yields:
            Record dictionaries
        """
        with open(file_path, "r", encoding=self.encoding, errors="replace") as f:
            if self.has_header:
                reader = csv.DictReader(
                    f,
                    delimiter=self.delimiter,
                    quotechar=self.quotechar,
                )
            else:
                reader = csv.reader(
                    f, delimiter=self.delimiter, quotechar=self.quotechar
                )

            count = 0
            for row in reader:
                if limit and count >= limit:
                    break

                if self.has_header:
                    record = self._process_record(dict(row))
                else:
                    # Use field names or generate column names
                    field_names = self.field_names or [
                        f"column_{i}" for i in range(len(row))
                    ]
                    record = self._process_record(dict(zip(field_names, row)))

                yield record
                count += 1

    def _process_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Process a record with type inference and normalization.

        Args:
            record: Raw record dictionary

        Returns:
            Processed record
        """
        processed = {}

        for key, value in record.items():
            # Normalize key
            normalized_key = self._normalize_field_name(key)

            # Convert value
            processed[normalized_key] = self._convert_value(normalized_key, value)

        return processed

    def _normalize_field_name(self, name: str) -> str:
        """Normalize a field name.

        Args:
            name: Original field name

        Returns:
            Normalized name (lowercase, underscores)
        """
        if not name:
            return "unnamed"

        # Strip whitespace
        name = name.strip()

        # Replace spaces and special chars with underscores
        normalized = ""
        for char in name:
            if char.isalnum():
                normalized += char.lower()
            elif char in " -_":
                normalized += "_"

        # Remove consecutive underscores
        while "__" in normalized:
            normalized = normalized.replace("__", "_")

        return normalized.strip("_") or "unnamed"

    def _convert_value(self, field_name: str, value: str) -> Any:
        """Convert a value based on field name hints.

        Args:
            field_name: Normalized field name
            value: String value

        Returns:
            Converted value
        """
        if not value or value.strip() == "":
            return None

        value = value.strip()

        # Amount/charge/price fields
        if any(
            term in field_name
            for term in ["amount", "charge", "price", "cost", "fee", "total", "paid"]
        ):
            try:
                # Remove currency symbols and commas
                cleaned = value.replace("$", "").replace(",", "")
                return float(cleaned)
            except ValueError:
                return value

        # Quantity/units/count fields
        if any(term in field_name for term in ["units", "quantity", "count", "qty"]):
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return value

        # Boolean fields
        if any(term in field_name for term in ["is_", "has_", "flag", "active"]):
            lower = value.lower()
            if lower in ("true", "yes", "1", "y", "t"):
                return True
            elif lower in ("false", "no", "0", "n", "f"):
                return False

        return value


class JSONParser:
    """Parser for JSON files with healthcare data.

    Handles:
    - JSON arrays
    - Newline-delimited JSON (NDJSON)
    - Nested record extraction
    """

    def __init__(
        self,
        records_path: str | None = None,
        encoding: str = "utf-8",
    ) -> None:
        """Initialize the JSON parser.

        Args:
            records_path: Dot-notation path to records array (e.g., "data.claims")
            encoding: File encoding
        """
        self.records_path = records_path
        self.encoding = encoding

    def parse(
        self, file_path: str, limit: int | None = None
    ) -> Iterator[dict[str, Any]]:
        """Parse a JSON file.

        Args:
            file_path: Path to JSON file
            limit: Optional limit on number of records

        Yields:
            Record dictionaries
        """
        with open(file_path, "r", encoding=self.encoding, errors="replace") as f:
            # Try to detect format
            first_char = f.read(1)
            f.seek(0)

            if first_char == "[":
                # JSON array
                yield from self._parse_array(f, limit)
            elif first_char == "{":
                # Try as single object or nested structure
                try:
                    data = json.load(f)
                    records = self._extract_records(data)
                    count = 0
                    for record in records:
                        if limit and count >= limit:
                            break
                        yield self._flatten_record(record)
                        count += 1
                except json.JSONDecodeError:
                    # Try as NDJSON
                    f.seek(0)
                    yield from self._parse_ndjson(f, limit)
            else:
                # Assume NDJSON
                yield from self._parse_ndjson(f, limit)

    def _parse_array(self, f, limit: int | None) -> Iterator[dict[str, Any]]:
        """Parse a JSON array file.

        Args:
            f: File object
            limit: Record limit

        Yields:
            Record dictionaries
        """
        try:
            data = json.load(f)
            if isinstance(data, list):
                count = 0
                for item in data:
                    if limit and count >= limit:
                        break
                    if isinstance(item, dict):
                        yield self._flatten_record(item)
                        count += 1
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")

    def _parse_ndjson(self, f, limit: int | None) -> Iterator[dict[str, Any]]:
        """Parse newline-delimited JSON.

        Args:
            f: File object
            limit: Record limit

        Yields:
            Record dictionaries
        """
        count = 0
        for line in f:
            if limit and count >= limit:
                break

            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                if isinstance(record, dict):
                    yield self._flatten_record(record)
                    count += 1
            except json.JSONDecodeError:
                continue

    def _extract_records(self, data: Any) -> list[dict[str, Any]]:
        """Extract records from nested JSON structure.

        Args:
            data: JSON data

        Returns:
            List of records
        """
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]

        if isinstance(data, dict):
            # Check for records path
            if self.records_path:
                parts = self.records_path.split(".")
                current = data
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return [data]

                if isinstance(current, list):
                    return [r for r in current if isinstance(r, dict)]

            # Common array field names
            for key in ["data", "records", "items", "results", "claims"]:
                if key in data and isinstance(data[key], list):
                    return [r for r in data[key] if isinstance(r, dict)]

            # Return the object itself
            return [data]

        return []

    def _flatten_record(
        self, record: dict[str, Any], prefix: str = ""
    ) -> dict[str, Any]:
        """Flatten a nested record to single level.

        Args:
            record: Nested record
            prefix: Key prefix for nested fields

        Returns:
            Flattened record
        """
        result = {}

        for key, value in record.items():
            flat_key = f"{prefix}{key}" if prefix else key

            if isinstance(value, dict):
                # Flatten nested dict
                nested = self._flatten_record(value, f"{flat_key}_")
                result.update(nested)
            elif isinstance(value, list):
                if all(isinstance(v, dict) for v in value):
                    # Keep list of dicts as-is (e.g., service_lines)
                    result[flat_key] = value
                else:
                    # Convert simple list to comma-separated string
                    result[flat_key] = ",".join(str(v) for v in value)
            else:
                result[flat_key] = value

        return result
