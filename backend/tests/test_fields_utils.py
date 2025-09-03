import sys
import os

# Ensure backend package is on path when running from repo root
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.fields import sanitize_answers, canonical_vm_fields


def test_sanitize_maps_machine_type_from_ambiguous_key():
    out = sanitize_answers({"which": "n1-standard-4"})
    assert out == {"machineType": "n1-standard-4"}


def test_sanitize_maps_zone_from_ambiguous_key():
    out = sanitize_answers({"which": "us-east4-a"})
    assert out == {"zone": "us-east4-a"}


def test_sanitize_preserves_canonical_keys():
    inp = {"machineType": "e2-small", "project": "my-project"}
    out = sanitize_answers(inp)
    assert out == inp


def test_sanitize_drops_unknown_when_value_not_valid():
    # Not an exact valid machine type or zone; should be dropped
    out = sanitize_answers({"type": "n1 standard 4gb"})
    assert out == {}


def test_canonical_vm_fields_contains_core_names():
    fields = canonical_vm_fields()
    assert "machineType" in fields
    assert "zone" in fields
    assert "project" in fields

