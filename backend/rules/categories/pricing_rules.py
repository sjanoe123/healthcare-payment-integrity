"""Pricing and reimbursement rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit


def pricing_exceeds_fee_rule(context: RuleContext) -> list[RuleHit]:
    """Check if billed amount exceeds fee schedule or contract."""
    fee_schedule = context.datasets.get("fee_schedule", {})
    contracts = context.datasets.get("provider_contracts", {})
    claim = context.claim
    provider = claim.get("provider", {})
    npi = provider.get("npi")
    region = provider.get("region", "national")

    provider_contract = contracts.get(npi, {})
    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code")
        billed_amount = item.get("line_amount", 0)

        if not code or not billed_amount:
            continue

        allowed = None
        if provider_contract:
            allowed = provider_contract.get("rates", {}).get(code)

        if allowed is None:
            schedule = fee_schedule.get(code, {})
            allowed = schedule.get(region) or schedule.get("national")

        if allowed and billed_amount > allowed * 1.5:
            hits.append(
                RuleHit(
                    rule_id="PRICING_EXCEEDS_FEE",
                    description=f"{code} billed ${billed_amount:.2f} exceeds fee schedule ${allowed:.2f} by {((billed_amount/allowed)-1)*100:.0f}%",
                    weight=0.10,
                    severity="medium",
                    flag="pricing_exceeds_fee",
                    citation="CMS Fee Schedule / Provider Contract",
                    metadata={
                        "category": "pricing",
                        "line_index": idx,
                        "billed_amount": billed_amount,
                        "allowed_amount": allowed,
                        "excess_percentage": ((billed_amount / allowed) - 1) * 100,
                    },
                )
            )

    return hits


def pricing_units_exceed_rule(context: RuleContext) -> list[RuleHit]:
    """Check if units exceed contract or policy limits."""
    unit_limits = context.datasets.get("unit_limits", {})
    hits: list[RuleHit] = []

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        quantity = item.get("quantity", 1)

        if not code or code not in unit_limits:
            continue

        limit = unit_limits[code]
        max_units = limit.get("max_per_claim", limit.get("max_units"))

        if max_units and quantity > max_units:
            hits.append(
                RuleHit(
                    rule_id="PRICING_UNITS_EXCEED",
                    description=f"{code} quantity {quantity} exceeds contract limit of {max_units}",
                    weight=0.12,
                    severity="medium",
                    flag="pricing_units_exceed",
                    citation="Provider Contract / Policy",
                    metadata={
                        "category": "pricing",
                        "line_index": idx,
                        "quantity": quantity,
                        "max_units": max_units,
                    },
                )
            )

    return hits


def pricing_drg_mismatch_rule(context: RuleContext) -> list[RuleHit]:
    """Check if DRG assignment matches diagnoses and procedures."""
    drg_rules = context.datasets.get("drg_rules", {})
    claim = context.claim
    assigned_drg = claim.get("drg") or claim.get("assigned_drg")

    if not assigned_drg or not drg_rules:
        return []

    drg_info = drg_rules.get(assigned_drg)
    if not drg_info:
        return []

    hits: list[RuleHit] = []
    diagnosis_codes = set(claim.get("diagnosis_codes", []))
    procedure_codes = {item.get("procedure_code") for item in claim.get("items", []) if item.get("procedure_code")}

    required_dx = set(drg_info.get("required_diagnoses", []))
    required_px = set(drg_info.get("required_procedures", []))

    if required_dx and not diagnosis_codes.intersection(required_dx):
        hits.append(
            RuleHit(
                rule_id="PRICING_DRG_MISMATCH",
                description=f"DRG {assigned_drg} requires diagnosis from: {', '.join(list(required_dx)[:3])}",
                weight=0.16,
                severity="high",
                flag="pricing_drg_mismatch",
                citation="CMS MS-DRG Grouper",
                metadata={
                    "category": "pricing",
                    "assigned_drg": assigned_drg,
                    "required_diagnoses": list(required_dx),
                    "claim_diagnoses": list(diagnosis_codes),
                },
            )
        )

    if required_px and not procedure_codes.intersection(required_px):
        hits.append(
            RuleHit(
                rule_id="PRICING_DRG_MISMATCH",
                description=f"DRG {assigned_drg} requires procedure from: {', '.join(list(required_px)[:3])}",
                weight=0.16,
                severity="high",
                flag="pricing_drg_mismatch",
                citation="CMS MS-DRG Grouper",
                metadata={
                    "category": "pricing",
                    "assigned_drg": assigned_drg,
                    "required_procedures": list(required_px),
                    "claim_procedures": list(procedure_codes),
                },
            )
        )

    expected_weight = drg_info.get("weight", 1.0)
    claimed_weight = claim.get("drg_weight")
    if claimed_weight and abs(claimed_weight - expected_weight) > 0.01:
        hits.append(
            RuleHit(
                rule_id="PRICING_DRG_WEIGHT_MISMATCH",
                description=f"DRG {assigned_drg} weight {claimed_weight} differs from expected {expected_weight}",
                weight=0.14,
                severity="high",
                flag="pricing_drg_weight",
                citation="CMS MS-DRG Weights",
                metadata={
                    "category": "pricing",
                    "assigned_drg": assigned_drg,
                    "claimed_weight": claimed_weight,
                    "expected_weight": expected_weight,
                },
            )
        )

    return hits


def pricing_revenue_code_rule(context: RuleContext) -> list[RuleHit]:
    """Check for revenue code and CPT/HCPCS mismatches."""
    revenue_code_rules = context.datasets.get("revenue_code_rules", {})
    hits: list[RuleHit] = []

    for idx, item in enumerate(context.claim.get("items", [])):
        revenue_code = item.get("revenue_code")
        procedure_code = item.get("procedure_code")

        if not revenue_code or not procedure_code:
            continue

        if revenue_code not in revenue_code_rules:
            continue

        rules = revenue_code_rules[revenue_code]
        allowed_procedures = rules.get("allowed_procedures", [])
        excluded_procedures = rules.get("excluded_procedures", [])

        if allowed_procedures and procedure_code not in allowed_procedures:
            hits.append(
                RuleHit(
                    rule_id="PRICING_REVENUE_CODE_MISMATCH",
                    description=f"Procedure {procedure_code} not valid with revenue code {revenue_code}",
                    weight=0.12,
                    severity="medium",
                    flag="pricing_revenue_mismatch",
                    citation="CMS UB-04 Guidelines",
                    metadata={
                        "category": "pricing",
                        "line_index": idx,
                        "revenue_code": revenue_code,
                        "procedure_code": procedure_code,
                    },
                )
            )

        if procedure_code in excluded_procedures:
            hits.append(
                RuleHit(
                    rule_id="PRICING_REVENUE_CODE_MISMATCH",
                    description=f"Procedure {procedure_code} explicitly excluded from revenue code {revenue_code}",
                    weight=0.14,
                    severity="high",
                    flag="pricing_revenue_mismatch",
                    citation="CMS UB-04 Guidelines",
                    metadata={
                        "category": "pricing",
                        "line_index": idx,
                        "revenue_code": revenue_code,
                        "procedure_code": procedure_code,
                    },
                )
            )

    return hits
