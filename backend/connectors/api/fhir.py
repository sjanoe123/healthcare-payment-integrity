"""HL7 FHIR R4 API connector.

Provides connectivity to FHIR R4 servers for extracting healthcare data
including Claims, ExplanationOfBenefit, Patient, Coverage, and Practitioner.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator

from ..base import SyncMode
from ..models import ConnectionTestResult, ConnectorSubtype, ConnectorType, DataType
from ..registry import register_connector
from .base_api import BaseAPIConnector, HTTPX_AVAILABLE

logger = logging.getLogger(__name__)


# FHIR resource types relevant to payment integrity
FHIR_RESOURCE_TYPES = {
    "claims": ["Claim", "ExplanationOfBenefit"],
    "eligibility": ["Coverage", "CoverageEligibilityResponse"],
    "providers": ["Practitioner", "PractitionerRole", "Organization", "Location"],
    "reference": ["CodeSystem", "ValueSet", "NamingSystem"],
}

# Common FHIR search parameters
FHIR_SEARCH_PARAMS = {
    "Claim": ["created", "patient", "provider", "status", "use"],
    "ExplanationOfBenefit": ["created", "patient", "provider", "status"],
    "Coverage": ["patient", "status", "period"],
    "Patient": ["identifier", "name", "birthdate", "gender"],
    "Practitioner": ["identifier", "name", "active"],
    "Organization": ["identifier", "name", "active", "type"],
}


class FHIRConnector(BaseAPIConnector):
    """Connector for HL7 FHIR R4 servers.

    Supports:
    - SMART on FHIR authentication (OAuth2)
    - FHIR bundle pagination
    - Resource type filtering
    - _lastUpdated-based incremental sync
    - Multiple resource type extraction
    """

    def __init__(
        self,
        connector_id: str,
        name: str,
        config: dict[str, Any],
        batch_size: int = 100,
    ) -> None:
        """Initialize FHIR connector.

        Args:
            connector_id: Unique identifier
            name: Human-readable name
            config: FHIR configuration with keys:
                - base_url: FHIR server base URL
                - resource_types: List of resource types to extract
                - auth_type: none, basic, bearer, oauth2
                - oauth2_config: SMART on FHIR OAuth2 settings
                - include_params: _include parameters
                - search_params: Additional search parameters
            batch_size: Records per batch (_count parameter)
        """
        super().__init__(connector_id, name, config, batch_size)

    def test_connection(self) -> ConnectionTestResult:
        """Test FHIR server connection."""
        result = super().test_connection()

        if result.success:
            try:
                # Get capability statement
                response = self._get("/metadata")
                capability = response.json()

                # Extract server info
                result.details["fhir_version"] = capability.get(
                    "fhirVersion", "unknown"
                )
                result.details["software"] = capability.get("software", {}).get(
                    "name", "unknown"
                )

                # Get supported resource types
                rest = capability.get("rest", [{}])[0]
                resources = rest.get("resource", [])
                resource_types = [r.get("type") for r in resources if r.get("type")]
                result.details["resource_types"] = resource_types[:10]
                result.details["total_resource_types"] = len(resource_types)

            except Exception as e:
                result.details["metadata_warning"] = str(e)[:100]

        return result

    def extract(
        self,
        sync_mode: SyncMode,
        watermark_value: str | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        """Extract data from FHIR server.

        Args:
            sync_mode: Full or incremental sync
            watermark_value: Last sync timestamp for incremental

        Yields:
            Batches of FHIR resources converted to flat records
        """
        if not self._connected:
            self.connect()

        resource_types = self.config.get("resource_types", ["Claim"])
        if isinstance(resource_types, str):
            resource_types = [resource_types]

        total_extracted = 0

        for resource_type in resource_types:
            self._log("info", f"Extracting FHIR resource: {resource_type}")

            for batch in self._extract_resource(
                resource_type, sync_mode, watermark_value
            ):
                yield batch
                total_extracted += len(batch)

        self._log("info", f"Extracted {total_extracted} total FHIR resources")

    def _extract_resource(
        self,
        resource_type: str,
        sync_mode: SyncMode,
        watermark_value: str | None,
    ) -> Iterator[list[dict[str, Any]]]:
        """Extract a specific FHIR resource type.

        Args:
            resource_type: FHIR resource type (e.g., Claim)
            sync_mode: Full or incremental
            watermark_value: Timestamp for incremental sync

        Yields:
            Batches of flattened records
        """
        # Build search parameters
        params: dict[str, Any] = {
            "_count": self.batch_size,
            "_format": "json",
        }

        # Add _include parameters
        include_params = self.config.get("include_params", [])
        if include_params:
            params["_include"] = include_params

        # Add custom search params
        search_params = self.config.get("search_params", {})
        params.update(search_params)

        # Add _lastUpdated for incremental sync
        if sync_mode == SyncMode.INCREMENTAL and watermark_value:
            params["_lastUpdated"] = f"ge{watermark_value}"

        # Initial search
        endpoint = f"/{resource_type}"
        next_url: str | None = endpoint

        while next_url:
            # Make request
            if next_url == endpoint:
                response = self._get(endpoint, params=params)
            else:
                # Follow next link (already has params)
                response = self._get(next_url)

            bundle = response.json()

            # Extract entries
            entries = bundle.get("entry", [])
            if not entries:
                break

            # Flatten resources
            records = []
            for entry in entries:
                resource = entry.get("resource", {})
                if resource:
                    flat_record = self._flatten_resource(resource)
                    records.append(flat_record)

            if records:
                yield records

            # Get next page URL
            next_url = self._get_next_link(bundle)

    def _get_next_link(self, bundle: dict[str, Any]) -> str | None:
        """Extract next page URL from bundle.

        Args:
            bundle: FHIR Bundle response

        Returns:
            Next page URL or None
        """
        links = bundle.get("link", [])
        for link in links:
            if link.get("relation") == "next":
                url = link.get("url")
                # Convert absolute URL to relative path
                if url:
                    base_url = self.config.get("base_url", "")
                    if url.startswith(base_url):
                        return url[len(base_url) :]
                    return url
        return None

    def _flatten_resource(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Flatten a FHIR resource to a simple dictionary.

        Args:
            resource: FHIR resource

        Returns:
            Flattened dictionary suitable for storage
        """
        resource_type = resource.get("resourceType", "Unknown")
        flat: dict[str, Any] = {
            "resource_type": resource_type,
            "resource_id": resource.get("id"),
            "last_updated": resource.get("meta", {}).get("lastUpdated"),
        }

        # Handle common resource types
        if resource_type == "Claim":
            flat.update(self._flatten_claim(resource))
        elif resource_type == "ExplanationOfBenefit":
            flat.update(self._flatten_eob(resource))
        elif resource_type == "Coverage":
            flat.update(self._flatten_coverage(resource))
        elif resource_type == "Patient":
            flat.update(self._flatten_patient(resource))
        elif resource_type == "Practitioner":
            flat.update(self._flatten_practitioner(resource))
        elif resource_type == "Organization":
            flat.update(self._flatten_organization(resource))
        else:
            # Generic flattening for other types
            flat.update(self._flatten_generic(resource))

        return flat

    def _flatten_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        """Flatten FHIR Claim resource.

        Args:
            claim: FHIR Claim resource

        Returns:
            Flattened claim data
        """
        flat: dict[str, Any] = {
            "status": claim.get("status"),
            "use": claim.get("use"),
            "type_code": self._get_codeable_concept(claim.get("type")),
            "patient_reference": self._get_reference(claim.get("patient")),
            "created": claim.get("created"),
            "provider_reference": self._get_reference(claim.get("provider")),
            "priority_code": self._get_codeable_concept(claim.get("priority")),
            "total_value": self._get_money(claim.get("total")),
        }

        # Billable period
        billable = claim.get("billablePeriod", {})
        flat["billable_start"] = billable.get("start")
        flat["billable_end"] = billable.get("end")

        # Diagnosis codes
        diagnoses = claim.get("diagnosis", [])
        flat["diagnosis_codes"] = [
            self._get_codeable_concept(d.get("diagnosisCodeableConcept"))
            for d in diagnoses
        ]

        # Procedure codes
        procedures = claim.get("procedure", [])
        flat["procedure_codes"] = [
            self._get_codeable_concept(p.get("procedureCodeableConcept"))
            for p in procedures
        ]

        # Items/service lines
        items = claim.get("item", [])
        flat["items"] = [self._flatten_claim_item(item) for item in items]
        flat["item_count"] = len(items)

        # Insurance
        insurances = claim.get("insurance", [])
        if insurances:
            flat["insurance_reference"] = self._get_reference(
                insurances[0].get("coverage")
            )

        return flat

    def _flatten_claim_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Flatten a Claim item (service line).

        Args:
            item: FHIR Claim item

        Returns:
            Flattened item data
        """
        return {
            "sequence": item.get("sequence"),
            "service_code": self._get_codeable_concept(item.get("productOrService")),
            "modifier_codes": [
                self._get_codeable_concept(m) for m in item.get("modifier", [])
            ],
            "quantity": item.get("quantity", {}).get("value"),
            "unit_price": self._get_money(item.get("unitPrice")),
            "net": self._get_money(item.get("net")),
            "service_date": item.get("servicedDate"),
            "location_code": self._get_codeable_concept(
                item.get("locationCodeableConcept")
            ),
        }

    def _flatten_eob(self, eob: dict[str, Any]) -> dict[str, Any]:
        """Flatten FHIR ExplanationOfBenefit resource.

        Args:
            eob: FHIR ExplanationOfBenefit resource

        Returns:
            Flattened EOB data
        """
        flat: dict[str, Any] = {
            "status": eob.get("status"),
            "use": eob.get("use"),
            "outcome": eob.get("outcome"),
            "type_code": self._get_codeable_concept(eob.get("type")),
            "patient_reference": self._get_reference(eob.get("patient")),
            "created": eob.get("created"),
            "provider_reference": self._get_reference(eob.get("provider")),
            "claim_reference": self._get_reference(eob.get("claim")),
        }

        # Billable period
        billable = eob.get("billablePeriod", {})
        flat["billable_start"] = billable.get("start")
        flat["billable_end"] = billable.get("end")

        # Total amounts
        totals = eob.get("total", [])
        for total in totals:
            category = self._get_codeable_concept(total.get("category"))
            amount = self._get_money(total.get("amount"))
            if category:
                flat[f"total_{category.lower().replace(' ', '_')}"] = amount

        # Payment
        payment = eob.get("payment", {})
        flat["payment_amount"] = self._get_money(payment.get("amount"))
        flat["payment_date"] = payment.get("date")

        # Items
        items = eob.get("item", [])
        flat["item_count"] = len(items)

        return flat

    def _flatten_coverage(self, coverage: dict[str, Any]) -> dict[str, Any]:
        """Flatten FHIR Coverage resource.

        Args:
            coverage: FHIR Coverage resource

        Returns:
            Flattened coverage data
        """
        return {
            "status": coverage.get("status"),
            "type_code": self._get_codeable_concept(coverage.get("type")),
            "subscriber_reference": self._get_reference(coverage.get("subscriber")),
            "beneficiary_reference": self._get_reference(coverage.get("beneficiary")),
            "payor_reference": self._get_reference(
                coverage.get("payor", [{}])[0] if coverage.get("payor") else {}
            ),
            "period_start": coverage.get("period", {}).get("start"),
            "period_end": coverage.get("period", {}).get("end"),
            "subscriber_id": coverage.get("subscriberId"),
            "dependent": coverage.get("dependent"),
            "relationship_code": self._get_codeable_concept(
                coverage.get("relationship")
            ),
        }

    def _flatten_patient(self, patient: dict[str, Any]) -> dict[str, Any]:
        """Flatten FHIR Patient resource.

        Args:
            patient: FHIR Patient resource

        Returns:
            Flattened patient data
        """
        # Get primary identifier
        identifiers = patient.get("identifier", [])
        primary_id = identifiers[0].get("value") if identifiers else None
        id_system = identifiers[0].get("system") if identifiers else None

        # Get primary name
        names = patient.get("name", [])
        if names:
            name = names[0]
            family = name.get("family", "")
            given = " ".join(name.get("given", []))
        else:
            family = ""
            given = ""

        return {
            "identifier": primary_id,
            "identifier_system": id_system,
            "family_name": family,
            "given_name": given,
            "birth_date": patient.get("birthDate"),
            "gender": patient.get("gender"),
            "active": patient.get("active"),
            "deceased": patient.get("deceasedBoolean", False),
        }

    def _flatten_practitioner(self, practitioner: dict[str, Any]) -> dict[str, Any]:
        """Flatten FHIR Practitioner resource.

        Args:
            practitioner: FHIR Practitioner resource

        Returns:
            Flattened practitioner data
        """
        # Get NPI
        identifiers = practitioner.get("identifier", [])
        npi = None
        for ident in identifiers:
            if "npi" in ident.get("system", "").lower():
                npi = ident.get("value")
                break

        # Get primary name
        names = practitioner.get("name", [])
        if names:
            name = names[0]
            family = name.get("family", "")
            given = " ".join(name.get("given", []))
        else:
            family = ""
            given = ""

        return {
            "npi": npi,
            "family_name": family,
            "given_name": given,
            "active": practitioner.get("active"),
            "gender": practitioner.get("gender"),
        }

    def _flatten_organization(self, org: dict[str, Any]) -> dict[str, Any]:
        """Flatten FHIR Organization resource.

        Args:
            org: FHIR Organization resource

        Returns:
            Flattened organization data
        """
        # Get NPI
        identifiers = org.get("identifier", [])
        npi = None
        for ident in identifiers:
            if "npi" in ident.get("system", "").lower():
                npi = ident.get("value")
                break

        return {
            "npi": npi,
            "name": org.get("name"),
            "type_code": self._get_codeable_concept(
                org.get("type", [{}])[0] if org.get("type") else {}
            ),
            "active": org.get("active"),
        }

    def _flatten_generic(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Generic flattening for unknown resource types.

        Args:
            resource: FHIR resource

        Returns:
            Basic flattened data
        """
        flat: dict[str, Any] = {}

        # Extract common fields
        for key in ["status", "active", "name", "identifier"]:
            if key in resource:
                value = resource[key]
                if isinstance(value, list):
                    flat[key] = str(value[0]) if value else None
                else:
                    flat[key] = value

        return flat

    def _get_codeable_concept(self, concept: dict[str, Any] | None) -> str | None:
        """Extract code from CodeableConcept.

        Args:
            concept: FHIR CodeableConcept

        Returns:
            Code string or None
        """
        if not concept:
            return None

        codings = concept.get("coding", [])
        if codings:
            return codings[0].get("code")

        return concept.get("text")

    def _get_reference(self, ref: dict[str, Any] | None) -> str | None:
        """Extract reference string.

        Args:
            ref: FHIR Reference

        Returns:
            Reference string or None
        """
        if not ref:
            return None
        return ref.get("reference")

    def _get_money(self, money: dict[str, Any] | None) -> float | None:
        """Extract money value.

        Args:
            money: FHIR Money

        Returns:
            Decimal value or None
        """
        if not money:
            return None
        return money.get("value")

    def discover_schema(self) -> dict[str, Any]:
        """Discover FHIR server capabilities.

        Returns:
            Server capabilities and supported resources
        """
        if not self._connected:
            self.connect()

        try:
            response = self._get("/metadata")
            capability = response.json()

            # Extract server info
            software = capability.get("software", {})
            rest = capability.get("rest", [{}])[0]
            resources = rest.get("resource", [])

            # Build resource list with search params
            resource_info = []
            for res in resources:
                res_type = res.get("type")
                if res_type:
                    search_params = [p.get("name") for p in res.get("searchParam", [])]
                    resource_info.append(
                        {
                            "type": res_type,
                            "search_params": search_params[:10],
                            "interactions": [
                                i.get("code") for i in res.get("interaction", [])
                            ],
                        }
                    )

            return {
                "fhir_version": capability.get("fhirVersion"),
                "software_name": software.get("name"),
                "software_version": software.get("version"),
                "resources": resource_info,
                "security": rest.get("security", {}),
            }

        except Exception as e:
            logger.error(f"FHIR schema discovery failed: {e}")
            return {"error": str(e)}


