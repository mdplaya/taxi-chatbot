import sys
import os
import re
import pytest

# Ensure backend package paths are importable when running this file directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.gcp_catalog import (
    is_valid_machine_type,
    is_valid_zone,
    parse_region,
    is_valid_region,
    machine_family,
    is_family_supported_in_region,
    get_all_machine_types,
    REGION_SUPPORTED_FAMILIES,
    SUPPORTED_ZONES,
    SUPPORTED_REGIONS,
    SUPPORTED_MACHINE_TYPES,
)


def test_machine_type_validation_basic():
    assert is_valid_machine_type("e2-small") is True
    assert is_valid_machine_type("n1-standard-1") is True
    assert is_valid_machine_type("e2-notreal") is False
    assert is_valid_machine_type("") is False


def test_zone_and_region_validation():
    # Known good zone
    assert is_valid_zone("us-east4-a") is True
    # Known bad zone
    assert is_valid_zone("us-mars1-a") is False

    # Parse region from zone
    assert parse_region("us-east4-a") == "us-east4"
    # Already a region stays the same
    assert parse_region("us-east4") == "us-east4"
    # Empty input
    assert parse_region("") == ""

    # Known regions
    assert is_valid_region("us-east4") is True
    assert is_valid_region("us-west2") is True
    # Invalid region
    assert is_valid_region("us-mars1") is False


def test_machine_family_extraction():
    assert machine_family("n4-standard-2") == "N4"
    assert machine_family("e2-small") == "E2"
    assert machine_family("n2d-standard-16") == "N2D"
    assert machine_family("c4a-standard-4") == "C4A"
    assert machine_family("c3d-standard-60") == "C3D"
    assert machine_family("") == ""


def test_family_supported_in_region_matrix():
    # us-west2 supports E2 but not N4 per REGION_SUPPORTED_FAMILIES
    assert is_family_supported_in_region("E2", "us-west2") is True
    assert is_family_supported_in_region("N4", "us-west2") is False

    # us-west1 supports N4 (per mapping)
    assert is_family_supported_in_region("N4", "us-west1") is True

    # Unknown family/region combos
    assert is_family_supported_in_region("XYZ", "us-west1") is False
    assert is_family_supported_in_region("E2", "us-mars1") is False


def test_get_all_machine_types_includes_common_values():
    mts = get_all_machine_types()
    assert isinstance(mts, list)
    assert len(mts) > 0
    # Common types present in our catalog
    assert "e2-small" in mts
    assert "n1-standard-1" in mts


@pytest.mark.parametrize("zone", sorted(SUPPORTED_ZONES))
def test_parse_region_matches_supported_zones(zone):
    assert is_valid_zone(zone)
    region = parse_region(zone)
    assert region in SUPPORTED_REGIONS
    assert is_valid_region(region)


# Build exhaustive positive region/family pairs
positive_pairs = [
    (region, fam)
    for region, fams in REGION_SUPPORTED_FAMILIES.items()
    for fam in sorted(fams)
]

@pytest.mark.parametrize("region,family", positive_pairs)
def test_region_family_positive_pairs(region, family):
    assert is_family_supported_in_region(family, region) is True


# Build negative pairs by taking families supported in other regions but not this one
all_families = set().union(*REGION_SUPPORTED_FAMILIES.values())
negative_pairs = []
for region, fams in REGION_SUPPORTED_FAMILIES.items():
    missing = sorted(all_families - fams)
    for fam in missing:
        negative_pairs.append((region, fam))

@pytest.mark.parametrize("region,family", negative_pairs)
def test_region_family_negative_pairs(region, family):
    assert is_family_supported_in_region(family, region) is False


@pytest.mark.parametrize(
    "mt,expected_prefix",
    [
        ("e2-small", "E2"),
        ("n1-standard-1", "N1"),
        ("n2d-standard-16", "N2D"),
        ("c4a-standard-4", "C4A"),
        ("c3d-standard-8", "C3D"),
        ("f1-micro", "F1"),
        ("g1-small", "G1"),
    ],
)
def test_machine_family_known_examples(mt, expected_prefix):
    assert machine_family(mt) == expected_prefix


@pytest.mark.parametrize("mt", sorted(list(SUPPORTED_MACHINE_TYPES)))
def test_is_valid_machine_type_for_entire_catalog(mt):
    # Validate every supported machine type
    assert is_valid_machine_type(mt) is True


@pytest.mark.parametrize("mt", sorted(list(SUPPORTED_MACHINE_TYPES)))
def test_machine_family_for_entire_catalog(mt):
    # Derive expected prefix independently via regex and compare
    m = re.match(r"^([a-z]+\d*[a-z]?)", mt)
    assert m is not None, f"Unexpected machine type format: {mt}"
    expected = m.group(1).upper()
    fam = machine_family(mt)
    # Must be uppercase alphanumeric and start with a letter
    assert re.match(r"^[A-Z][A-Z0-9]*$", fam), f"Bad family format for {mt}: {fam}"
    assert fam == expected


def test_every_observed_family_exists_in_region_map():
    observed_families = {machine_family(mt) for mt in SUPPORTED_MACHINE_TYPES}
    union_families = set().union(*REGION_SUPPORTED_FAMILIES.values())
    missing = observed_families - union_families
    assert not missing, f"Observed families missing from region map: {sorted(missing)}"


@pytest.mark.parametrize("family", sorted({machine_family(mt) for mt in SUPPORTED_MACHINE_TYPES}))
def test_each_observed_family_present_in_at_least_one_region(family):
    assert any(
        family in fams for fams in REGION_SUPPORTED_FAMILIES.values()
    ), f"Family {family} not present in any region"
