#!/usr/bin/env python3
"""Load and process OIG LEIE (List of Excluded Individuals/Entities) data."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def load_leie(source_path: str, output_path: str) -> dict:
    """
    Parse LEIE CSV and extract excluded NPIs.

    Args:
        source_path: Path to LEIE_raw.csv
        output_path: Path to output JSON file

    Returns:
        Statistics about the loaded data
    """
    excluded_npis = set()
    excluded_names = []
    total_rows = 0
    rows_with_npi = 0

    with open(source_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            npi = row.get("NPI", "").strip()

            # NPI should be 10 digits and not all zeros
            if npi and len(npi) == 10 and npi != "0000000000":
                excluded_npis.add(npi)
                rows_with_npi += 1

            # Also track by name for entities without NPI
            busname = row.get("BUSNAME", "").strip()
            lastname = row.get("LASTNAME", "").strip()
            firstname = row.get("FIRSTNAME", "").strip()
            excltype = row.get("EXCLTYPE", "").strip()
            excldate = row.get("EXCLDATE", "").strip()

            if busname or lastname:
                excluded_names.append(
                    {
                        "name": busname
                        if busname
                        else f"{lastname}, {firstname}".strip(", "),
                        "npi": npi if npi != "0000000000" else None,
                        "exclusion_type": excltype,
                        "exclusion_date": excldate,
                    }
                )

    # Output data structure
    output_data = {
        "excluded_npis": sorted(list(excluded_npis)),
        "metadata": {
            "source": "OIG LEIE",
            "total_exclusions": total_rows,
            "exclusions_with_npi": rows_with_npi,
            "unique_npis": len(excluded_npis),
        },
    }

    # Write JSON output
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    return output_data["metadata"]


def main():
    """Main entry point."""
    # Default paths
    base_dir = Path(__file__).parent.parent
    source_path = base_dir.parent / "artifacts" / "reference" / "LEIE_raw.csv"
    output_path = base_dir / "data" / "oig_exclusions.json"

    # Allow override via command line
    if len(sys.argv) > 1:
        source_path = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])

    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}")
        print(
            "Download LEIE data from: https://oig.hhs.gov/exclusions/exclusions_list.asp"
        )
        return 1

    print(f"Loading LEIE data from: {source_path}")
    stats = load_leie(str(source_path), str(output_path))

    print("\nLEIE Processing Complete:")
    print(f"  Total exclusions: {stats['total_exclusions']:,}")
    print(f"  With NPI: {stats['exclusions_with_npi']:,}")
    print(f"  Unique NPIs: {stats['unique_npis']:,}")
    print(f"\nOutput written to: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
