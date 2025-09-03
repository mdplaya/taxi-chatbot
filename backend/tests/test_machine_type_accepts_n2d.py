import pytest
import sys
import os

# Ensure backend package is on path when running from repo root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest


@pytest.mark.asyncio
async def test_accepts_normalized_n2d_standard_16():
    """Clarification should accept a valid normalized machineType string."""
    agent = ClarificationAgent()
    vm_request = VMRequest()

    # Provide already-normalized, valid GCP machine type
    answers = {"machineType": "n2d-standard-16"}

    # Should not raise; should set machineType to the provided string
    updated = await agent.process_answers(vm_request, answers)
    assert updated.machineType == "n2d-standard-16"
