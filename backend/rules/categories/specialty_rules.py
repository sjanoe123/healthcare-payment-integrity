"""Specialty-specific rules (dental, DME, telehealth, etc.)."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit


def specialty_dental_rule(context: RuleContext) -> list[RuleHit]:
    """Check for dental procedures on medical claims."""
    dental_codes = context.datasets.get("dental_codes", set())
    claim = context.claim
    claim_type = claim.get("claim_type", "").lower()

    if claim_type == "dental":
        return []

    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code", "")

        is_dental = code in dental_codes or code.startswith("D")

        if is_dental:
            hits.append(
                RuleHit(
                    rule_id="SPECIALTY_DENTAL_ON_MEDICAL",
                    description=f"Dental procedure {code} submitted on medical claim",
                    weight=0.14,
                    severity="high",
                    flag="specialty_dental",
                    citation="Coverage Policy - Dental Exclusion",
                    metadata={
                        "category": "specialty",
                        "line_index": idx,
                        "procedure_code": code,
                        "claim_type": claim_type,
                    },
                )
            )

    return hits


def specialty_dme_rule(context: RuleContext) -> list[RuleHit]:
    """Check for DME without certificate of medical necessity."""
    dme_codes = context.datasets.get("dme_codes", {})
    cmn_on_file = context.datasets.get("cmn_on_file", {})
    claim = context.claim
    member_id = claim.get("member", {}).get("member_id")

    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code")
        if not code or code not in dme_codes:
            continue

        dme_info = dme_codes[code]
        requires_cmn = dme_info.get("requires_cmn", False)

        if not requires_cmn:
            continue

        member_cmns = cmn_on_file.get(member_id, {})
        has_valid_cmn = (
            code in member_cmns and member_cmns[code].get("status") == "valid"
        )

        if not has_valid_cmn:
            hits.append(
                RuleHit(
                    rule_id="SPECIALTY_DME_NO_CMN",
                    description=f"DME code {code} requires Certificate of Medical Necessity",
                    weight=0.15,
                    severity="high",
                    flag="specialty_dme_no_cmn",
                    citation="Medicare DME Policy",
                    metadata={
                        "category": "specialty",
                        "line_index": idx,
                        "procedure_code": code,
                    },
                )
            )

        is_rental = item.get("is_rental", False)
        rental_months = item.get("rental_month")
        purchase_price = dme_info.get("purchase_price")
        rental_price = item.get("line_amount", 0)

        if is_rental and rental_months and purchase_price:
            total_rental = rental_price * rental_months
            if total_rental > purchase_price:
                hits.append(
                    RuleHit(
                        rule_id="SPECIALTY_DME_RENTAL_EXCEED",
                        description=f"DME {code} rental cost ${total_rental:.2f} exceeds purchase price ${purchase_price:.2f}",
                        weight=0.12,
                        severity="medium",
                        flag="specialty_dme_rental",
                        citation="Medicare DME Rental Rules",
                        metadata={
                            "category": "specialty",
                            "line_index": idx,
                            "procedure_code": code,
                            "total_rental": total_rental,
                            "purchase_price": purchase_price,
                        },
                    )
                )

    return hits


def specialty_telehealth_rule(context: RuleContext) -> list[RuleHit]:
    """Check for telehealth billing compliance."""
    telehealth_codes = context.datasets.get("telehealth_codes", set())
    telehealth_eligible_providers = context.datasets.get(
        "telehealth_eligible_providers", set()
    )
    telehealth_eligible_pos = context.datasets.get(
        "telehealth_eligible_pos", {"02", "10"}
    )
    claim = context.claim
    provider = claim.get("provider", {})
    pos = claim.get("place_of_service")

    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code")
        item_pos = item.get("place_of_service") or pos

        modifiers = set(item.get("modifiers", []))
        if item.get("modifier"):
            modifiers.add(item.get("modifier"))

        is_telehealth = (
            code in telehealth_codes
            or item_pos in telehealth_eligible_pos
            or "95" in modifiers
            or "GT" in modifiers
        )

        if not is_telehealth:
            continue

        if telehealth_eligible_providers:
            provider_type = provider.get("provider_type") or provider.get("specialty")
            npi = provider.get("npi")
            if provider_type and provider_type not in telehealth_eligible_providers:
                if npi not in telehealth_eligible_providers:
                    hits.append(
                        RuleHit(
                            rule_id="SPECIALTY_TELEHEALTH_PROVIDER",
                            description=f"Provider type {provider_type} not authorized for telehealth services",
                            weight=0.14,
                            severity="high",
                            flag="specialty_telehealth",
                            citation="CMS Telehealth Policy",
                            metadata={
                                "category": "specialty",
                                "line_index": idx,
                                "provider_type": provider_type,
                            },
                        )
                    )

        if telehealth_codes and code not in telehealth_codes:
            if item_pos in {"02", "10"} or "95" in modifiers or "GT" in modifiers:
                hits.append(
                    RuleHit(
                        rule_id="SPECIALTY_TELEHEALTH_CODE",
                        description=f"Procedure {code} not eligible for telehealth delivery",
                        weight=0.13,
                        severity="medium",
                        flag="specialty_telehealth",
                        citation="CMS Telehealth Eligible Services",
                        metadata={
                            "category": "specialty",
                            "line_index": idx,
                            "procedure_code": code,
                        },
                    )
                )

    return hits


def specialty_unbundling_rule(context: RuleContext) -> list[RuleHit]:
    """Check for unbundled billing of comprehensive codes."""
    comprehensive_codes = context.datasets.get("comprehensive_codes", {})
    hits: list[RuleHit] = []

    items = context.claim.get("items", [])
    codes_billed = {
        item.get("procedure_code") for item in items if item.get("procedure_code")
    }

    for code in codes_billed:
        if code not in comprehensive_codes:
            continue

        components = set(comprehensive_codes[code].get("component_codes", []))
        billed_components = codes_billed.intersection(components)

        if billed_components:
            hits.append(
                RuleHit(
                    rule_id="SPECIALTY_UNBUNDLING",
                    description=f"Component codes {', '.join(billed_components)} billed separately from comprehensive {code}",
                    weight=0.16,
                    severity="high",
                    flag="specialty_unbundling",
                    citation="CMS Unbundling Policy",
                    metadata={
                        "category": "specialty",
                        "comprehensive_code": code,
                        "component_codes": list(billed_components),
                    },
                )
            )

    return hits


def specialty_incidental_rule(context: RuleContext) -> list[RuleHit]:
    """Check for incidental services billed separately."""
    incidental_rules = context.datasets.get("incidental_rules", {})
    hits: list[RuleHit] = []

    items = context.claim.get("items", [])
    codes_billed = {
        item.get("procedure_code") for item in items if item.get("procedure_code")
    }

    for idx, item in enumerate(items):
        code = item.get("procedure_code")
        if not code or code not in incidental_rules:
            continue

        rule = incidental_rules[code]
        incidental_to = set(rule.get("incidental_to", []))
        primary_present = codes_billed.intersection(incidental_to)

        if primary_present:
            hits.append(
                RuleHit(
                    rule_id="SPECIALTY_INCIDENTAL",
                    description=f"Procedure {code} is incidental to {', '.join(primary_present)} and should not be billed separately",
                    weight=0.12,
                    severity="medium",
                    flag="specialty_incidental",
                    citation="CMS Incidental Services Policy",
                    metadata={
                        "category": "specialty",
                        "line_index": idx,
                        "incidental_code": code,
                        "primary_codes": list(primary_present),
                    },
                )
            )

    return hits
