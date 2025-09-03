import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent
import asyncio


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def extract_with_orchestrator(text: str) -> dict:
    agent = OrchestratorAgent()
    return run_async(agent.process(text))


class TestExtractionViaOrchestrator:
    def _extracted(self, text: str) -> dict:
        res = extract_with_orchestrator(text)
        return res.get('context', {}).get('extracted_requirements', {}) if isinstance(res, dict) else {}

    def test_development_environment(self):
        extracted = self._extracted("I need a VM for development")
        assert extracted.get('environment') == 'NONPROD'
        assert extracted.get('appEnvironmentSubtype') == 'dev'

    def test_production_environment(self):
        extracted = self._extracted("Deploy a production server")
        assert extracted.get('environment') == 'PROD'

    def test_windows_22_detection(self):
        extracted = self._extracted("Create a Windows 2022 VM")
        assert extracted.get('os') == 'WINDOWS_22'

    def test_windows_19_detection(self):
        extracted = self._extracted("Need a Windows 2019 server")
        assert extracted.get('os') == 'WINDOWS_19'

    def test_linux_rhel8_detection(self):
        extracted = self._extracted("Set up a Linux RHEL8 instance")
        assert extracted.get('os') == 'LINUX_RHEL8'

    def test_linux_rhel9_detection(self):
        extracted = self._extracted("Deploy RHEL 9 server")
        assert extracted.get('os') == 'LINUX_RHEL9'

    def test_database_use_type(self):
        extracted = self._extracted("VM for our database server")
        assert extracted.get('use_type') == 'database'

    def test_app_use_type(self):
        extracted = self._extracted("Server for our web application")
        assert extracted.get('use_type') == 'app'

    def test_machine_type_n1_standard(self):
        extracted = self._extracted("Create VM with n1-standard-2 machine type")
        assert extracted.get('machine_type') == 'n1-standard-2'

    def test_machine_type_n2_standard(self):
        extracted = self._extracted("Need n2-standard-4 instance")
        assert extracted.get('machine_type') == 'n2-standard-4'

    def test_zone_detection(self):
        extracted = self._extracted("Deploy VM in us-east4-a zone")
        assert extracted.get('zone') == 'us-east4-a'

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
        extracted = self._extracted(
            "Deploy a Windows 2022 VM in us-east4-a for retail app in production"
        )
        assert extracted.get('os') == 'WINDOWS_22'
        assert extracted.get('zone') == 'us-east4-a'
        assert extracted.get('lineOfBusiness') == 'RETAIL'
        assert extracted.get('use_type') == 'app'
        assert extracted.get('environment') == 'PROD'

    def test_partial_requirements(self):
        extracted = self._extracted("I need a Linux server")
        assert extracted.get('os') == 'LINUX_RHEL9'  # Default Linux
        # No environment or zone guaranteed from this input
        assert 'environment' not in extracted or extracted.get('environment') in ['PROD', 'NONPROD']
        assert 'zone' not in extracted or isinstance(extracted.get('zone'), str)

    def test_staging_is_nonprod(self):
        extracted = self._extracted("Deploy to staging environment")
        assert extracted.get('environment') == 'NONPROD'

    def test_case_insensitive_detection(self):
        extracted = self._extracted("DEPLOY A WINDOWS VM FOR RETAIL IN PROD")
        assert extracted.get('os') == 'WINDOWS_22'
        assert extracted.get('lineOfBusiness') == 'RETAIL'
        assert extracted.get('environment') == 'PROD'
