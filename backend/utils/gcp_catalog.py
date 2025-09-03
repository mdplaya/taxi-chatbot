"""
GCP catalog of supported machine types, zones, and region family support.

Pure-Python constants generated from the CSV sources at repo root. No runtime
CSV reads. Helpers offer deterministic validation used by the GCE specialist.
"""

from __future__ import annotations

from typing import Dict, List, Set
import re

# Supported machine types (generated from gcp_machine_types.csv, first column)
SUPPORTED_MACHINE_TYPES: Set[str] = {
    "c3-highcpu-176",
    "c3-highcpu-22",
    "c3-highcpu-4",
    "c3-highcpu-44",
    "c3-highcpu-8",
    "c3-highcpu-88",
    "c3-highmem-176",
    "c3-highmem-22",
    "c3-highmem-4",
    "c3-highmem-44",
    "c3-highmem-8",
    "c3-highmem-88",
    "c3-standard-176",
    "c3-standard-22",
    "c3-standard-4",
    "c3-standard-44",
    "c3-standard-8",
    "c3-standard-88",
    "c3d-highcpu-16",
    "c3d-highcpu-180",
    "c3d-highcpu-30",
    "c3d-highcpu-360",
    "c3d-highcpu-4",
    "c3d-highcpu-60",
    "c3d-highcpu-8",
    "c3d-highcpu-90",
    "c3d-highmem-16",
    "c3d-highmem-180",
    "c3d-highmem-30",
    "c3d-highmem-360",
    "c3d-highmem-4",
    "c3d-highmem-60",
    "c3d-highmem-8",
    "c3d-highmem-90",
    "c3d-standard-16",
    "c3d-standard-180",
    "c3d-standard-30",
    "c3d-standard-360",
    "c3d-standard-4",
    "c3d-standard-60",
    "c3d-standard-8",
    "c3d-standard-90",
    "c4-highcpu-144",
    "c4-highcpu-16",
    "c4-highcpu-192",
    "c4-highcpu-2",
    "c4-highcpu-24",
    "c4-highcpu-288",
    "c4-highcpu-32",
    "c4-highcpu-4",
    "c4-highcpu-48",
    "c4-highcpu-8",
    "c4-highcpu-96",
    "c4-highmem-144",
    "c4-highmem-16",
    "c4-highmem-192",
    "c4-highmem-2",
    "c4-highmem-24",
    "c4-highmem-288",
    "c4-highmem-32",
    "c4-highmem-4",
    "c4-highmem-48",
    "c4-highmem-8",
    "c4-highmem-96",
    "c4-standard-144",
    "c4-standard-16",
    "c4-standard-192",
    "c4-standard-2",
    "c4-standard-24",
    "c4-standard-288",
    "c4-standard-32",
    "c4-standard-4",
    "c4-standard-48",
    "c4-standard-8",
    "c4-standard-96",
    "c4a-highcpu-1",
    "c4a-highcpu-16",
    "c4a-highcpu-2",
    "c4a-highcpu-32",
    "c4a-highcpu-4",
    "c4a-highcpu-48",
    "c4a-highcpu-64",
    "c4a-highcpu-72",
    "c4a-highcpu-8",
    "c4a-highmem-1",
    "c4a-highmem-16",
    "c4a-highmem-2",
    "c4a-highmem-32",
    "c4a-highmem-4",
    "c4a-highmem-48",
    "c4a-highmem-64",
    "c4a-highmem-72",
    "c4a-highmem-8",
    "c4a-standard-1",
    "c4a-standard-16",
    "c4a-standard-2",
    "c4a-standard-32",
    "c4a-standard-4",
    "c4a-standard-48",
    "c4a-standard-64",
    "c4a-standard-72",
    "c4a-standard-8",
    "c4d-highcpu-16",
    "c4d-highcpu-192",
    "c4d-highcpu-2",
    "c4d-highcpu-32",
    "c4d-highcpu-384",
    "c4d-highcpu-4",
    "c4d-highcpu-48",
    "c4d-highcpu-64",
    "c4d-highcpu-8",
    "c4d-highcpu-96",
    "c4d-highmem-16",
    "c4d-highmem-192",
    "c4d-highmem-2",
    "c4d-highmem-32",
    "c4d-highmem-384",
    "c4d-highmem-4",
    "c4d-highmem-48",
    "c4d-highmem-64",
    "c4d-highmem-8",
    "c4d-highmem-96",
    "c4d-standard-16",
    "c4d-standard-192",
    "c4d-standard-2",
    "c4d-standard-32",
    "c4d-standard-384",
    "c4d-standard-4",
    "c4d-standard-48",
    "c4d-standard-64",
    "c4d-standard-8",
    "c4d-standard-96",
    "e2-highcpu-16",
    "e2-highcpu-2",
    "e2-highcpu-32",
    "e2-highcpu-4",
    "e2-highcpu-8",
    "e2-highmem-16",
    "e2-highmem-2",
    "e2-highmem-4",
    "e2-highmem-8",
    "e2-medium",
    "e2-micro",
    "e2-small",
    "e2-standard-16",
    "e2-standard-2",
    "e2-standard-32",
    "e2-standard-4",
    "e2-standard-8",
    "f1-micro",
    "g1-small",
    "n1-highcpu-16",
    "n1-highcpu-2",
    "n1-highcpu-32",
    "n1-highcpu-4",
    "n1-highcpu-64",
    "n1-highcpu-8",
    "n1-highcpu-96",
    "n1-highmem-16",
    "n1-highmem-2",
    "n1-highmem-32",
    "n1-highmem-4",
    "n1-highmem-64",
    "n1-highmem-8",
    "n1-highmem-96",
    "n1-standard-1",
    "n1-standard-16",
    "n1-standard-2",
    "n1-standard-32",
    "n1-standard-4",
    "n1-standard-64",
    "n1-standard-8",
    "n1-standard-96",
    "n2-highcpu-16",
    "n2-highcpu-2",
    "n2-highcpu-32",
    "n2-highcpu-4",
    "n2-highcpu-48",
    "n2-highcpu-64",
    "n2-highcpu-8",
    "n2-highcpu-80",
    "n2-highcpu-96",
    "n2-highmem-128",
    "n2-highmem-16",
    "n2-highmem-2",
    "n2-highmem-32",
    "n2-highmem-4",
    "n2-highmem-48",
    "n2-highmem-64",
    "n2-highmem-8",
    "n2-highmem-80",
    "n2-highmem-96",
    "n2-standard-128",
    "n2-standard-16",
    "n2-standard-2",
    "n2-standard-32",
    "n2-standard-4",
    "n2-standard-48",
    "n2-standard-64",
    "n2-standard-8",
    "n2-standard-80",
    "n2-standard-96",
    "n2d-highcpu-128",
    "n2d-highcpu-16",
    "n2d-highcpu-2",
    "n2d-highcpu-224",
    "n2d-highcpu-32",
    "n2d-highcpu-4",
    "n2d-highcpu-48",
    "n2d-highcpu-64",
    "n2d-highcpu-8",
    "n2d-highcpu-80",
    "n2d-highcpu-96",
    "n2d-highmem-16",
    "n2d-highmem-2",
    "n2d-highmem-32",
    "n2d-highmem-4",
    "n2d-highmem-48",
    "n2d-highmem-64",
    "n2d-highmem-8",
    "n2d-highmem-80",
    "n2d-highmem-96",
    "n2d-standard-128",
    "n2d-standard-16",
    "n2d-standard-2",
    "n2d-standard-224",
    "n2d-standard-32",
    "n2d-standard-4",
    "n2d-standard-48",
    "n2d-standard-64",
    "n2d-standard-8",
    "n2d-standard-80",
    "n2d-standard-96",
    "n4-highcpu-16",
    "n4-highcpu-2",
    "n4-highcpu-32",
    "n4-highcpu-4",
    "n4-highcpu-48",
    "n4-highcpu-64",
    "n4-highcpu-8",
    "n4-highcpu-80",
    "n4-highmem-16",
    "n4-highmem-2",
    "n4-highmem-32",
    "n4-highmem-4",
    "n4-highmem-48",
    "n4-highmem-64",
    "n4-highmem-8",
    "n4-highmem-80",
    "n4-standard-16",
    "n4-standard-2",
    "n4-standard-32",
    "n4-standard-4",
    "n4-standard-48",
    "n4-standard-64",
    "n4-standard-8",
    "n4-standard-80",
    "t2a-standard-1",
    "t2a-standard-16",
    "t2a-standard-2",
    "t2a-standard-32",
    "t2a-standard-4",
    "t2a-standard-48",
    "t2a-standard-8",
    "t2d-standard-1",
    "t2d-standard-16",
    "t2d-standard-2",
    "t2d-standard-32",
    "t2d-standard-4",
    "t2d-standard-48",
    "t2d-standard-60",
    "t2d-standard-8",
}


