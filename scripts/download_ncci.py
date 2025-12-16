#!/usr/bin/env python3
"""Download and process NCCI PTP and MUE data from CMS.

Downloads Medicaid NCCI edit files which are freely available from CMS.
These contain the same code edits as Medicare NCCI but without AMA license requirements.

Data sources:
- PTP: https://www.cms.gov/medicare/coding-billing/ncci-medicaid/medicaid-ncci-edit-files
- MUE: Same source

Output:
- data/ncci_ptp.json: PTP column 1/2 code pairs with modifier indicators
- data/ncci_mue.json: MUE (Medically Unlikely Edits) unit limits
"""
from __future__ import annotations

import io
import json
import ssl
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen, Request

# CMS Medicaid NCCI file URLs (updated quarterly)
# Check https://www.cms.gov/medicare/coding-billing/ncci-medicaid/medicaid-ncci-edit-files for latest
CMS_BASE = "https://www.cms.gov/files/zip"

# Current quarter files (update when CMS releases new data)
NCCI_FILES = {
    "ptp": f"{CMS_BASE}/medicaid-ncci-q1-2026-ptp-edits-practitioner-services.zip",
    "mue": f"{CMS_BASE}/medicaid-ncci-q1-2026-mue-edits-practitioner-services.zip",
}

# High-priority procedure codes for fraud detection
# Focus on codes that commonly appear in claims and have high fraud risk
HIGH_PRIORITY_CODES = {
    # E/M codes (office visits, hospital visits, ED)
    "99202", "99203", "99204", "99205", "99211", "99212", "99213", "99214", "99215",
    "99221", "99222", "99223", "99231", "99232", "99233", "99238", "99239",
    "99281", "99282", "99283", "99284", "99285", "99291", "99292",
    # Lab panels
    "80048", "80050", "80053", "80061", "85025", "85027", "36415",
    # Common imaging
    "71046", "71045", "72148", "72149", "73721", "74177",
    "93000", "93005", "93010",  # EKG
    # Therapy
    "97110", "97112", "97140", "97530", "97535", "97542",
    # Common procedures
    "43235", "43239", "45378", "45380", "45385",  # GI scopes
    "29881", "29880", "29876",  # Knee arthroscopy
    "20610", "20605", "20600",  # Joint injections
    # DME/Supplies often flagged
    "A4253", "A4259", "E0601", "E0424", "E0260",
    # Drug administration
    "96372", "96373", "96374", "96375",
    "J0696", "J1100", "J3490",  # Common injectables
}

# Also include these code ranges for comprehensive coverage
PRIORITY_CODE_PREFIXES = [
    "992",  # E/M office/outpatient
    "993",  # E/M hospital
    "994",  # E/M consultations
    "800",  # Lab panels
    "850",  # Hematology
    "364",  # Venipuncture
    "930",  # EKG
    "971",  # Physical therapy
    "433", "453", "458",  # GI procedures
]


def download_file(url: str, timeout: int = 120) -> bytes:
    """Download a file from URL with SSL handling."""
    print(f"  Downloading: {url}")

    # Create SSL context that doesn't verify (CMS certificates sometimes have issues)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (Healthcare Payment Integrity)"})
    try:
        with urlopen(request, timeout=timeout, context=ctx) as response:
            data = response.read()
            print(f"  Downloaded {len(data):,} bytes")
            return data
    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        return b""


