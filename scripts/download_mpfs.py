#!/usr/bin/env python3
"""Download and process Medicare Physician Fee Schedule (MPFS) data from CMS."""
from __future__ import annotations

import json
from pathlib import Path


def generate_mpfs_data() -> dict:
    """
    Generate comprehensive MPFS fee schedule data.

    In production, this would download from:
    https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files

    The data includes national payment rates and key indicators.
    """
    # Common procedure codes with 2024 national rates (approximate)
    mpfs_data = {
        # Evaluation & Management - Office/Outpatient
        "99202": {"regions": {"national": 76.57}, "global_surgery": "XXX", "rvu_work": 0.93, "description": "New patient E/M, straightforward"},
        "99203": {"regions": {"national": 111.89}, "global_surgery": "XXX", "rvu_work": 1.60, "description": "New patient E/M, low complexity"},
        "99204": {"regions": {"national": 167.10}, "global_surgery": "XXX", "rvu_work": 2.60, "description": "New patient E/M, moderate complexity"},
        "99205": {"regions": {"national": 211.12}, "global_surgery": "XXX", "rvu_work": 3.50, "description": "New patient E/M, high complexity"},
        "99211": {"regions": {"national": 24.31}, "global_surgery": "XXX", "rvu_work": 0.18, "description": "Established patient E/M, may not require MD"},
        "99212": {"regions": {"national": 57.38}, "global_surgery": "XXX", "rvu_work": 0.70, "description": "Established patient E/M, straightforward"},
        "99213": {"regions": {"national": 92.42}, "global_surgery": "XXX", "rvu_work": 1.30, "description": "Established patient E/M, low complexity"},
        "99214": {"regions": {"national": 130.40}, "global_surgery": "XXX", "rvu_work": 1.92, "description": "Established patient E/M, moderate complexity"},
        "99215": {"regions": {"national": 175.51}, "global_surgery": "XXX", "rvu_work": 2.80, "description": "Established patient E/M, high complexity"},

        # ED Visits
        "99281": {"regions": {"national": 22.67}, "global_surgery": "XXX", "rvu_work": 0.25, "description": "ED visit, self-limited problem"},
        "99282": {"regions": {"national": 45.38}, "global_surgery": "XXX", "rvu_work": 0.56, "description": "ED visit, low severity"},
        "99283": {"regions": {"national": 74.84}, "global_surgery": "XXX", "rvu_work": 1.01, "description": "ED visit, moderate severity"},
        "99284": {"regions": {"national": 133.26}, "global_surgery": "XXX", "rvu_work": 1.93, "description": "ED visit, high severity"},
        "99285": {"regions": {"national": 195.24}, "global_surgery": "XXX", "rvu_work": 3.00, "description": "ED visit, high severity with threat to life"},

        # Critical Care
        "99291": {"regions": {"national": 275.06}, "global_surgery": "XXX", "rvu_work": 4.50, "description": "Critical care, first 30-74 mins"},
        "99292": {"regions": {"national": 122.57}, "global_surgery": "ZZZ", "rvu_work": 2.25, "description": "Critical care, each additional 30 mins"},

        # Hospital Visits
        "99221": {"regions": {"national": 103.35}, "global_surgery": "XXX", "rvu_work": 1.92, "description": "Initial hospital care, low complexity"},
        "99222": {"regions": {"national": 143.21}, "global_surgery": "XXX", "rvu_work": 2.61, "description": "Initial hospital care, moderate complexity"},
        "99223": {"regions": {"national": 205.91}, "global_surgery": "XXX", "rvu_work": 3.86, "description": "Initial hospital care, high complexity"},
        "99231": {"regions": {"national": 49.67}, "global_surgery": "XXX", "rvu_work": 0.76, "description": "Subsequent hospital care, stable"},
        "99232": {"regions": {"national": 89.95}, "global_surgery": "XXX", "rvu_work": 1.39, "description": "Subsequent hospital care, responding"},
        "99233": {"regions": {"national": 127.95}, "global_surgery": "XXX", "rvu_work": 2.00, "description": "Subsequent hospital care, unstable"},

        # Psychotherapy
        "90832": {"regions": {"national": 68.40}, "global_surgery": "XXX", "rvu_work": 0.97, "description": "Psychotherapy, 30 mins"},
        "90834": {"regions": {"national": 102.60}, "global_surgery": "XXX", "rvu_work": 1.45, "description": "Psychotherapy, 45 mins"},
        "90837": {"regions": {"national": 136.80}, "global_surgery": "XXX", "rvu_work": 1.93, "description": "Psychotherapy, 60 mins"},

        # Lab/Pathology
        "36415": {"regions": {"national": 3.00}, "global_surgery": "XXX", "rvu_work": 0.03, "description": "Routine venipuncture"},
        "85025": {"regions": {"national": 10.56}, "global_surgery": "XXX", "rvu_work": 0.00, "description": "CBC with diff, automated"},
        "80053": {"regions": {"national": 14.35}, "global_surgery": "XXX", "rvu_work": 0.00, "description": "Comprehensive metabolic panel"},
        "80048": {"regions": {"national": 11.12}, "global_surgery": "XXX", "rvu_work": 0.00, "description": "Basic metabolic panel"},
        "81001": {"regions": {"national": 4.12}, "global_surgery": "XXX", "rvu_work": 0.00, "description": "Urinalysis with microscopy"},

        # EKG
        "93000": {"regions": {"national": 17.61}, "global_surgery": "XXX", "rvu_work": 0.17, "description": "EKG complete"},
        "93005": {"regions": {"national": 8.40}, "global_surgery": "XXX", "rvu_work": 0.00, "description": "EKG tracing only"},
        "93010": {"regions": {"national": 9.21}, "global_surgery": "XXX", "rvu_work": 0.17, "description": "EKG interpretation only"},

        # Imaging
        "71046": {"regions": {"national": 28.67}, "global_surgery": "XXX", "rvu_work": 0.18, "description": "Chest X-ray, 2 views"},
        "71045": {"regions": {"national": 21.13}, "global_surgery": "XXX", "rvu_work": 0.14, "description": "Chest X-ray, single view"},
        "72148": {"regions": {"national": 314.92}, "global_surgery": "XXX", "rvu_work": 1.13, "description": "MRI lumbar spine without contrast"},
        "72149": {"regions": {"national": 452.43}, "global_surgery": "XXX", "rvu_work": 1.35, "description": "MRI lumbar spine with contrast"},
        "73721": {"regions": {"national": 325.12}, "global_surgery": "XXX", "rvu_work": 1.13, "description": "MRI lower extremity without contrast"},

        # Physical Therapy
        "97110": {"regions": {"national": 29.45}, "global_surgery": "XXX", "rvu_work": 0.45, "description": "Therapeutic exercises, 15 min"},
        "97140": {"regions": {"national": 29.45}, "global_surgery": "XXX", "rvu_work": 0.43, "description": "Manual therapy, 15 min"},
        "97530": {"regions": {"national": 32.56}, "global_surgery": "XXX", "rvu_work": 0.44, "description": "Therapeutic activities, 15 min"},

        # Surgical - Minor
        "10060": {"regions": {"national": 120.33}, "global_surgery": "010", "rvu_work": 1.22, "description": "I&D abscess, simple"},
        "10061": {"regions": {"national": 220.33}, "global_surgery": "010", "rvu_work": 2.50, "description": "I&D abscess, complicated"},
        "11102": {"regions": {"national": 118.78}, "global_surgery": "000", "rvu_work": 0.81, "description": "Tangential biopsy of skin"},
        "11104": {"regions": {"national": 143.21}, "global_surgery": "000", "rvu_work": 0.91, "description": "Punch biopsy of skin"},

        # Endoscopy
        "43235": {"regions": {"national": 217.89}, "global_surgery": "000", "rvu_work": 2.39, "description": "Upper GI endoscopy, diagnostic"},
        "43239": {"regions": {"national": 285.67}, "global_surgery": "000", "rvu_work": 3.00, "description": "Upper GI endoscopy with biopsy"},
        "45378": {"regions": {"national": 290.45}, "global_surgery": "000", "rvu_work": 3.69, "description": "Colonoscopy, diagnostic"},
        "45380": {"regions": {"national": 340.12}, "global_surgery": "000", "rvu_work": 4.25, "description": "Colonoscopy with biopsy"},
        "45385": {"regions": {"national": 425.34}, "global_surgery": "000", "rvu_work": 5.00, "description": "Colonoscopy with polypectomy"},

        # Injections
        "20610": {"regions": {"national": 47.89}, "global_surgery": "000", "rvu_work": 0.66, "description": "Arthrocentesis, major joint"},
        "J1040": {"regions": {"national": 3.50}, "global_surgery": "XXX", "rvu_work": 0.00, "description": "Methylprednisolone 80mg injection"},
        "96372": {"regions": {"national": 25.78}, "global_surgery": "XXX", "rvu_work": 0.17, "description": "Therapeutic injection, SC/IM"},
    }

    return mpfs_data


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "data"
    output_dir.mkdir(exist_ok=True)

    print("MPFS Fee Schedule Data Generation")
    print("=" * 50)

    print("\nGenerating comprehensive MPFS sample data...")
    mpfs_data = generate_mpfs_data()

    # Write output
    output_path = output_dir / "mpfs.json"
    with open(output_path, 'w') as f:
        json.dump(mpfs_data, f, indent=2)

    print(f"\nWritten {len(mpfs_data)} procedure codes to: {output_path}")

    print("\nMPFS data generation complete!")
    print("\nTo get full production data:")
    print("1. Visit https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files")
    print("2. Download the latest RVU file (PPRRVUxx.zip)")
    print("3. Parse the fixed-width TXT file")

    return 0


if __name__ == '__main__':
    exit(main())
