import pytest
import sys, os

# Ensure backend package paths are importable when running this file directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.gce_specialist import GCESpecialistAgent


def test_payload_builder_requests_clarification_for_zone_and_machine_type():
    agent = GCESpecialistAgent()

    # Minimal technical + business fields, missing zone and machineType
    vm_request = {
        "appEnvironment": "NONPROD",
        "appEnvironmentSubtype": "dev",
        "os": "LINUX_RHEL9",
        "useType": "app",
        # missing: machineType, zone
        "lineOfBusiness": "RETAIL",
        "costCenter": "12345",
        "project": "my-gcp-project",
        "id": "user@example.com",
    }

    result = agent._build_taxi_payload(vm_request)

    assert isinstance(result, dict)
    assert result.get("needs_clarification") is True
    missing = set(result.get("missing_fields", []))
    assert "machineType" in missing
    assert "zone" in missing
    # Should include targeted questions
    questions = result.get("questions", [])
    q_fields = {q.get("field") for q in questions if isinstance(q, dict)}
    assert "machineType" in q_fields
    assert "zone" in q_fields


def test_payload_builder_no_defaults_when_complete():
    agent = GCESpecialistAgent()

    vm_request = {
        "appEnvironment": "NONPROD",
        "appEnvironmentSubtype": "dev",
        "os": "LINUX_RHEL9",
        "useType": "app",
        "machineType": "e2-small",
        "zone": "us-east4-a",
        "lineOfBusiness": "RETAIL",
        "costCenter": "12345",
        "project": "my-gcp-project",
        "id": "user@example.com",
    }

    payload = agent._build_taxi_payload(vm_request)
    assert payload.get("cloud") == "gcp"
    assert payload.get("machineType") == "e2-small"
    assert payload.get("zone") == "us-east4-a"
    # No needs_clarification in success payload
    assert not payload.get("needs_clarification")


def test_payload_builder_rejects_invalid_machine_type():
    agent = GCESpecialistAgent()

    vm_request = {
        "appEnvironment": "NONPROD",
        "appEnvironmentSubtype": "dev",
        "os": "LINUX_RHEL9",
        "useType": "app",
        "machineType": "e2-notreal",  # invalid
        "zone": "us-east4-a",  # valid zone
        "lineOfBusiness": "RETAIL",
        "costCenter": "12345",
        "project": "my-gcp-project",
        "id": "user@example.com",
    }

    result = agent._build_taxi_payload(vm_request)
    assert isinstance(result, dict)
    assert result.get("needs_clarification") is True
    q_fields = {q.get("field") for q in result.get("questions", []) if isinstance(q, dict)}
    assert "machineType" in q_fields


def test_payload_builder_rejects_invalid_zone():
    agent = GCESpecialistAgent()

    vm_request = {
        "appEnvironment": "NONPROD",
        "appEnvironmentSubtype": "dev",
        "os": "LINUX_RHEL9",
        "useType": "app",
        "machineType": "e2-small",  # valid
        "zone": "us-mars1-a",  # invalid zone
        "lineOfBusiness": "RETAIL",
        "costCenter": "12345",
        "project": "my-gcp-project",
        "id": "user@example.com",
    }

    result = agent._build_taxi_payload(vm_request)
    assert isinstance(result, dict)
    assert result.get("needs_clarification") is True
    q_fields = {q.get("field") for q in result.get("questions", []) if isinstance(q, dict)}
    assert "zone" in q_fields


def test_payload_builder_rejects_unsupported_family_in_region():
    agent = GCESpecialistAgent()

    # N4 family is not listed for the us-west2 region in regions CSV
    vm_request = {
        "appEnvironment": "NONPROD",
        "appEnvironmentSubtype": "dev",
        "os": "LINUX_RHEL9",
        "useType": "app",
        "machineType": "n4-standard-2",  # valid type overall
        "zone": "us-west2-a",  # region without N4 support
        "lineOfBusiness": "RETAIL",
        "costCenter": "12345",
        "project": "my-gcp-project",
        "id": "user@example.com",
    }

    result = agent._build_taxi_payload(vm_request)
    assert isinstance(result, dict)
    assert result.get("needs_clarification") is True
    q_fields = {q.get("field") for q in result.get("questions", []) if isinstance(q, dict)}
    assert "machineType" in q_fields


## Legacy validation path (CSV-based) removed; catalog-based tests cover validation behavior
