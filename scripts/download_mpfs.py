#!/usr/bin/env python3
"""Download and process Medicare Physician Fee Schedule (MPFS) data from CMS.

Downloads the PFS Relative Value Files which contain:
- RVU values (work, practice expense, malpractice)
- National payment rates
- Global surgery indicators
- Status codes

Data source:
https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files

Output:
- data/mpfs.json: Procedure codes with RVUs and national payment rates
"""

from __future__ import annotations

import csv
import io
import json
import ssl
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import urlopen, Request

# CMS MPFS RVU file URL (updated annually, with quarterly corrections)
# Check https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files for latest
CMS_MPFS_URL = "https://www.cms.gov/files/zip/rvu25a-updated-01/10/2025.zip"

# The main RVU file within the ZIP
RVU_CSV_FILENAME = "PPRRVU25_JAN.csv"

# 2025 Conversion Factor (used to calculate payment from RVUs)
CONVERSION_FACTOR = 32.3465

# CSV column indices (based on PPRRVU25_JAN.csv format)
COL_HCPCS = 0
COL_MOD = 1
COL_DESCRIPTION = 2
COL_STATUS = 3
COL_WORK_RVU = 5
COL_NONFAC_PE_RVU = 6
COL_FAC_PE_RVU = 8
COL_MP_RVU = 10
COL_NONFAC_TOTAL = 11
COL_FAC_TOTAL = 12
COL_GLOBAL = 14
COL_CONV_FACTOR = 24

# Filter to relevant procedure codes
RELEVANT_CODE_PREFIXES = (
    "99",  # E/M codes
    "80",
    "81",
    "82",
    "83",
    "84",
    "85",
    "86",
    "87",
    "88",
    "89",  # Lab/Pathology
    "70",
    "71",
    "72",
    "73",
    "74",
    "75",
    "76",
    "77",
    "78",
    "79",  # Radiology
    "90",
    "91",
    "92",
    "93",
    "94",
    "95",
    "96",
    "97",  # Medicine
    "36",  # Vascular access
    "43",
    "45",  # GI procedures
    "29",  # Arthroscopy
    "10",
    "11",
    "12",  # Integumentary
    "20",
    "21",
    "27",  # Musculoskeletal
    "A",
    "E",
    "G",
    "J",
    "L",
    "Q",  # HCPCS Level II
)


def download_file(url: str, timeout: int = 60) -> bytes:
    """Download a file from URL with SSL handling."""
    print(f"  Downloading: {url}")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    request = Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Healthcare Payment Integrity)"}
    )
    try:
        with urlopen(request, timeout=timeout, context=ctx) as response:
            data = response.read()
            print(f"  Downloaded {len(data):,} bytes")
            return data
    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        return b""


def safe_float(value: str, default: float = 0.0) -> float:
    """Safely convert string to float."""
    if not value or not value.strip():
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def parse_mpfs_csv(zip_data: bytes) -> dict[str, dict[str, Any]]:
    """Parse MPFS RVU CSV file from ZIP.

    Returns:
        Dictionary mapping HCPCS code to fee schedule info
    """
    if not zip_data:
        return {}

    mpfs_data = {}

    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            # Find the RVU CSV file
            csv_file = None
            for name in zf.namelist():
                if "PPRRVU" in name and name.endswith(".csv"):
                    csv_file = name
                    break

            if not csv_file:
                print("  Error: Could not find RVU CSV file in ZIP")
                return {}

            print(f"  Processing: {csv_file}")
            content = zf.read(csv_file).decode("utf-8", errors="ignore")
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)

            # Find header row (contains "HCPCS")
            header_row = 0
            for i, row in enumerate(rows):
                if row and row[0] == "HCPCS":
                    header_row = i
                    break

            # Process data rows
            for row in rows[header_row + 1 :]:
                if len(row) < 15:
                    continue

                hcpcs = row[COL_HCPCS].strip()
                if not hcpcs:
                    continue

                # Filter to relevant codes
                if not hcpcs.startswith(RELEVANT_CODE_PREFIXES):
                    continue

                modifier = row[COL_MOD].strip()
                description = row[COL_DESCRIPTION].strip()
                status = row[COL_STATUS].strip()

                # Skip deleted codes
                if status == "D":
                    continue

                # Get RVU values
                work_rvu = safe_float(row[COL_WORK_RVU])
                nonfac_pe_rvu = safe_float(row[COL_NONFAC_PE_RVU])
                fac_pe_rvu = safe_float(row[COL_FAC_PE_RVU])
                mp_rvu = safe_float(row[COL_MP_RVU])
                nonfac_total = safe_float(row[COL_NONFAC_TOTAL])
                fac_total = safe_float(row[COL_FAC_TOTAL])
                global_surgery = (
                    row[COL_GLOBAL].strip() if len(row) > COL_GLOBAL else "XXX"
                )

                # Calculate national payment (Total RVU * Conversion Factor)
                nonfac_payment = round(nonfac_total * CONVERSION_FACTOR, 2)
                fac_payment = round(fac_total * CONVERSION_FACTOR, 2)

                # Use code with modifier as key if modifier exists
                key = f"{hcpcs}-{modifier}" if modifier else hcpcs

                # Skip if we already have this code without modifier and this has no modifier
                if not modifier and key in mpfs_data:
                    continue

                mpfs_data[key] = {
                    "hcpcs": hcpcs,
                    "modifier": modifier if modifier else None,
                    "description": description,
                    "status": status,
                    "work_rvu": work_rvu,
                    "pe_rvu_nonfac": nonfac_pe_rvu,
                    "pe_rvu_fac": fac_pe_rvu,
                    "mp_rvu": mp_rvu,
                    "total_rvu_nonfac": nonfac_total,
                    "total_rvu_fac": fac_total,
                    "global_surgery": global_surgery,
                    "regions": {
                        "national_nonfac": nonfac_payment,
                        "national_fac": fac_payment,
                    },
                    "conversion_factor": CONVERSION_FACTOR,
                }

    except Exception as e:
        print(f"  Error parsing MPFS file: {e}")

    return mpfs_data