def parse_ptp_file(zip_data: bytes, active_only: bool = True) -> list[dict[str, Any]]:
    """Parse PTP edit file from ZIP.

    File format (tab-delimited):
    - Line 0: Title
    - Line 1: Notice
    - Line 2: Headers: Col1, Col2, EffDt, DelDt, ModifierIndicator, PTP Edit Rationale
    - Line 3+: Data

    Args:
        zip_data: ZIP file bytes
        active_only: If True, only include edits without deletion dates or future deletion

    Returns:
        List of PTP edit records
    """
    if not zip_data:
        return []

    ptp_pairs = []
    today = datetime.now().strftime("%Y%m%d")

    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".txt"):
                    print(f"  Processing: {name}")
                    content = zf.read(name).decode("utf-8", errors="ignore")
                    lines = content.strip().split("\n")

                    # Skip header lines (first 3 lines)
                    for line in lines[3:]:
                        if not line.strip() or "\t" not in line:
                            continue

                        parts = line.split("\t")
                        if len(parts) < 5:
                            continue

                        col1 = parts[0].strip()
                        col2 = parts[1].strip()
                        eff_date = parts[2].strip()
                        del_date = parts[3].strip()
                        modifier = parts[4].strip()
                        rationale = parts[5].strip() if len(parts) > 5 else ""

                        # Skip if not active (has past deletion date)
                        if active_only and del_date and del_date < today:
                            continue

                        # Skip if either code is empty
                        if not col1 or not col2:
                            continue

                        ptp_pairs.append({
                            "codes": sorted([col1, col2]),
                            "column1": col1,
                            "column2": col2,
                            "modifier": modifier,  # 0=not allowed, 1=allowed, 9=N/A
                            "effective_date": eff_date,
                            "deletion_date": del_date if del_date else None,
                            "rationale": rationale,
                        })
                    break

    except Exception as e:
        print(f"  Error parsing PTP file: {e}")

    return ptp_pairs


def parse_mue_file(zip_data: bytes) -> dict[str, dict[str, Any]]:
    """Parse MUE values file from ZIP.

    File format (tab-delimited):
    - Lines 0-8: Copyright and notices
    - Line 9: Headers: HCPCS/CPT Code, MUE Values, MUE Rationale
    - Line 10+: Data

    Returns:
        Dictionary mapping code to MUE limit info
    """
    if not zip_data:
        return {}

    mue_limits = {}

    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".txt"):
                    print(f"  Processing: {name}")
                    content = zf.read(name).decode("utf-8", errors="ignore")
                    lines = content.strip().split("\n")

                    # Find the header line
                    data_start = 0
                    for i, line in enumerate(lines):
                        if "HCPCS/CPT Code" in line:
                            data_start = i + 1
                            break

                    # Parse data lines
                    for line in lines[data_start:]:
                        if not line.strip() or "\t" not in line:
                            continue

                        parts = line.split("\t")
                        if len(parts) < 2:
                            continue

                        code = parts[0].strip()
                        mue_value = parts[1].strip()
                        rationale = parts[2].strip() if len(parts) > 2 else ""

                        if not code or not mue_value:
                            continue

                        try:
                            limit = int(mue_value)
                            mue_limits[code] = {
                                "limit": limit,
                                "unit": "services",
                                "rationale": rationale,
                            }
                        except ValueError:
                            continue
                    break

    except Exception as e:
        print(f"  Error parsing MUE file: {e}")

    return mue_limits


