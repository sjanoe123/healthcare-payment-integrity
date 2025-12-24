"""Provider data type interface.

Defines structured schemas for healthcare provider data
with validation and normalization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class ProviderType(str, Enum):
    """Type of healthcare provider."""

    INDIVIDUAL = "1"  # NPI Entity Type 1
    ORGANIZATION = "2"  # NPI Entity Type 2


class ProviderStatus(str, Enum):
    """Provider enrollment status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    TERMINATED = "terminated"
    EXCLUDED = "excluded"  # OIG/SAM excluded


@dataclass
class ProviderAddress:
    """Provider address information."""

    address_type: str = "practice"  # practice, mailing, billing
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "US"
    phone: str | None = None
    fax: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "address_type": self.address_type,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "country": self.country,
            "phone": self.phone,
            "fax": self.fax,
        }


@dataclass
class ProviderLicense:
    """Provider license information."""

    license_number: str
    license_state: str
    license_type: str | None = None  # MD, DO, NP, PA, etc.
    issue_date: date | None = None
    expiration_date: date | None = None
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "license_number": self.license_number,
            "license_state": self.license_state,
            "license_type": self.license_type,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "expiration_date": (
                self.expiration_date.isoformat() if self.expiration_date else None
            ),
            "status": self.status,
        }


@dataclass
class ProviderTaxonomy:
    """Provider taxonomy/specialty information."""

    taxonomy_code: str
    taxonomy_description: str | None = None
    is_primary: bool = False
    license_number: str | None = None
    state: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "taxonomy_code": self.taxonomy_code,
            "taxonomy_description": self.taxonomy_description,
            "is_primary": self.is_primary,
            "license_number": self.license_number,
            "state": self.state,
        }


@dataclass
class ProviderIdentifier:
    """Other provider identifiers (DEA, Medicaid, etc.)."""

    identifier_type: str  # DEA, Medicaid, Medicare, UPIN, etc.
    identifier_value: str
    state: str | None = None
    issuer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "identifier_type": self.identifier_type,
            "identifier_value": self.identifier_value,
            "state": self.state,
            "issuer": self.issuer,
        }


