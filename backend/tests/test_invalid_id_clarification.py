import pytest
import sys, os

# Ensure backend package paths are importable when running this file directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.gce_specialist import GCESpecialistAgent


@pytest.mark.asyncio
async def test_invalid_id_triggers_clarification():
    agent = GCESpecialistAgent()

    # Provide a complete VM request but with invalid id (not an email)
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
        "id": "vm-instance",  # invalid email
    }

    context = {"vm_request": vm_request}
    result = await agent.create_instance(context)

    # Should request clarification specifically for the 'id' field
    assert isinstance(result, dict)
    assert result.get("needs_clarification") is True
    missing = set(result.get("missing_fields", []))
    assert "id" in missing
    q_fields = {q.get("field") for q in result.get("questions", []) if isinstance(q, dict)}
    assert "id" in q_fields

