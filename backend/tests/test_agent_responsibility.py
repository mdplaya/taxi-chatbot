import asyncio
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent
from agents.compute import ComputeAgent
from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def orchestrator_extracted(text: str) -> dict:
    agent = OrchestratorAgent()
    res = run(agent.process(text))
    return res.get('action', {}).get('parameters', {}).get('extracted_requirements', {})


class TestBusinessOwnership:
    def test_deterministic_business_fields_but_env_is_candidates(self):
        text = (
            "Deploy a Windows 2022 VM in us-east4-a for retail production "
            "cost center 12345; contact user+tag@example.com"
        )
        extracted = orchestrator_extracted(text)
        # Deterministic business fields
        assert extracted.get('lineOfBusiness') == 'RETAIL'
        assert extracted.get('costCenter') == '12345'
        assert extracted.get('id') == 'user+tag@example.com'
        # appEnvironment/appEnvironmentSubtype are NON-deterministic: no direct set
        assert 'environment' not in extracted
        assert extracted.get('environment_ambiguous') is True
        candidates = extracted.get('environment_candidates') or []
        # Should include a signal for production/prod
        assert any(c in {'prod', 'production'} for c in candidates)

    @pytest.mark.parametrize(
        'text, expected_label',
        [
            ("performance environment", 'perf'),
            ("SIT testing box", 'sit'),
            ("UAT VM needed", 'uat'),
            ("staging server", 'staging'),
        ],
    )
    def test_nonprod_synonym_candidates_only(self, text, expected_label):
        extracted = orchestrator_extracted(text)
        assert 'environment' not in extracted
        assert extracted.get('environment_ambiguous') is True
        candidates = set(extracted.get('environment_candidates') or [])
        assert expected_label in candidates


class TestAgentScopes:
    def test_compute_outputs_only_resource_fields(self):
        ctx = {"raw_request": "retail prod 12345 user@example.com e2-small linux app"}
        comp = ComputeAgent()
        res = run(comp.process(ctx))
        vm = res.get('vm_request', {})
        # Must not include business fields
        for k in [
            'environment', 'lineOfBusiness', 'costCenter', 'id',
            'appEnvironment', 'appEnvironmentSubtype'
        ]:
            assert k not in vm

    def test_clarification_asks_env_not_guess(self):
        clar = ClarificationAgent()
        vm = VMRequest()
        ctx = {'raw_request': 'prod box'}
        res = run(clar.get_clarifications(vm, ctx))
        # Should not set lineOfBusiness or environment deterministically
        current = res.get('current_state', {})
        assert current.get('lineOfBusiness') is None
        # In offline mode, LLM may not generate questions; just ensure it didn't guess
        assert res.get('complete') is not True