# Supported zones (from gcp_regions_and_supported_machine_types.csv, "Zones" column)
SUPPORTED_ZONES: Set[str] = {
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
    "us-east1-b",
    "us-east1-c",
    "us-east1-d",
    "us-east4-a",
    "us-east4-b",
    "us-east4-c",
    "us-east5-a",
    "us-east5-b",
    "us-east5-c",
    "us-south1-a",
    "us-south1-b",
    "us-south1-c",
    "us-west1-a",
    "us-west1-b",
    "us-west1-c",
    "us-west2-a",
    "us-west2-b",
    "us-west2-c",
    "us-west3-a",
    "us-west3-b",
    "us-west3-c",
    "us-west4-a",
    "us-west4-b",
    "us-west4-c",
}


# Supported regions (derived from zones by stripping the last -<letter>)
SUPPORTED_REGIONS: Set[str] = {
    "us-central1",
    "us-east1",
    "us-east4",
    "us-east5",
    "us-south1",
    "us-west1",
    "us-west2",
    "us-west3",
    "us-west4",
}


# Region to supported families mapping (from CSV, union across the region's zones)
# Families include: E2, N4, N2, N2D, N1, C4, C4A, C4D, C3, C3D, T2D, T2A, etc.
REGION_SUPPORTED_FAMILIES: Dict[str, Set[str]] = {
    "us-central1": {"C3", "C3D", "C4", "C4A", "C4D", "E2", "N1", "N2", "N2D", "N4", "T2A", "T2D"},
    "us-east1": {"C3", "C3D", "C4", "C4A", "C4D", "E2", "N1", "N2", "N2D", "N4", "T2D"},
    "us-east4": {"C3", "C3D", "C4", "C4A", "C4D", "E2", "N1", "N2", "N2D", "N4", "T2D"},
    "us-east5": {"C3", "C3D", "C4", "E2", "N2", "N2D", "N4", "T2D"},
    "us-south1": {"A3", "C3", "C4", "E2", "N2", "N2D", "N4", "T2D"},
    "us-west1": {"C3", "C3D", "C4", "C4A", "C4D", "E2", "N1", "N2", "N2D", "N4", "T2D"},
    "us-west2": {"C3", "C3D", "C4", "E2", "N1", "N2", "N2D", "T2D"},
    "us-west3": {"C3", "C4", "E2", "N1", "N2", "N2D", "N4", "T2D"},
    "us-west4": {"C3", "C3D", "C4", "C4A", "C4D", "E2", "N1", "N2", "N2D", "T2D"},
}