def generate_sample_data() -> dict[str, dict[str, Any]]:
    """Generate sample MPFS data as fallback."""
    print("  Generating fallback sample data...")

    return {
        "99213": {
            "hcpcs": "99213",
            "description": "Office visit, established, low",
            "status": "A",
            "work_rvu": 1.30,
            "total_rvu_nonfac": 2.75,
            "total_rvu_fac": 1.97,
            "global_surgery": "XXX",
            "regions": {"national_nonfac": 88.95, "national_fac": 63.72},
            "conversion_factor": CONVERSION_FACTOR,
        },
        "99214": {
            "hcpcs": "99214",
            "description": "Office visit, established, moderate",
            "status": "A",
            "work_rvu": 1.92,
            "total_rvu_nonfac": 3.80,
            "total_rvu_fac": 2.83,
            "global_surgery": "XXX",
            "regions": {"national_nonfac": 122.92, "national_fac": 91.54},
            "conversion_factor": CONVERSION_FACTOR,
        },
        "85025": {
            "hcpcs": "85025",
            "description": "CBC with diff, automated",
            "status": "A",
            "work_rvu": 0.00,
            "total_rvu_nonfac": 0.33,
            "total_rvu_fac": 0.33,
            "global_surgery": "XXX",
            "regions": {"national_nonfac": 10.67, "national_fac": 10.67},
            "conversion_factor": CONVERSION_FACTOR,
        },
    }


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "data"
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("MPFS Fee Schedule Download Script")
    print("=" * 60)
    print("\nSource: CMS PFS Relative Value Files")
    print(
        "https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files\n"
    )

    # Download and process MPFS data
    print("Step 1: Downloading MPFS RVU file...")
    zip_data = download_file(CMS_MPFS_URL)
    mpfs_data = parse_mpfs_csv(zip_data)

    if not mpfs_data:
        print("  Download failed, using sample data")
        mpfs_data = generate_sample_data()

    # Write output
    print("\nStep 2: Writing output file...")
    output_path = output_dir / "mpfs.json"
    with open(output_path, "w") as f:
        json.dump(mpfs_data, f, indent=2)

    file_size = output_path.stat().st_size
    print(f"  Written {len(mpfs_data):,} procedure codes to: {output_path}")
    print(f"  File size: {file_size / 1024:.1f} KB")

    print("\n" + "=" * 60)
    print("MPFS data download complete!")
    print("=" * 60)

    # Summary statistics
    print("\nSummary:")
    print(f"  Total codes: {len(mpfs_data):,}")

    # Count by code type
    em_codes = sum(1 for k in mpfs_data if k.startswith("99"))
    lab_codes = sum(1 for k in mpfs_data if k.startswith(("8",)))
    imaging_codes = sum(1 for k in mpfs_data if k.startswith("7"))
    hcpcs_codes = sum(1 for k in mpfs_data if k[0].isalpha())

    print(f"  E/M codes (99xxx): {em_codes}")
    print(f"  Lab codes (8xxxx): {lab_codes}")
    print(f"  Imaging codes (7xxxx): {imaging_codes}")
    print(f"  HCPCS Level II: {hcpcs_codes}")

    # Sample E/M code
    if "99213" in mpfs_data:
        sample = mpfs_data["99213"]
        print("\n  Sample - 99213:")
        print(f"    Description: {sample.get('description', 'N/A')}")
        print(f"    Work RVU: {sample.get('work_rvu', 'N/A')}")
        print(
            f"    National Payment: ${sample.get('regions', {}).get('national_nonfac', 'N/A')}"
        )

    return 0


if __name__ == "__main__":
    exit(main())