# Configuration schema for the UI
FHIR_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["base_url"],
    "properties": {
        "base_url": {
            "type": "string",
            "title": "FHIR Server URL",
            "description": "FHIR R4 server base URL",
        },
        "resource_types": {
            "type": "array",
            "title": "Resource Types",
            "description": "FHIR resource types to extract",
            "items": {
                "type": "string",
                "enum": [
                    "Claim",
                    "ExplanationOfBenefit",
                    "Coverage",
                    "CoverageEligibilityResponse",
                    "Patient",
                    "Practitioner",
                    "PractitionerRole",
                    "Organization",
                    "Location",
                ],
            },
            "default": ["Claim"],
        },
        "auth_type": {
            "type": "string",
            "title": "Authentication",
            "description": "Authentication method",
            "enum": ["none", "basic", "bearer", "oauth2"],
            "default": "oauth2",
        },
        "username": {
            "type": "string",
            "title": "Username",
            "description": "Username for Basic auth",
        },
        "password": {
            "type": "string",
            "title": "Password",
            "description": "Password for Basic auth",
            "format": "password",
        },
        "bearer_token": {
            "type": "string",
            "title": "Bearer Token",
            "description": "Bearer token for authentication",
            "format": "password",
        },
        "oauth2_config": {
            "type": "object",
            "title": "SMART on FHIR OAuth2",
            "properties": {
                "token_url": {
                    "type": "string",
                    "title": "Token URL",
                    "description": "OAuth2 token endpoint",
                },
                "client_id": {
                    "type": "string",
                    "title": "Client ID",
                },
                "client_secret": {
                    "type": "string",
                    "title": "Client Secret",
                    "format": "password",
                },
                "scope": {
                    "type": "string",
                    "title": "Scope",
                    "description": "SMART scopes (e.g., system/*.read)",
                    "default": "system/*.read",
                },
            },
        },
        "search_params": {
            "type": "object",
            "title": "Search Parameters",
            "description": "Additional FHIR search parameters",
        },
        "include_params": {
            "type": "array",
            "title": "_include Parameters",
            "description": "Resources to include in results",
            "items": {"type": "string"},
        },
        "timeout": {
            "type": "integer",
            "title": "Timeout (seconds)",
            "description": "Request timeout",
            "default": 60,
            "minimum": 10,
            "maximum": 300,
        },
        "rate_limit": {
            "type": "integer",
            "title": "Rate Limit (req/sec)",
            "description": "Maximum requests per second",
            "default": 5,
            "minimum": 1,
            "maximum": 50,
        },
        "verify_ssl": {
            "type": "boolean",
            "title": "Verify SSL",
            "description": "Verify SSL certificates",
            "default": True,
        },
    },
}


def _register_fhir() -> None:
    """Register FHIR connector with the registry."""
    if not HTTPX_AVAILABLE:
        return

    register_connector(
        subtype=ConnectorSubtype.FHIR,
        connector_class=FHIRConnector,
        name="HL7 FHIR R4",
        description="Connect to FHIR R4 servers for healthcare data",
        connector_type=ConnectorType.API,
        config_schema=FHIR_CONFIG_SCHEMA,
        supported_data_types=[
            DataType.CLAIMS,
            DataType.ELIGIBILITY,
            DataType.PROVIDERS,
        ],
    )


# Auto-register on import
_register_fhir()
