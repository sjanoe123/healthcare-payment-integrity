"""Pre-built mapping templates for common healthcare claim formats.

This module provides mapping configurations for standard claim formats:
- EDI 837P: Professional claims (CMS-1500)
- EDI 837I: Institutional claims (UB-04)
- Generic CSV: Common CSV field naming conventions
"""

from .csv_generic import CSV_GENERIC_MAPPING
from .edi_837i import EDI_837I_MAPPING
from .edi_837p import EDI_837P_MAPPING

__all__ = [
    "EDI_837P_MAPPING",
    "EDI_837I_MAPPING",
    "CSV_GENERIC_MAPPING",
]


def get_template(template_name: str) -> dict[str, str]:
    """Get a mapping template by name.

    Args:
        template_name: Name of the template ('edi_837p', 'edi_837i', 'csv')

    Returns:
        Mapping configuration dictionary

    Raises:
        ValueError: If template name is not recognized
    """
    templates = {
        "edi_837p": EDI_837P_MAPPING,
        "edi_837i": EDI_837I_MAPPING,
        "csv": CSV_GENERIC_MAPPING,
        "csv_generic": CSV_GENERIC_MAPPING,
    }

    if template_name.lower() not in templates:
        available = ", ".join(templates.keys())
        raise ValueError(f"Unknown template: {template_name}. Available: {available}")

    return templates[template_name.lower()]
