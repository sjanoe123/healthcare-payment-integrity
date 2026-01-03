"""Rule statistics and coverage routes.

This router provides analytics on rule execution across analyzed claims,
helping identify which rules fire most frequently and their impact.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from config import DB_PATH

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["rules"])


def safe_json_loads(data: str | None, default: list | dict | None = None) -> Any:
    """Safely parse JSON, returning default on error."""
    if default is None:
        default = []
    if not data:
        return default
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default


@router.get("/stats")
async def get_rule_stats(limit: int = Query(default=50, le=100)):
    """Get aggregated statistics on rule execution.

    Returns:
    - Total claims analyzed
    - Per-rule hit counts and percentages
    - Rule type distribution
    - Top N most triggered rules
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Get total claims count
            cursor = conn.execute("SELECT COUNT(*) FROM results")
            row = cursor.fetchone()
            total_claims = row[0] if row else 0

            if total_claims == 0:
                return {
                    "total_claims_analyzed": 0,
                    "total_rule_hits": 0,
                    "rules_by_frequency": [],
                    "rules_by_type": {},
                    "average_rules_per_claim": 0,
                }

            # Aggregate rule statistics by iterating through results
            rule_counts: dict[str, int] = defaultdict(int)
            type_counts: dict[str, int] = defaultdict(int)
            severity_counts: dict[str, int] = defaultdict(int)
            total_hits = 0

            cursor = conn.execute("SELECT rule_hits FROM results")
            for (rule_hits_json,) in cursor:
                hits = safe_json_loads(rule_hits_json, [])
                for hit in hits:
                    rule_id = hit.get("rule_id", "unknown")
                    rule_type = hit.get("rule_type", "unknown")
                    severity = hit.get("severity", "medium")

                    rule_counts[rule_id] += 1
                    type_counts[rule_type] += 1
                    severity_counts[severity] += 1
                    total_hits += 1

            # Build response
            rules_by_frequency = [
                {
                    "rule_id": rule_id,
                    "count": count,
                    "percentage": round(count / total_claims * 100, 2),
                }
                for rule_id, count in sorted(
                    rule_counts.items(), key=lambda x: x[1], reverse=True
                )[:limit]
            ]

            return {
                "total_claims_analyzed": total_claims,
                "total_rule_hits": total_hits,
                "average_rules_per_claim": round(total_hits / total_claims, 2),
                "rules_by_frequency": rules_by_frequency,
                "rules_by_type": dict(type_counts),
                "rules_by_severity": dict(severity_counts),
            }

    except Exception as e:
        logger.error(f"Failed to get rule stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get rule statistics: {str(e)[:200]}"
        )


@router.get("/catalog")
async def get_rule_catalog():
    """Get a catalog of all available rules with metadata.

    Returns list of all registered rules with their IDs, types, and descriptions.
    """
    try:
        # Import rule registry to get available rules
        from rules.registry import default_registry

        rules = []
        for rule_func in default_registry.active_rules():
            # Extract rule info from function
            rule_name = rule_func.__name__
            rule_doc = rule_func.__doc__ or ""
            rules.append(
                {
                    "rule_id": rule_name.upper(),
                    "name": rule_name.replace("_", " ").title(),
                    "description": rule_doc.strip().split("\n")[0] if rule_doc else "",
                }
            )

        return {
            "rules": rules,
            "total_rules": len(rules),
        }

    except Exception as e:
        logger.error(f"Failed to get rule catalog: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get rule catalog: {str(e)[:200]}"
        )


@router.get("/coverage")
async def get_field_coverage():
    """Get field coverage statistics for analyzed claims.

    Returns which fields are present/missing most often,
    helping identify data quality issues.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT j.claim_data
                FROM jobs j
                JOIN results r ON j.id = r.job_id
                WHERE j.claim_data IS NOT NULL
                """
            )

            field_presence: dict[str, int] = defaultdict(int)
            field_missing: dict[str, int] = defaultdict(int)
            total_claims = 0

            # Required fields for fraud detection
            required_fields = [
                "procedure_code",
                "diagnosis_code",
                "billing_npi",
                "rendering_npi",
                "service_date",
                "billed_amount",
                "patient_dob",
                "patient_gender",
                "place_of_service",
                "modifier",
            ]

            for (claim_json,) in cursor:
                claim = safe_json_loads(claim_json, {})
                if not claim:
                    continue

                total_claims += 1

                # Check main claim fields
                for field in required_fields:
                    if claim.get(field):
                        field_presence[field] += 1
                    else:
                        field_missing[field] += 1

                # Check line items
                items = claim.get("items", [])
                if items:
                    field_presence["items"] += 1
                    for item in items:
                        for field in ["procedure_code", "quantity", "line_amount"]:
                            if item.get(field):
                                field_presence[f"item.{field}"] += 1
                            else:
                                field_missing[f"item.{field}"] += 1
                else:
                    field_missing["items"] += 1

            if total_claims == 0:
                return {
                    "total_claims": 0,
                    "field_coverage": [],
                    "coverage_score": 0,
                }

            # Build coverage report
            coverage = []
            for field in required_fields + ["items"]:
                present = field_presence.get(field, 0)
                missing = field_missing.get(field, 0)
                coverage.append(
                    {
                        "field": field,
                        "present": present,
                        "missing": missing,
                        "coverage_pct": round(present / total_claims * 100, 1),
                    }
                )

            # Overall coverage score
            total_field_checks = sum(field_presence.values()) + sum(
                field_missing.values()
            )
            coverage_score = (
                round(sum(field_presence.values()) / total_field_checks * 100, 1)
                if total_field_checks > 0
                else 0
            )

            return {
                "total_claims": total_claims,
                "field_coverage": sorted(
                    coverage, key=lambda x: x["coverage_pct"], reverse=True
                ),
                "coverage_score": coverage_score,
            }

    except Exception as e:
        logger.error(f"Failed to get field coverage: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get field coverage: {str(e)[:200]}"
        )


@router.get("/effectiveness")
async def get_rule_effectiveness():
    """Get rule effectiveness metrics.

    Shows which rules have the highest impact on fraud scores
    and their average weight contribution.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT rule_hits, fraud_score FROM results")

            rule_impacts: dict[str, list[float]] = defaultdict(list)
            rule_weights: dict[str, list[float]] = defaultdict(list)

            for rule_hits_json, fraud_score in cursor:
                hits = safe_json_loads(rule_hits_json, [])
                for hit in hits:
                    rule_id = hit.get("rule_id", "unknown")
                    weight = hit.get("weight", 0)

                    rule_impacts[rule_id].append(fraud_score)
                    rule_weights[rule_id].append(weight)

            if not rule_impacts:
                return {
                    "rules": [],
                    "total_rules_fired": 0,
                }

            # Calculate effectiveness metrics
            effectiveness = []
            for rule_id in rule_impacts:
                impacts = rule_impacts[rule_id]
                weights = rule_weights[rule_id]

                effectiveness.append(
                    {
                        "rule_id": rule_id,
                        "times_fired": len(impacts),
                        "avg_weight": round(sum(weights) / len(weights), 4),
                        "total_weight_contribution": round(sum(weights), 4),
                        "avg_claim_score": round(sum(impacts) / len(impacts), 4),
                    }
                )

            # Sort by total impact
            effectiveness.sort(
                key=lambda x: abs(x["total_weight_contribution"]), reverse=True
            )

            return {
                "rules": effectiveness[:50],  # Top 50
                "total_rules_fired": len(effectiveness),
            }

    except Exception as e:
        logger.error(f"Failed to get rule effectiveness: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get rule effectiveness: {str(e)[:200]}"
        )