@dataclass
class ProviderRecord:
    """Complete provider record."""

    # Primary identifier
    npi: str
    provider_type: ProviderType = ProviderType.INDIVIDUAL

    # Individual provider fields
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    name_prefix: str | None = None  # Dr., Mr., etc.
    name_suffix: str | None = None  # Jr., III, MD, etc.
    credential: str | None = None  # MD, DO, NP, PA, etc.

    # Organization fields
    organization_name: str | None = None
    organization_other_name: str | None = None
    authorized_official_first_name: str | None = None
    authorized_official_last_name: str | None = None
    authorized_official_title: str | None = None
    authorized_official_phone: str | None = None

    # Gender (for individuals)
    gender: str | None = None  # M, F

    # Status
    status: ProviderStatus = ProviderStatus.ACTIVE
    enumeration_date: date | None = None
    last_update_date: date | None = None
    deactivation_date: date | None = None
    reactivation_date: date | None = None

    # Taxonomies/Specialties
    taxonomies: list[ProviderTaxonomy] = field(default_factory=list)
    primary_taxonomy: str | None = None

    # Addresses
    addresses: list[ProviderAddress] = field(default_factory=list)

    # Licenses
    licenses: list[ProviderLicense] = field(default_factory=list)

    # Other identifiers
    other_identifiers: list[ProviderIdentifier] = field(default_factory=list)

    # Network participation
    network_ids: list[str] = field(default_factory=list)
    payer_ids: list[str] = field(default_factory=list)

    # Exclusion info
    is_excluded: bool = False
    exclusion_type: str | None = None
    exclusion_date: date | None = None
    reinstatement_date: date | None = None

    # Metadata
    source_system: str | None = None
    last_verified: datetime | None = None

    @property
    def display_name(self) -> str:
        """Get display name for the provider."""
        if self.provider_type == ProviderType.ORGANIZATION:
            return self.organization_name or ""
        else:
            parts = []
            if self.name_prefix:
                parts.append(self.name_prefix)
            if self.first_name:
                parts.append(self.first_name)
            if self.middle_name:
                parts.append(self.middle_name)
            if self.last_name:
                parts.append(self.last_name)
            if self.name_suffix:
                parts.append(self.name_suffix)
            return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "npi": self.npi,
            "provider_type": self.provider_type.value,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "middle_name": self.middle_name,
            "name_prefix": self.name_prefix,
            "name_suffix": self.name_suffix,
            "credential": self.credential,
            "organization_name": self.organization_name,
            "organization_other_name": self.organization_other_name,
            "authorized_official_first_name": self.authorized_official_first_name,
            "authorized_official_last_name": self.authorized_official_last_name,
            "authorized_official_title": self.authorized_official_title,
            "authorized_official_phone": self.authorized_official_phone,
            "gender": self.gender,
            "display_name": self.display_name,
            "status": self.status.value,
            "enumeration_date": (
                self.enumeration_date.isoformat() if self.enumeration_date else None
            ),
            "last_update_date": (
                self.last_update_date.isoformat() if self.last_update_date else None
            ),
            "deactivation_date": (
                self.deactivation_date.isoformat() if self.deactivation_date else None
            ),
            "reactivation_date": (
                self.reactivation_date.isoformat() if self.reactivation_date else None
            ),
            "taxonomies": [t.to_dict() for t in self.taxonomies],
            "primary_taxonomy": self.primary_taxonomy,
            "addresses": [a.to_dict() for a in self.addresses],
            "licenses": [lic.to_dict() for lic in self.licenses],
            "other_identifiers": [i.to_dict() for i in self.other_identifiers],
            "network_ids": self.network_ids,
            "payer_ids": self.payer_ids,
            "is_excluded": self.is_excluded,
            "exclusion_type": self.exclusion_type,
            "exclusion_date": (
                self.exclusion_date.isoformat() if self.exclusion_date else None
            ),
            "reinstatement_date": (
                self.reinstatement_date.isoformat() if self.reinstatement_date else None
            ),
            "source_system": self.source_system,
            "last_verified": (
                self.last_verified.isoformat() if self.last_verified else None
            ),
        }


@dataclass
class ProviderValidationResult:
    """Result of provider validation."""

    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)


def validate_npi(npi: str) -> bool:
    """Validate NPI using Luhn algorithm.

    Args:
        npi: 10-digit NPI string

    Returns:
        True if valid NPI
    """
    if not npi or len(npi) != 10 or not npi.isdigit():
        return False

    # Luhn algorithm for NPI validation
    # Prefix with 80840 for health care prefix
    prefixed = "80840" + npi

    total = 0
    for i, digit in enumerate(reversed(prefixed)):
        n = int(digit)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n

    return total % 10 == 0


