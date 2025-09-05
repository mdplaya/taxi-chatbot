import os
import sys
import pytest

# Ensure backend package is on PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest


import asyncio

def test_lob_guess_high_confidence(monkeypatch):
    agent = ClarificationAgent()

    async def fake_reason(prompt: str, system_prompt: str = None):
        # Simulate a strong RETAIL signal
        return {"lineOfBusiness": "RETAIL", "confidence": 0.9, "evidence": "mentions retail"}

    # Patch the agent's reason call to avoid network
    monkeypatch.setattr(agent, "reason", fake_reason)

    vm = VMRequest()
    ctx = {
        "raw_request": "Deploy Windows Server 2022 VM in us-east4-a for retail production"
    }
    result = asyncio.run(agent.get_clarifications(vm, ctx))

    state = result.get("current_state", {})
    assert state.get("lineOfBusiness") == "RETAIL", "LOB should be set from high-confidence guess"

    # LOB should not be asked once inferred
    fields = [q.get("field") for q in result.get("questions", []) if isinstance(q, dict)]
    assert "lineOfBusiness" not in fields


def test_lob_guess_low_confidence(monkeypatch):
    agent = ClarificationAgent()

    async def fake_reason(prompt: str, system_prompt: str = None):
        # Low confidence: should not auto-set
        return {"lineOfBusiness": "RETAIL", "confidence": 0.4, "evidence": "weak signal"}

    monkeypatch.setattr(agent, "reason", fake_reason)

    vm = VMRequest()
    ctx = {
        "raw_request": "Deploy Windows Server 2022 VM in us-east4-a for retail production"
    }
    result = asyncio.run(agent.get_clarifications(vm, ctx))

    state = result.get("current_state", {})
    assert state.get("lineOfBusiness") is None, "LOB should remain unset under threshold"

    # In offline mode, question generation may return an empty list.
    # The key expectation for low confidence is that LOB is not auto-set.
    # If questions are generated, LOB may or may not be included depending on ordering.
    # So we only assert the state is unset here.
