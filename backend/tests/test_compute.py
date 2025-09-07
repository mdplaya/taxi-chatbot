import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent
from agents.gce_specialist import GCESpecialistAgent
import asyncio


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def extract_with_orchestrator(text: str) -> dict:
    agent = OrchestratorAgent()
    return run_async(agent.process(text))


class TestExtractionViaOrchestrator:
    def _extracted(self, text: str) -> dict:
        res = extract_with_orchestrator(text)
        if not isinstance(res, dict):
            return {}
        # Prefer action.parameters.extracted_requirements if present
        action = res.get('action') or {}
        params = action.get('parameters') or {}
        if 'extracted_requirements' in params:
            return params.get('extracted_requirements', {})
        # Fallback to top-level context for older structures
        return res.get('context', {}).get('extracted_requirements', {})

    def test_development_environment(self):
        extracted = self._extracted("I need a VM for development")
        assert 'environment' not in extracted
        assert extracted.get('environment_ambiguous') is True
        assert 'dev' in set(extracted.get('environment_candidates') or [])

    def test_production_environment(self):
        extracted = self._extracted("Deploy a production server")
        assert 'environment' not in extracted
        assert extracted.get('environment_ambiguous') is True
        cands = set(extracted.get('environment_candidates') or [])
        assert ('prod' in cands) or ('production' in cands)

    def test_windows_22_detection(self):
        # Refactor: validate GCE uses provided technical fields
        ctx = {
            'raw_request': 'Create a Windows 2022 VM',
            'extracted_requirements': {
                'os': 'WINDOWS_22',
                'machineType': 'e2-small',
                'zone': 'us-east4-a',
                'project': 'proja-12345'
            },
            'business_metadata': {}
        }
        gce = GCESpecialistAgent()
        res = run_async(gce.create_instance(ctx))
        assert res.get('success') is True
        payload = res.get('payload_sent') or {}
        assert payload.get('os') == 'WINDOWS_22'

    def test_windows_19_detection(self):
        ctx = {
            'raw_request': 'Need a Windows 2019 server',
            'extracted_requirements': {
                'os': 'WINDOWS_19',
                'machineType': 'n1-standard-1',
                'zone': 'us-east4-a',
                'project': 'proja-12345'
            },
            'business_metadata': {}
        }
        gce = GCESpecialistAgent()
        res = run_async(gce.create_instance(ctx))
        assert res.get('success') is True
        assert res.get('payload_sent', {}).get('os') == 'WINDOWS_19'

    def test_linux_rhel8_detection(self):
        ctx = {
            'raw_request': 'Set up a Linux RHEL8 instance',
            'extracted_requirements': {
                'os': 'LINUX_RHEL8',
                'machineType': 'n1-standard-1',
                'zone': 'us-east4-a',
                'project': 'proja-12345'
            },
            'business_metadata': {}
        }
        res = run_async(GCESpecialistAgent().create_instance(ctx))
        assert res.get('success') is True
        assert res.get('payload_sent', {}).get('os') == 'LINUX_RHEL8'

    def test_linux_rhel9_detection(self):
        ctx = {
            'raw_request': 'Deploy RHEL 9 server',
            'extracted_requirements': {
                'os': 'LINUX_RHEL9',
                'machineType': 'n1-standard-1',
                'zone': 'us-east4-a',
                'project': 'proja-12345'
            },
            'business_metadata': {}
        }
        res = run_async(GCESpecialistAgent().create_instance(ctx))
        assert res.get('success') is True
        assert res.get('payload_sent', {}).get('os') == 'LINUX_RHEL9'

    def test_database_use_type(self):
        # Resource field asserted downstream in GCE payload when provided
        ctx = {
            'raw_request': 'VM for our database server',
            'extracted_requirements': {
                'useType': 'database',
                'os': 'LINUX_RHEL9',
                'machineType': 'n1-standard-1',
                'zone': 'us-east4-a',
                'project': 'proja-12345'
            },
            'business_metadata': {}
        }
        res = run_async(GCESpecialistAgent().create_instance(ctx))
        assert res.get('success') is True
        assert res.get('payload_sent', {}).get('useType') == 'database'

    def test_app_use_type(self):
        ctx = {
            'raw_request': 'Server for our web application',
            'extracted_requirements': {
                'useType': 'app',
                'os': 'LINUX_RHEL9',
                'machineType': 'n1-standard-1',
                'zone': 'us-east4-a',
                'project': 'proja-12345'
            },
            'business_metadata': {}
        }
        res = run_async(GCESpecialistAgent().create_instance(ctx))
        assert res.get('success') is True
        assert res.get('payload_sent', {}).get('useType') == 'app'

    def test_machine_type_n1_standard(self):
        ctx = {
            'raw_request': 'Create VM with n1-standard-2 machine type',
            'extracted_requirements': {
                'machineType': 'n1-standard-2',
                'zone': 'us-east4-a',
                'os': 'LINUX_RHEL9',
                'project': 'proja-12345'
            },
            'business_metadata': {}
        }
        res = run_async(GCESpecialistAgent().create_instance(ctx))
        assert res.get('success') is True
        assert res.get('payload_sent', {}).get('machineType') == 'n1-standard-2'

    def test_machine_type_n2_standard(self):
        ctx = {
            'raw_request': 'Need n2-standard-4 instance',
            'extracted_requirements': {
                'machineType': 'n2-standard-4',
                'zone': 'us-east4-a',
                'os': 'LINUX_RHEL9',
                'project': 'proja-12345'
            },
            'business_metadata': {}
        }
        res = run_async(GCESpecialistAgent().create_instance(ctx))
        assert res.get('success') is True
        assert res.get('payload_sent', {}).get('machineType') == 'n2-standard-4'

    def test_zone_detection(self):
        ctx = {
            'raw_request': 'Deploy VM in us-east4-a zone',
            'extracted_requirements': {
                'zone': 'us-east4-a',
                'machineType': 'n1-standard-1',
                'os': 'LINUX_RHEL9',
                'project': 'proja-12345'
            },
            'business_metadata': {}
        }
        res = run_async(GCESpecialistAgent().create_instance(ctx))
        assert res.get('success') is True
        assert res.get('payload_sent', {}).get('zone') == 'us-east4-a'

    def test_retail_line_of_business(self):
        extracted = self._extracted("VM for retail application")
        assert extracted.get('lineOfBusiness') == 'RETAIL'

    def test_ists_line_of_business(self):
        extracted = self._extracted("Server for ISTS team")
        assert extracted.get('lineOfBusiness') == 'ISTS'

    def test_edml_line_of_business(self):
        extracted = self._extracted("Create instance for EDML project")
        assert extracted.get('lineOfBusiness') == 'EDML'

    def test_complex_request(self):
        # Orchestrator supplies business; technical fields validated by GCE
        ctx = {
            'raw_request': 'Deploy a Windows 2022 VM in us-east4-a for retail app in production',
            'extracted_requirements': {
                'os': 'WINDOWS_22',
                'useType': 'app',
                'zone': 'us-east4-a',
                'machineType': 'e2-small',
                'project': 'proja-12345',
                'lineOfBusiness': 'RETAIL'
            },
            'business_metadata': {'lineOfBusiness': 'RETAIL'}
        }
        res = run_async(GCESpecialistAgent().create_instance(ctx))
        assert res.get('success') is True
        payload = res.get('payload_sent', {})
        assert payload.get('os') == 'WINDOWS_22'
        assert payload.get('zone') == 'us-east4-a'
        assert payload.get('machineType') == 'e2-small'

    def test_partial_requirements(self):
        extracted = self._extracted("I need a Linux server")
        # Orchestrator no longer extracts OS; ensure it didn't guess
        assert 'os' not in extracted or extracted.get('os') is None
        assert 'environment' not in extracted
        assert 'zone' not in extracted or isinstance(extracted.get('zone'), str)

    def test_staging_is_nonprod(self):
        extracted = self._extracted("Deploy to staging environment")
        assert 'environment' not in extracted
        cands = set(extracted.get('environment_candidates') or [])
        assert 'staging' in cands

    def test_case_insensitive_detection(self):
        extracted = self._extracted("DEPLOY A WINDOWS VM FOR RETAIL IN PROD")
        # Orchestrator handles LoB and env candidates only
        assert extracted.get('lineOfBusiness') == 'RETAIL'
        assert 'environment' not in extracted
        cands = set(extracted.get('environment_candidates') or [])
        assert 'prod' in cands or 'production' in cands
