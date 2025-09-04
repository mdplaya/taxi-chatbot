import sys
import os
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest


@pytest.mark.asyncio
async def test_machine_type_invalid_raises_no_autosalvage():
    agent = ClarificationAgent()
    vm = VMRequest()

    with pytest.raises(ValueError):
        await agent.process_answers(vm, {"machineType": "n1-standard-72323"})


@pytest.mark.asyncio
async def test_machine_type_valid_is_set():
    agent = ClarificationAgent()
    vm = VMRequest()

    updated = await agent.process_answers(vm, {"machineType": "n1-standard-2"})
    assert updated.machineType == "n1-standard-2"

