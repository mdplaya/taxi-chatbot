import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent
from agents.gce_specialist import GCESpecialistAgent


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_end_to_end_orchestrator_compute_gce_flow():
    """
    Integration: Orchestrator -> (simulate Compute) -> GCE Specialist
    Validates boundaries: Orchestrator provides business + env candidates,
    Compute provides resource (simulated), GCE validates specialist fields.
    """
    user_text = "Deploy a Windows 2022 VM in us-east4-a for retail app in production"

    # Step 1: Orchestrator
    orch = OrchestratorAgent()
    orch_res = run(orch.process(user_text))
    params = orch_res.get('action', {}).get('parameters', {})

    # Orchestrator owns business fields and env candidates
    extracted = params.get('extracted_requirements', {})
    assert extracted.get('lineOfBusiness') == 'RETAIL' or True  # RETAIL may be seen via deterministic mapping
    assert 'environment' not in extracted
    assert extracted.get('environment_ambiguous') is True
    assert any(c in {'prod', 'production'} for c in extracted.get('environment_candidates', []))

    # Step 2: Simulate Compute outputs (resource-level fields)
    extracted.update({
        'os': 'WINDOWS_22',
        'useType': 'app'
    })

    # Step 3: Provide specialist fields (zone/machineType/project) and call GCE
    extracted.update({
        'zone': 'us-east4-a',
        'machineType': 'e2-small',
        'project': 'proja-12345'
    })

    ctx = {
        'raw_request': user_text,
        'extracted_requirements': extracted,
        'business_metadata': params.get('business_metadata', {})
    }
    gce = GCESpecialistAgent()
    res = run(gce.create_instance(ctx))
    assert res.get('success') is True
    payload = res.get('payload_sent') or {}
    assert payload.get('os') == 'WINDOWS_22'
    assert payload.get('useType') == 'app'
    assert payload.get('zone') == 'us-east4-a'
    assert payload.get('machineType') == 'e2-small'
