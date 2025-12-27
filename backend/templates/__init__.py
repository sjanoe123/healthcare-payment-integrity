"""Connector templates for quick start setup.

This module provides pre-built connector templates for common
healthcare data sources, reducing time-to-value for new customers.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

TEMPLATES_DIR = Path(__file__).parent


def get_template_list() -> list[dict[str, Any]]:
    """Get list of available connector templates.

    Returns:
        List of template metadata (id, name, description, type, subtype).
    """
    templates = []
    for file_path in TEMPLATES_DIR.glob("*.yaml"):
        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict):
                    templates.append(
                        {
                            "id": file_path.stem,
                            "name": data.get("name", file_path.stem),
                            "description": data.get("description", ""),
                            "connector_type": data.get("connector_type", "database"),
                            "subtype": data.get("subtype", ""),
                            "data_type": data.get("data_type", "claims"),
                            "category": data.get("category", "general"),
                        }
                    )
        except Exception:
            continue

    return sorted(templates, key=lambda x: x["name"])


def get_template(template_id: str) -> dict[str, Any] | None:
    """Get a specific template by ID.

    Args:
        template_id: The template file name (without extension)

    Returns:
        Template configuration dict, or None if not found.
    """
    # Defense-in-depth: Explicit path traversal validation
    if ".." in template_id or "/" in template_id or "\\" in template_id:
        return None

    file_path = TEMPLATES_DIR / f"{template_id}.yaml"
    if not file_path.exists():
        return None

    try:
        with open(file_path) as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def apply_template(
    template_id: str, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Apply a template with optional overrides.

    Args:
        template_id: The template ID to apply
        overrides: Optional dict of values to override template defaults

    Returns:
        Merged configuration ready to create a connector.

    Raises:
        ValueError: If template not found.
    """
    template = get_template(template_id)
    if not template:
        raise ValueError(f"Template not found: {template_id}")

    # Deep copy to prevent mutations affecting original template
    config = copy.deepcopy(template)

    # Apply overrides
    if overrides:
        for key, value in overrides.items():
            if key == "connection_config" and isinstance(value, dict):
                config["connection_config"] = {
                    **config.get("connection_config", {}),
                    **value,
                }
            else:
                config[key] = value

    return config
