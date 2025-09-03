#!/usr/bin/env python3
"""
Dev-only utility to regenerate backend/utils/gcp_catalog.py constants from CSVs.

Usage:
  python automation/gen_gcp_catalog.py \
    --machine-types gcp_machine_types.csv \
    --regions gcp_regions_and_supported_machine_types.csv \
    --out backend/utils/gcp_catalog.py

Notes:
- This script is not used at runtime. It exists to keep the in-code catalog
  maintainable. Commit the generated Python file to source control.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set


def read_machine_types(path: Path) -> List[str]:
    types: Set[str] = set()
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            if not row:
                continue
            mt = (row[0] or "").strip()
            if not mt:
                continue
            if mt.lower() == "machine types":
                continue
            types.add(mt)
    return sorted(types)


def read_regions_and_families(path: Path):
    zones: Set[str] = set()
    region_families: Dict[str, Set[str]] = defaultdict(set)
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            if not row:
                continue
            zone = (row[0] or "").strip()
            if not zone or zone.lower() == "zones":
                continue
            zones.add(zone)
            region = re.sub(r"-[a-z]$", "", zone)
            fams_raw = (row[2] or "").strip()
            for ch in ["\u200a", "\u2009", "\u200b", "\xa0"]:
                fams_raw = fams_raw.replace(ch, " ")
            fams = [x.strip().upper() for x in fams_raw.split(",") if x.strip()]
            fams = [re.sub(r"[^A-Z0-9]+$", "", x) for x in fams]
            for fam in fams:
                if fam:
                    region_families[region].add(fam)

    regions = sorted({re.sub(r"-[a-z]$", "", z) for z in zones})
    return sorted(zones), regions, {k: sorted(v) for k, v in sorted(region_families.items())}


TEMPLATE = """"""
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
{machine_types}
}


# Supported zones (from gcp_regions_and_supported_machine_types.csv, "Zones" column)
SUPPORTED_ZONES: Set[str] = {
{zones}
}


# Supported regions (derived from zones by stripping the last -<letter>)
SUPPORTED_REGIONS: Set[str] = {
{regions}
}


# Region to supported families mapping (from CSV, union across the region's zones)
# Families include: E2, N4, N2, N2D, N1, C4, C4A, C4D, C3, C3D, T2D, T2A, etc.
REGION_SUPPORTED_FAMILIES: Dict[str, Set[str]] = {{
{region_families}
}}


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
"""


def _fmt_set(items: List[str]) -> str:
    return ",\n".join(f"    {item!r}" for item in items)


def _fmt_region_map(d: Dict[str, List[str]]) -> str:
    lines = []
    for region, fams in d.items():
        fams_s = ", ".join(repr(x) for x in fams)
        lines.append(f"    {region!r}: {{{fams_s}}},")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine-types", type=Path, required=True)
    ap.add_argument("--regions", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    mts = read_machine_types(args.machine_types)
    zones, regions, region_fams = read_regions_and_families(args.regions)

    code = TEMPLATE.format(
        machine_types=_fmt_set(mts),
        zones=_fmt_set(zones),
        regions=_fmt_set(regions),
        region_families=_fmt_region_map(region_fams),
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(code, encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()