def filter_priority_codes(ptp_pairs: list[dict], mue_limits: dict) -> tuple[list[dict], dict]:
    """Filter to priority codes for smaller file size.

    This reduces the dataset to common high-volume codes that are most
    relevant for fraud detection in typical claims processing.

    Uses two-tier filtering:
    1. High-priority codes (specific codes known for fraud risk)
    2. Priority prefixes (code ranges for common services)
    """
    print("\n  Filtering to priority codes...")

    def is_priority(code: str) -> bool:
        # Check if it's a specific high-priority code
        if code in HIGH_PRIORITY_CODES:
            return True
        # Check if it matches a priority prefix
        for prefix in PRIORITY_CODE_PREFIXES:
            if code.startswith(prefix):
                return True
        return False

    # Filter PTP pairs where AT LEAST ONE code is high-priority
    # (captures edits involving common codes)
    filtered_ptp = [
        p for p in ptp_pairs
        if is_priority(p["column1"]) or is_priority(p["column2"])
    ]

    # Further filter to pairs where both are core clinical codes
    def is_core_code(code: str) -> bool:
        # Focus on E/M, key labs, common radiology, common medicine
        return (
            code.startswith(("99",  # E/M
                           "800", "850", "851", "852",  # Key labs
                           "710", "720", "730", "740",  # Common imaging
                           "930", "931", "932", "933",  # Cardio diagnostics
                           "971", "972",  # Physical therapy
                           "963", "964",  # Drug admin
                           "364",  # Venipuncture
                           "432", "433", "453", "454",  # GI scopes
                           "298",  # Arthroscopy
                           "206",  # Joint injections
                           ))
        )

    # Apply filter to keep dataset manageable
    filtered_ptp = [
        p for p in filtered_ptp
        if is_core_code(p["column1"]) and is_core_code(p["column2"])
    ]

    # For MUE, keep more codes (they're small records)
    # Include E/M, labs, radiology, medicine, therapy, procedures
    def is_mue_relevant(code: str) -> bool:
        return (
            code.startswith(("99",  # E/M
                           "8",  # Labs/pathology
                           "7",  # Radiology
                           "9",  # Medicine
                           "36", "43", "45", "29", "20", "27",  # Common procedures
                           "A", "E", "G", "J", "L", "Q",  # HCPCS
                           ))
        )

    filtered_mue = {
        code: info for code, info in mue_limits.items()
        if is_mue_relevant(code)
    }

    print(f"  PTP: {len(ptp_pairs):,} -> {len(filtered_ptp):,} pairs")
    print(f"  MUE: {len(mue_limits):,} -> {len(filtered_mue):,} codes")

    return filtered_ptp, filtered_mue


def deduplicate_ptp(ptp_pairs: list[dict]) -> list[dict]:
    """Remove duplicate PTP pairs (same codes, keep most restrictive)."""
    # Group by sorted code pair
    by_pair: dict[tuple, list[dict]] = {}
    for p in ptp_pairs:
        key = tuple(p["codes"])
        if key not in by_pair:
            by_pair[key] = []
        by_pair[key].append(p)

    # For each pair, keep the most restrictive (modifier=0 preferred)
    deduped = []
    for key, records in by_pair.items():
        # Sort by modifier (0 first, then 1, then 9)
        records.sort(key=lambda x: x.get("modifier", "9"))
        deduped.append(records[0])

    return deduped


