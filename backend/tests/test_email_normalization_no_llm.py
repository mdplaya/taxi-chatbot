import os
import sys
import pytest

# Ensure backend package is on PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest


def test_email_normalization_bypasses_llm(monkeypatch):
    agent = ClarificationAgent()

    # If reason() were called, this will raise and fail the test
    async def boom(prompt: str, system_prompt: str = None):
        raise RuntimeError("LLM should not be called for email normalization")

    monkeypatch.setattr(agent, "reason", boom)

    vm = VMRequest()
    # Directly test normalization path to avoid pydantic EmailStr dependency in assignment
    normalized = __import__("asyncio").run(agent._normalize_value("id", "user@example.com", vm))
    assert normalized == "user@example.com"
