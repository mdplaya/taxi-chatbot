import asyncio
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent
from agents.clarification import ClarificationAgent
from agents.gce_specialist import GCESpecialistAgent
from models.taxi_models import VMRequest
from backend.tests.utils import add_resource_fields


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.mark.parametrize('phrase, subtype', [
    ('dev environment', 'dev'),
    ('QA testing', 'qa'),
    ('test server', 'test'),
    ('perf testing', 'perf'),
])
def test_env_candidates_and_confirmation_flow(phrase, subtype):
    # Step 1: Orchestrator surfaces environment candidates only
    orch = OrchestratorAgent()
    orch_res = run(orch.process(phrase))
    params = orch_res.get('action', {}).get('parameters', {})
    extracted = params.get('extracted_requirements', {})
    assert 'environment' not in extracted
    assert extracted.get('environment_ambiguous') is True
    assert subtype in set(extracted.get('environment_candidates') or [])

    # Step 2: Clarification asks questions (fallback if offline), we answer
    clar = ClarificationAgent()
    vm = VMRequest()
    # Generate questions to ensure agent path runs; we won't assert phrasing here
    _ = run(clar.get_clarifications(vm, {'raw_request': phrase}))

    answers = {
        'appEnvironment': 'NONPROD',
        'appEnvironmentSubtype': subtype,
        'lineOfBusiness': 'RETAIL',
        'costCenter': '12345',
        'id': 'user@example.com',
    }
    vm2 = run(clar.process_answers(vm, answers))
    assert str(vm2.appEnvironment) == 'AppEnvironment.NONPROD' or vm2.appEnvironment.value == 'NONPROD'
    assert vm2.appEnvironmentSubtype.value == subtype
    assert vm2.lineOfBusiness.value == 'RETAIL'
    assert vm2.costCenter == '12345'

    # Step 3: Simulate Compute outputs and call GCE Specialist
    ctx = {
        'raw_request': phrase,
        'extracted_requirements': {
            'project': 'proja-12345',
            'zone': 'us-east4-a',
            'machineType': 'e2-small',
        },
        'business_metadata': {
            'lineOfBusiness': 'RETAIL',
            'costCenter': '12345',
            'id': 'user@example.com'
        }
    }
    ctx = add_resource_fields(ctx, 'LINUX_RHEL9', 'app')
    gce = GCESpecialistAgent()
    res = run(gce.create_instance(ctx))
    assert res.get('success') is True
    payload = res.get('payload_sent') or {}
    assert payload.get('zone') == 'us-east4-a'
    assert payload.get('machineType') == 'e2-small'
    assert payload.get('os') == 'LINUX_RHEL9'
    assert payload.get('useType') == 'app'