def is_valid_machine_type(machine_type: str) -> bool:
    """Check if the exact machine type string is supported."""
    if machine_type is None:
        return False
    return machine_type.strip() in SUPPORTED_MACHINE_TYPES


def is_valid_zone(zone: str) -> bool:
    """Check if the exact zone string is supported (e.g., 'us-east4-a')."""
    if zone is None:
        return False
    return zone.strip() in SUPPORTED_ZONES


def parse_region(zone_or_region: str) -> str:
    """Parse a region from a full zone or return the region as-is.

    Examples:
    - 'us-east4-a' -> 'us-east4'
    - 'us-east4'   -> 'us-east4'
    """
    if not zone_or_region:
        return ""
    s = zone_or_region.strip()
    # If looks like a zone (ends with -<single letter>), strip the suffix
    if re.search(r"-[a-z]$", s):
        return s.rsplit("-", 1)[0]
    return s


def is_valid_region(region: str) -> bool:
    """Check if region is supported (e.g., 'us-east4')."""
    if region is None:
        return False
    return region.strip() in SUPPORTED_REGIONS


def machine_family(machine_type: str) -> str:
    """Return the machine family code for a machine type (uppercased).

    Examples:
    - 'n4-standard-2'   -> 'N4'
    - 'e2-small'        -> 'E2'
    - 'n2d-standard-16' -> 'N2D'
    - 'c4a-standard-4'  -> 'C4A'
    - 'c3d-standard-4'  -> 'C3D'
    """
    if not machine_type:
        return ""
    m = re.match(r"^([a-z]+\d*[a-z]?)", machine_type.strip())
    return m.group(1).upper() if m else ""


def is_family_supported_in_region(family: str, region: str) -> bool:
    """Check if a machine family (e.g., 'N4') is supported in a region (e.g., 'us-west4')."""
    if not family or not region:
        return False
    fams = REGION_SUPPORTED_FAMILIES.get(region.strip())
    return family.strip().upper() in fams if fams else False


def get_all_machine_types() -> List[str]:
    """Return all supported machine types as a sorted list."""
    return sorted(SUPPORTED_MACHINE_TYPES)


__all__ = [
    "SUPPORTED_MACHINE_TYPES",
    "SUPPORTED_ZONES",
    "SUPPORTED_REGIONS",
    "REGION_SUPPORTED_FAMILIES",
    "is_valid_machine_type",
    "is_valid_zone",
    "parse_region",
    "is_valid_region",
    "machine_family",
    "is_family_supported_in_region",
    "get_all_machine_types",
]

