"""Healthcare data type interfaces.

Provides structured schemas and validation for healthcare data types:
- Claims (837P/837I)
- Eligibility (270/271)
- Providers (NPI, taxonomy)
- Reference data (NCCI, LCD, MPFS)
"""

from .claims import (
    ClaimRecord,
    ClaimLine,
    ClaimType,
    validate_claim,
    normalize_claim,
)
from .eligibility import (
    EligibilityRecord,
    CoverageInfo,
    BenefitInfo,
    validate_eligibility,
    normalize_eligibility,
)
from .providers import (
    ProviderRecord,
    ProviderType,
    validate_provider,
    normalize_provider,
)

__all__ = [
    # Claims
    "ClaimRecord",
    "ClaimLine",
    "ClaimType",
    "validate_claim",
    "normalize_claim",
    # Eligibility
    "EligibilityRecord",
    "CoverageInfo",
    "BenefitInfo",
    "validate_eligibility",
    "normalize_eligibility",
    # Providers
    "ProviderRecord",
    "ProviderType",
    "validate_provider",
    "normalize_provider",
]
