"""
Reference Data Loader for Healthcare Payment Integrity Test Data.

Loads NCCI PTP pairs, MUE limits, OIG exclusions, and MPFS rates
from the existing data/ directory to generate realistic fraud scenarios.
"""

import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class MPFSEntry:
    """Medicare Physician Fee Schedule entry."""
    code: str
    description: str
    work_rvu: float
    total_rvu_nonfac: float
    total_rvu_fac: float
    conversion_factor: float
    global_surgery: str
    national_nonfac: float
    national_fac: float

    @property
    def medicare_rate(self) -> float:
        """Calculate non-facility Medicare rate."""
        return self.total_rvu_nonfac * self.conversion_factor

    @property
    def medicare_rate_facility(self) -> float:
        """Calculate facility Medicare rate."""
        return self.total_rvu_fac * self.conversion_factor


@dataclass
class MUEEntry:
    """Medically Unlikely Edit entry."""
    code: str
    limit: int
    unit: str
    rationale: str


@dataclass
class PTPEntry:
    """Procedure-to-Procedure edit entry."""
    column1: str
    column2: str
    modifier: str  # "0" = no modifier allowed, "1" = modifier allowed
    rationale: str
    effective_date: str


class ReferenceDataLoader:
    """Load and index reference data for fraud scenario generation."""

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the reference data loader.

        Args:
            data_dir: Path to the data/ directory. Defaults to ../../data relative to this file.
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data"
        self.data_dir = data_dir

        # Loaded data
        self._ncci_ptp: Optional[list[PTPEntry]] = None
        self._ncci_mue: Optional[dict[str, MUEEntry]] = None
        self._oig_exclusions: Optional[set[str]] = None
        self._mpfs: Optional[dict[str, MPFSEntry]] = None

        # Indexed data for quick lookups
        self._ptp_by_code: dict[str, list[PTPEntry]] = {}
        self._priced_codes: list[tuple[str, MPFSEntry]] = []

    def load_all(self) -> "ReferenceDataLoader":
        """Load all reference data files."""
        self.load_ncci_ptp()
        self.load_ncci_mue()
        self.load_oig_exclusions()
        self.load_mpfs()
        return self

    def load_ncci_ptp(self) -> list[PTPEntry]:
        """
        Load NCCI Procedure-to-Procedure edits.

        Format: Array of {column1, column2, modifier, rationale, effective_date}
        """
        if self._ncci_ptp is not None:
            return self._ncci_ptp

        ptp_path = self.data_dir / "ncci_ptp.json"
        if not ptp_path.exists():
            print(f"Warning: NCCI PTP file not found at {ptp_path}")
            self._ncci_ptp = []
            return self._ncci_ptp

        with open(ptp_path) as f:
            raw_data = json.load(f)

        self._ncci_ptp = []
        for entry in raw_data:
            ptp = PTPEntry(
                column1=entry.get("column1", ""),
                column2=entry.get("column2", ""),
                modifier=entry.get("modifier", "0"),
                rationale=entry.get("rationale", ""),
                effective_date=entry.get("effective_date", ""),
            )
            self._ncci_ptp.append(ptp)

            # Index by both codes for quick lookup
            self._ptp_by_code.setdefault(ptp.column1, []).append(ptp)
            self._ptp_by_code.setdefault(ptp.column2, []).append(ptp)

        print(f"Loaded {len(self._ncci_ptp)} NCCI PTP pairs")
        return self._ncci_ptp

    def load_ncci_mue(self) -> dict[str, MUEEntry]:
        """
        Load NCCI Medically Unlikely Edits.

        Format: Dict of {code: {limit, unit, rationale}}
        """
        if self._ncci_mue is not None:
            return self._ncci_mue

        mue_path = self.data_dir / "ncci_mue.json"
        if not mue_path.exists():
            print(f"Warning: NCCI MUE file not found at {mue_path}")
            self._ncci_mue = {}
            return self._ncci_mue

        with open(mue_path) as f:
            raw_data = json.load(f)

        self._ncci_mue = {}
        for code, info in raw_data.items():
            if isinstance(info, dict):
                self._ncci_mue[code] = MUEEntry(
                    code=code,
                    limit=info.get("limit", 1),
                    unit=info.get("unit", "services"),
                    rationale=info.get("rationale", ""),
                )

        print(f"Loaded {len(self._ncci_mue)} NCCI MUE codes")
        return self._ncci_mue

    def load_oig_exclusions(self) -> set[str]:
        """
        Load OIG Excluded Provider NPIs.

        Format: {excluded_npis: [npi1, npi2, ...]}
        """
        if self._oig_exclusions is not None:
            return self._oig_exclusions

        oig_path = self.data_dir / "oig_exclusions.json"
        if not oig_path.exists():
            print(f"Warning: OIG exclusions file not found at {oig_path}")
            self._oig_exclusions = set()
            return self._oig_exclusions

        with open(oig_path) as f:
            raw_data = json.load(f)

        self._oig_exclusions = set(raw_data.get("excluded_npis", []))
        print(f"Loaded {len(self._oig_exclusions)} OIG excluded NPIs")
        return self._oig_exclusions

    def load_mpfs(self) -> dict[str, MPFSEntry]:
        """
        Load Medicare Physician Fee Schedule.

        Format: Dict of {code: {hcpcs, description, work_rvu, ...}}
        """
        if self._mpfs is not None:
            return self._mpfs

        mpfs_path = self.data_dir / "mpfs.json"
        if not mpfs_path.exists():
            print(f"Warning: MPFS file not found at {mpfs_path}")
            self._mpfs = {}
            return self._mpfs

        with open(mpfs_path) as f:
            raw_data = json.load(f)

        self._mpfs = {}
        for code, info in raw_data.items():
            if isinstance(info, dict):
                regions = info.get("regions", {})
                entry = MPFSEntry(
                    code=code,
                    description=info.get("description", ""),
                    work_rvu=info.get("work_rvu", 0.0),
                    total_rvu_nonfac=info.get("total_rvu_nonfac", 0.0),
                    total_rvu_fac=info.get("total_rvu_fac", 0.0),
                    conversion_factor=info.get("conversion_factor", 32.3465),
                    global_surgery=info.get("global_surgery", "XXX"),
                    national_nonfac=regions.get("national_nonfac", 0.0),
                    national_fac=regions.get("national_fac", 0.0),
                )
                self._mpfs[code] = entry

                # Index codes with actual pricing for outlier scenarios
                if entry.medicare_rate > 50:  # Only codes with meaningful rates
                    self._priced_codes.append((code, entry))

        print(f"Loaded {len(self._mpfs)} MPFS codes ({len(self._priced_codes)} with pricing)")
        return self._mpfs

    # =====================================================
    # ACCESSORS
    # =====================================================

    @property
    def ncci_ptp(self) -> list[PTPEntry]:
        """Get NCCI PTP pairs."""
        if self._ncci_ptp is None:
            self.load_ncci_ptp()
        return self._ncci_ptp or []

    @property
    def ncci_mue(self) -> dict[str, MUEEntry]:
        """Get NCCI MUE limits."""
        if self._ncci_mue is None:
            self.load_ncci_mue()
        return self._ncci_mue or {}

    @property
    def oig_exclusions(self) -> set[str]:
        """Get OIG excluded NPIs."""
        if self._oig_exclusions is None:
            self.load_oig_exclusions()
        return self._oig_exclusions or set()

    @property
    def mpfs(self) -> dict[str, MPFSEntry]:
        """Get MPFS entries."""
        if self._mpfs is None:
            self.load_mpfs()
        return self._mpfs or {}

    @property
    def priced_codes(self) -> list[tuple[str, MPFSEntry]]:
        """Get codes with meaningful pricing for outlier scenarios."""
        if self._mpfs is None:
            self.load_mpfs()
        return self._priced_codes

    # =====================================================
    # HELPER METHODS
    # =====================================================

    def get_ptp_pairs_for_code(self, code: str) -> list[PTPEntry]:
        """Get all PTP pairs involving a specific code."""
        if self._ncci_ptp is None:
            self.load_ncci_ptp()
        return self._ptp_by_code.get(code, [])

    def get_mue_limit(self, code: str) -> Optional[int]:
        """Get MUE limit for a procedure code."""
        mue = self.ncci_mue.get(code)
        return mue.limit if mue else None

    def is_oig_excluded(self, npi: str) -> bool:
        """Check if an NPI is on the OIG exclusion list."""
        return npi in self.oig_exclusions

    def get_medicare_rate(self, code: str, facility: bool = False) -> Optional[float]:
        """Get Medicare rate for a procedure code."""
        entry = self.mpfs.get(code)
        if entry is None:
            return None
        return entry.medicare_rate_facility if facility else entry.medicare_rate

    def get_random_oig_excluded_npis(self, count: int = 50) -> list[str]:
        """Get a random sample of OIG excluded NPIs."""
        import random
        npis = list(self.oig_exclusions)
        return random.sample(npis, min(count, len(npis)))

    def get_random_ptp_pairs(self, count: int = 100) -> list[PTPEntry]:
        """Get a random sample of PTP pairs for violation scenarios."""
        import random
        return random.sample(self.ncci_ptp, min(count, len(self.ncci_ptp)))

    def get_random_mue_codes(self, count: int = 100) -> list[MUEEntry]:
        """Get a random sample of MUE codes for violation scenarios."""
        import random
        entries = list(self.ncci_mue.values())
        return random.sample(entries, min(count, len(entries)))

    def get_random_priced_codes(self, count: int = 100) -> list[tuple[str, MPFSEntry]]:
        """Get a random sample of priced codes for outlier scenarios."""
        import random
        return random.sample(self.priced_codes, min(count, len(self.priced_codes)))

    # =====================================================
    # PROCEDURE CODE CATEGORIES
    # =====================================================

    def categorize_code(self, code: str) -> str:
        """Categorize a procedure code by type."""
        if not code:
            return "unknown"

        # HCPCS Level II (start with letter)
        if code[0].isalpha():
            first = code[0].upper()
            if first == "E":
                return "dme"
            elif first == "A":
                return "ambulance"
            elif first == "J":
                return "drugs"
            elif first == "L":
                return "orthotics"
            elif first == "G":
                return "procedures"
            else:
                return "hcpcs"

        # CPT codes (numeric)
        try:
            code_num = int(code[:5])
        except ValueError:
            return "unknown"

        if 99201 <= code_num <= 99499:
            return "em"
        elif 10000 <= code_num <= 69999:
            return "surgery"
        elif 70000 <= code_num <= 79999:
            return "radiology"
        elif 80000 <= code_num <= 89999:
            return "laboratory"
        elif 90000 <= code_num <= 99199:
            return "medicine"
        else:
            return "other"

    def get_codes_by_category(self, category: str, limit: int = 100) -> list[str]:
        """Get procedure codes by category from MPFS."""
        codes = [
            code for code in self.mpfs.keys()
            if self.categorize_code(code) == category
        ]
        import random
        return random.sample(codes, min(limit, len(codes))) if codes else []
