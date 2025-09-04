import sys
import os
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest


@pytest.mark.asyncio
async def test_business_group_asked_first(monkeypatch):
    agent = ClarificationAgent()
    vm = VMRequest()

    # Ensure multiple fields are missing across groups
    # Only set OS to simulate "Create a Linux server for development" partially
    vm.os = None

    captured_fields = {}

    async def fake_generate(missing_fields, vm_request, context):
        captured_fields['fields'] = list(missing_fields)
        # Return stub questions for those fields
        return [{"field": f, "question": f"{f}?", "description": ""} for f in missing_fields]

    monkeypatch.setattr(agent, "_generate_natural_questions", fake_generate)

    # Invoke get_clarifications with empty context
    result = await agent.get_clarifications(vm, {"raw_request": "", "conversation_history": [], "session_id": "t"})

    # Business fields include these; since VM is empty, the first group is Business
    business = {"lineOfBusiness", "id", "appEnvironment", "appEnvironmentSubtype", "costCenter"}
    assert set(captured_fields['fields']).issubset(business)
    assert result["complete"] is False
    assert isinstance(result.get("questions"), list)

