import pytest
import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestOrchestratorProcess:
    def _route(self, text: str) -> dict:
        agent = OrchestratorAgent()
        return run_async(agent.process(text))

    def test_gcp_vm_request(self):
        res = self._route("I want a VM in GCP")
        assert res.get('next_agent') in ["compute", "gce_specialist", "clarification"]
        ctx = res.get('context', {})
        # Provider detection prefers GCP
        assert ctx.get('extracted_requirements', {}).get('provider', 'gcp') in ['gcp', None]
        assert ctx.get('intent') == 'create_compute'
        assert ctx.get('resource_type') == 'vm'

    def test_google_cloud_variation(self):
        res = self._route("Set up a virtual machine in Google Cloud")
        ctx = res.get('context', {})
        assert ctx.get('intent') == 'create_compute'
        assert ctx.get('resource_type') == 'vm'

    def test_aws_instance_request(self):
        res = self._route("Launch an EC2 instance")
        ctx = res.get('context', {})
        assert ctx.get('intent') == 'create_compute'
        # Provider may be captured in extracted requirements
        prov = ctx.get('extracted_requirements', {}).get('provider')
        assert prov in ['aws', None]

    def test_generic_vm_request(self):
        res = self._route("Create a Linux server")
        ctx = res.get('context', {})
        assert ctx.get('intent') == 'create_compute'
        assert ctx.get('resource_type') == 'vm'

    def test_case_insensitive(self):
        res = self._route("I WANT A VM IN GCP")
        ctx = res.get('context', {})
        assert ctx.get('intent') == 'create_compute'

    def test_multiple_keywords(self):
        res = self._route("Create a new virtual machine instance in Google Cloud Platform")
        ctx = res.get('context', {})
        assert ctx.get('intent') == 'create_compute'
        assert ctx.get('resource_type') == 'vm'
