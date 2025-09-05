"""
Simple Error Correction System
Basic field validation and normalization
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CorrectionResult:
    """Result of correction attempt"""
    original: Any
    corrected_text: Any
    has_correction: bool
    confidence: float
    reasoning: str
    requires_confirmation: bool = False


class ErrorCorrectionSystem:
    """
    Basic error correction with simple validation
    """
    
    def __init__(self, model: str = "gpt-5-mini"):
        self.model = model
    
    async def correct(self, text: str, context: Dict[str, Any] = None) -> CorrectionResult:
        """
        Simple correction for common patterns
        Returns corrected text if any corrections needed
        """
        # No correction for very short inputs
        if len(text.strip()) < 3:
            return CorrectionResult(
                original=text,
                corrected_text=text,
                has_correction=False,
                confidence=1.0,
                reasoning="Text too short to correct"
            )
        
        # Simple normalizations
        corrected = text
        corrections_made = []
        
        # Normalize common OS names (case-insensitive replacement)
        os_normalizations = {
            "red hat 8": "RHEL8",
            "rhel 8": "RHEL8",
            "redhat 8": "RHEL8",
            "windows 2022": "Windows Server 2022",
            "win22": "Windows Server 2022",
            "win 2022": "Windows Server 2022"
        }
        
        lower_text = corrected.lower()
        for pattern, replacement in os_normalizations.items():
            if pattern in lower_text:
                # Case-insensitive replacement
                import re
                corrected = re.sub(re.escape(pattern), replacement, corrected, flags=re.IGNORECASE)
                corrections_made.append(f"Normalized '{pattern}' to '{replacement}'")
        
        # Check if corrections were made
        has_correction = corrected != text
        
        return CorrectionResult(
            original=text,
            corrected_text=corrected,
            has_correction=has_correction,
            confidence=0.9 if has_correction else 1.0,
            reasoning="; ".join(corrections_made) if corrections_made else "No corrections needed",
            requires_confirmation=False
        )


def validate_field(field_name: str, value: Any) -> Tuple[bool, str]:
    """
    Basic field validation
    Returns (is_valid, error_message)
    """
    
    if not value:
        return False, f"{field_name} is required"
    
    # Basic email validation for requestor ID
    if field_name == "requestor_id" and "@" not in str(value):
        return False, "Requestor ID must be an email address"
    
    # Zone validation for GCP
    if field_name == "zone" and value:
        import re
        # Basic GCP zone pattern: region-zone (e.g., us-east4-a)
        if not re.match(r'^[a-z]+-[a-z0-9]+-[a-z]$', value):
            return False, f"Invalid zone format: {value}"
    
    return True, ""


def normalize_value(field_name: str, value: Any) -> Any:
    """
    Simple value normalization
    """
    if not value:
        return value
    
    # Normalize environment values
    if field_name == "environment":
        env_map = {
            "prod": "production",
            "dev": "development",
            "test": "test",
            "stage": "staging",
            "qa": "qa"
        }
        lower_val = str(value).lower()
        return env_map.get(lower_val, value)
    
    # Normalize OS values
    if field_name == "operatingSystem":
        os_map = {
            "rhel8": "RHEL8",
            "rhel 8": "RHEL8",
            "red hat 8": "RHEL8",
            "windows 2022": "Windows Server 2022",
            "win2022": "Windows Server 2022",
            "ubuntu": "Ubuntu 20.04",
            "ubuntu20": "Ubuntu 20.04"
        }
        lower_val = str(value).lower()
        return os_map.get(lower_val, value)
    
    return value