def generate_sample_data() -> tuple[list[dict], dict]:
    """Generate sample NCCI data as fallback when downloads fail."""
    print("  Generating fallback sample data...")

    ptp_pairs = [
        {"codes": ["99213", "99214"], "column1": "99213", "column2": "99214", "modifier": "0", "rationale": "E/M level conflict"},
        {"codes": ["99214", "99215"], "column1": "99214", "column2": "99215", "modifier": "0", "rationale": "E/M level conflict"},
        {"codes": ["80053", "80048"], "column1": "80053", "column2": "80048", "modifier": "0", "rationale": "CMP includes BMP"},
        {"codes": ["85025", "85027"], "column1": "85025", "column2": "85027", "modifier": "0", "rationale": "CBC with diff includes CBC"},
        {"codes": ["93000", "93005"], "column1": "93000", "column2": "93005", "modifier": "0", "rationale": "EKG global includes tracing"},
        {"codes": ["43239", "43235"], "column1": "43239", "column2": "43235", "modifier": "0", "rationale": "EGD with biopsy includes diagnostic"},
        {"codes": ["45380", "45378"], "column1": "45380", "column2": "45378", "modifier": "0", "rationale": "Colonoscopy with biopsy includes diagnostic"},
        {"codes": ["99213", "36415"], "column1": "99213", "column2": "36415", "modifier": "1", "rationale": "E/M with venipuncture - modifier allowed"},
        {"codes": ["71046", "71045"], "column1": "71046", "column2": "71045", "modifier": "0", "rationale": "Chest X-ray 2v includes 1v"},
    ]

    mue_limits = {
        "99211": {"limit": 1, "unit": "services", "rationale": "E/M - one per DOS"},
        "99212": {"limit": 1, "unit": "services", "rationale": "E/M - one per DOS"},
        "99213": {"limit": 1, "unit": "services", "rationale": "E/M - one per DOS"},
        "99214": {"limit": 1, "unit": "services", "rationale": "E/M - one per DOS"},
        "99215": {"limit": 1, "unit": "services", "rationale": "E/M - one per DOS"},
        "99291": {"limit": 1, "unit": "services", "rationale": "Critical care initial"},
        "99292": {"limit": 8, "unit": "services", "rationale": "Critical care add-on"},
        "36415": {"limit": 3, "unit": "services", "rationale": "Venipuncture"},
        "85025": {"limit": 2, "unit": "services", "rationale": "CBC"},
        "80053": {"limit": 2, "unit": "services", "rationale": "CMP"},
        "97110": {"limit": 12, "unit": "services", "rationale": "Therapeutic exercises"},
    }

    return ptp_pairs, mue_limits


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "data"
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("NCCI Data Download Script")
    print("=" * 60)
    print("\nSource: CMS Medicaid NCCI Edit Files")
    print("https://www.cms.gov/medicare/coding-billing/ncci-medicaid/medicaid-ncci-edit-files\n")

    # Download and process MUE data
    print("Step 1: Downloading MUE (Medically Unlikely Edits)...")
    mue_data = download_file(NCCI_FILES["mue"])
    mue_limits = parse_mue_file(mue_data)

    if not mue_limits:
        print("  MUE download failed, using sample data")
        _, mue_limits = generate_sample_data()

    # Download and process PTP data
    print("\nStep 2: Downloading PTP (Procedure-to-Procedure Edits)...")
    print("  Note: This is a large file (~68MB), please wait...")
    ptp_data = download_file(NCCI_FILES["ptp"], timeout=180)
    ptp_pairs = parse_ptp_file(ptp_data, active_only=True)

    if not ptp_pairs:
        print("  PTP download failed, using sample data")
        ptp_pairs, _ = generate_sample_data()

    # Filter and deduplicate
    print("\nStep 3: Processing data...")
    if len(ptp_pairs) > 10000:
        ptp_pairs, mue_limits = filter_priority_codes(ptp_pairs, mue_limits)

    ptp_pairs = deduplicate_ptp(ptp_pairs)
    print(f"  After deduplication: {len(ptp_pairs):,} PTP pairs")

    # Write output files
    print("\nStep 4: Writing output files...")

    ptp_output = output_dir / "ncci_ptp.json"
    # Use compact format (no indent) for large PTP file
    with open(ptp_output, "w") as f:
        json.dump(ptp_pairs, f, separators=(",", ":"))
    ptp_size = ptp_output.stat().st_size
    print(f"  Written {len(ptp_pairs):,} PTP pairs to: {ptp_output} ({ptp_size / 1024 / 1024:.1f} MB)")

    mue_output = output_dir / "ncci_mue.json"
    with open(mue_output, "w") as f:
        json.dump(mue_limits, f, indent=2)
    mue_size = mue_output.stat().st_size
    print(f"  Written {len(mue_limits):,} MUE limits to: {mue_output} ({mue_size:,} bytes)")

    print("\n" + "=" * 60)
    print("NCCI data download complete!")
    print("=" * 60)

    # Print summary statistics
    print("\nSummary:")
    print(f"  PTP Code Pairs: {len(ptp_pairs):,}")
    if ptp_pairs:
        mod_0 = sum(1 for p in ptp_pairs if p.get("modifier") == "0")
        mod_1 = sum(1 for p in ptp_pairs if p.get("modifier") == "1")
        print(f"    - Modifier 0 (never bill together): {mod_0:,}")
        print(f"    - Modifier 1 (modifier may allow): {mod_1:,}")

    print(f"  MUE Limits: {len(mue_limits):,}")
    if mue_limits:
        common_limits = sorted(
            [(k, v["limit"]) for k, v in mue_limits.items() if k.startswith("99")],
            key=lambda x: x[0]
        )[:5]
        print(f"    Sample E/M limits: {common_limits}")

    return 0


if __name__ == "__main__":
    exit(main())
