"""
Utilities for VM field handling: canonical field names and answer sanitization.
"""

from __future__ import annotations

from typing import Dict, Any
import logging

from .gcp_catalog import is_valid_machine_type, is_valid_zone

logger = logging.getLogger(__name__)


# Single source of truth for canonical VMRequest field names
CANONICAL_VM_FIELDS = {
    "machineType",
    "zone",
    "project",
    "lineOfBusiness",
    "costCenter",
    "os",
    "useType",
    "id",
    "appEnvironment",
    "appEnvironmentSubtype",
}


def canonical_vm_fields() -> set[str]:
    """Return the canonical VMRequest field names."""
    return CANONICAL_VM_FIELDS


def sanitize_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize user answers before applying them to the VMRequest.

    - Keep only canonical fields.
    - Map ambiguous keys (e.g., "which", "what", "type", "size") to
      machineType when the value is a valid machine type.
    - Map ambiguous keys to zone when the value is a valid zone.
    - Drop unknown/ambiguous keys otherwise.
    """
    if not answers:
        return {}

    sanitized: Dict[str, Any] = {}
    for raw_key, value in answers.items():
        key = str(raw_key).strip()
        if key in CANONICAL_VM_FIELDS:
            sanitized[key] = value
            continue

        key_lower = key.lower()
        # Attempt value-based canonicalization for common ambiguous keys
        if key_lower in {"which", "what", "type", "size"}:
            if isinstance(value, (str, int)):
                v_str = str(value)
                if is_valid_machine_type(v_str):
                    sanitized["machineType"] = v_str
                    logger.info("[Sanitize] Mapped ambiguous key '%s' to 'machineType'", raw_key)
                    continue
                if is_valid_zone(v_str):
                    sanitized["zone"] = v_str
                    logger.info("[Sanitize] Mapped ambiguous key '%s' to 'zone'", raw_key)
                    continue

        # Unknown key: drop silently (avoid logging sensitive values)
        logger.warning("[Sanitize] Dropping unknown answer key '%s'", raw_key)

    return sanitized