def validate_provider(provider: ProviderRecord) -> ProviderValidationResult:
    """Validate a provider record.

    Checks for:
    - Valid NPI format and checksum
    - Required fields based on provider type
    - Valid taxonomy codes
    - Valid license information
    - Exclusion status

    Args:
        provider: ProviderRecord to validate

    Returns:
        ProviderValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    # NPI validation
    if not provider.npi:
        errors.append({"field": "npi", "message": "NPI is required"})
    elif not validate_npi(provider.npi):
        errors.append({
            "field": "npi",
            "message": f"Invalid NPI: {provider.npi} (failed Luhn check)",
        })

    # Type-specific validation
    if provider.provider_type == ProviderType.INDIVIDUAL:
        if not provider.last_name:
            errors.append({
                "field": "last_name",
                "message": "Last name is required for individual providers",
            })
        if not provider.first_name:
            warnings.append({
                "field": "first_name",
                "message": "First name is recommended for individual providers",
            })
    else:  # Organization
        if not provider.organization_name:
            errors.append({
                "field": "organization_name",
                "message": "Organization name is required for organization providers",
            })

    # Taxonomy validation
    taxonomy_pattern = re.compile(r"^\d{10}X$")
    for i, taxonomy in enumerate(provider.taxonomies):
        if not taxonomy_pattern.match(taxonomy.taxonomy_code):
            warnings.append({
                "field": f"taxonomies[{i}].taxonomy_code",
                "message": f"Invalid taxonomy code format: {taxonomy.taxonomy_code}",
            })

    # Check for primary taxonomy
    has_primary = any(t.is_primary for t in provider.taxonomies)
    if provider.taxonomies and not has_primary:
        warnings.append({
            "field": "taxonomies",
            "message": "No primary taxonomy designated",
        })

    # License validation
    for i, lic in enumerate(provider.licenses):
        if lic.expiration_date and lic.expiration_date < date.today():
            warnings.append({
                "field": f"licenses[{i}]",
                "message": f"License expired: {lic.license_number}",
            })

    # Address validation
    if not provider.addresses:
        warnings.append({
            "field": "addresses",
            "message": "No address information provided",
        })

    # Exclusion check
    if provider.is_excluded:
        errors.append({
            "field": "is_excluded",
            "message": f"Provider is excluded ({provider.exclusion_type})",
        })

    return ProviderValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def normalize_provider(data: dict[str, Any]) -> ProviderRecord:
    """Normalize raw provider data to ProviderRecord.

    Handles various input formats including NPPES data format.

    Args:
        data: Raw provider dictionary

    Returns:
        Normalized ProviderRecord
    """

    def parse_date(val: Any) -> date | None:
        if val is None:
            return None
        if isinstance(val, date):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d", "%m-%d-%Y"):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
        return None

    # Determine provider type
    provider_type_val = data.get(
        "provider_type",
        data.get("entity_type_code", data.get("entity_type", "1")),
    )
    try:
        provider_type = ProviderType(str(provider_type_val))
    except ValueError:
        provider_type = ProviderType.INDIVIDUAL

    # Parse taxonomies
    taxonomies = []
    raw_taxonomies = data.get("taxonomies", [])

    # Handle NPPES format with taxonomy_1, taxonomy_2, etc.
    if not raw_taxonomies:
        for i in range(1, 16):
            code = data.get(f"healthcare_provider_taxonomy_code_{i}")
            if code:
                taxonomies.append(
                    ProviderTaxonomy(
                        taxonomy_code=code,
                        taxonomy_description=data.get(
                            f"provider_taxonomy_description_{i}"
                        ),
                        is_primary=data.get(f"healthcare_provider_primary_taxonomy_switch_{i}") == "Y",
                        license_number=data.get(f"provider_license_number_{i}"),
                        state=data.get(f"provider_license_number_state_code_{i}"),
                    )
                )
    else:
        for tax in raw_taxonomies:
            if isinstance(tax, dict):
                taxonomies.append(
                    ProviderTaxonomy(
                        taxonomy_code=tax.get("taxonomy_code", tax.get("code", "")),
                        taxonomy_description=tax.get("taxonomy_description", tax.get("desc")),
                        is_primary=tax.get("is_primary", tax.get("primary", False)),
                        license_number=tax.get("license_number"),
                        state=tax.get("state"),
                    )
                )
            elif isinstance(tax, str):
                taxonomies.append(ProviderTaxonomy(taxonomy_code=tax))

    # Parse addresses
    addresses = []
    raw_addresses = data.get("addresses", [])

    # Handle NPPES format with practice/mailing location
    if not raw_addresses:
        for addr_type in ["practice", "mailing"]:
            prefix = (
                "provider_first_line_business_"
                if addr_type == "practice"
                else "provider_first_line_business_mailing_"
            )
            addr1 = data.get(f"{prefix}location_address")
            if addr1:
                addresses.append(
                    ProviderAddress(
                        address_type=addr_type,
                        address_line1=addr1,
                        address_line2=data.get(f"{prefix.replace('first', 'second')}location_address"),
                        city=data.get(f"{prefix}location_city_name"),
                        state=data.get(f"{prefix}location_state_name"),
                        zip_code=data.get(f"{prefix}location_postal_code"),
                        phone=data.get(f"{prefix}location_telephone_number"),
                        fax=data.get(f"{prefix}location_fax_number"),
                    )
                )
    else:
        for addr in raw_addresses:
            if isinstance(addr, dict):
                addresses.append(
                    ProviderAddress(
                        address_type=addr.get("address_type", "practice"),
                        address_line1=addr.get("address_line1", addr.get("address1")),
                        address_line2=addr.get("address_line2", addr.get("address2")),
                        city=addr.get("city"),
                        state=addr.get("state"),
                        zip_code=addr.get("zip_code", addr.get("zip")),
                        phone=addr.get("phone"),
                        fax=addr.get("fax"),
                    )
                )

    # Parse other identifiers
    other_identifiers = []
    raw_identifiers = data.get("other_identifiers", [])

    # Handle NPPES format
    if not raw_identifiers:
        for i in range(1, 51):
            id_val = data.get(f"other_provider_identifier_{i}")
            if id_val:
                other_identifiers.append(
                    ProviderIdentifier(
                        identifier_type=data.get(
                            f"other_provider_identifier_type_code_{i}", "OTHER"
                        ),
                        identifier_value=id_val,
                        state=data.get(f"other_provider_identifier_state_{i}"),
                        issuer=data.get(f"other_provider_identifier_issuer_{i}"),
                    )
                )
    else:
        for ident in raw_identifiers:
            if isinstance(ident, dict):
                other_identifiers.append(
                    ProviderIdentifier(
                        identifier_type=ident.get("identifier_type", ident.get("type", "OTHER")),
                        identifier_value=ident.get("identifier_value", ident.get("value", "")),
                        state=ident.get("state"),
                        issuer=ident.get("issuer"),
                    )
                )

    # Get primary taxonomy
    primary_taxonomy = None
    for tax in taxonomies:
        if tax.is_primary:
            primary_taxonomy = tax.taxonomy_code
            break
    if not primary_taxonomy and taxonomies:
        primary_taxonomy = taxonomies[0].taxonomy_code

    return ProviderRecord(
        npi=data.get("npi", data.get("NPI", "")),
        provider_type=provider_type,
        first_name=data.get(
            "first_name",
            data.get("provider_first_name", data.get("authorized_official_first_name")),
        ),
        last_name=data.get(
            "last_name",
            data.get(
                "provider_last_name_legal_name",
                data.get("provider_last_name"),
            ),
        ),
        middle_name=data.get("middle_name", data.get("provider_middle_name")),
        name_prefix=data.get("name_prefix", data.get("provider_name_prefix_text")),
        name_suffix=data.get("name_suffix", data.get("provider_name_suffix_text")),
        credential=data.get("credential", data.get("provider_credential_text")),
        organization_name=data.get(
            "organization_name",
            data.get("provider_organization_name_legal_business_name"),
        ),
        organization_other_name=data.get(
            "organization_other_name",
            data.get("provider_other_organization_name"),
        ),
        authorized_official_first_name=data.get("authorized_official_first_name"),
        authorized_official_last_name=data.get("authorized_official_last_name"),
        authorized_official_title=data.get(
            "authorized_official_title",
            data.get("authorized_official_title_or_position"),
        ),
        authorized_official_phone=data.get(
            "authorized_official_phone",
            data.get("authorized_official_telephone_number"),
        ),
        gender=data.get("gender", data.get("provider_gender_code")),
        status=ProviderStatus.ACTIVE,
        enumeration_date=parse_date(
            data.get("enumeration_date", data.get("provider_enumeration_date"))
        ),
        last_update_date=parse_date(
            data.get("last_update_date", data.get("last_update"))
        ),
        deactivation_date=parse_date(
            data.get("deactivation_date", data.get("npi_deactivation_date"))
        ),
        reactivation_date=parse_date(
            data.get("reactivation_date", data.get("npi_reactivation_date"))
        ),
        taxonomies=taxonomies,
        primary_taxonomy=primary_taxonomy,
        addresses=addresses,
        licenses=[],  # Populated from taxonomies if available
        other_identifiers=other_identifiers,
        is_excluded=data.get("is_excluded", False),
        exclusion_type=data.get("exclusion_type"),
        exclusion_date=parse_date(data.get("exclusion_date")),
        source_system=data.get("source_system", data.get("_source_file")),
        last_verified=datetime.now(),
    )
