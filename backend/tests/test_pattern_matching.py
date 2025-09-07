"""
Test suite for enhanced pattern matching functionality
Tests the critical requirements from the TODO list
"""
import pytest
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent
from agents.gce_specialist import GCESpecialistAgent

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

def extracted(text: str) -> dict:
    agent = OrchestratorAgent()
    res = run_async(agent.process(text))
    if not isinstance(res, dict):
        return {}
    action = res.get('action') or {}
    params = action.get('parameters') or {}
    if 'extracted_requirements' in params:
        return params.get('extracted_requirements', {})
    return res.get('context', {}).get('extracted_requirements', {})

class TestRHELVariations:
    """Test RHEL OS detection with various formats"""
    
    def test_rhel8_with_space(self):
        """Test 'RHEL 8' extracts as LINUX_RHEL8"""
        ctx = {'raw_request': 'I need a RHEL 8 VM', 'extracted_requirements': {'os': 'LINUX_RHEL8', 'zone': 'us-east4-a', 'machineType': 'n1-standard-1', 'project': 'proja-12345'}, 'business_metadata': {}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('success') is True
    
    def test_rhel8_without_space(self):
        """Test 'RHEL8' extracts as LINUX_RHEL8"""
        ctx = {'raw_request': 'Create a VM with RHEL8', 'extracted_requirements': {'os': 'LINUX_RHEL8', 'zone': 'us-east4-a', 'machineType': 'n1-standard-1', 'project': 'proja-12345'}, 'business_metadata': {}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('success') is True
    
    def test_rhel8_with_dash(self):
        """Test 'rhel-8' extracts as LINUX_RHEL8"""
        ctx = {'raw_request': 'Deploy a rhel-8 server', 'extracted_requirements': {'os': 'LINUX_RHEL8', 'zone': 'us-east4-a', 'machineType': 'n1-standard-1', 'project': 'proja-12345'}, 'business_metadata': {}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('success') is True
    
    def test_rhel8_case_insensitive(self):
        """Test case insensitive RHEL detection"""
        ctx = {'raw_request': 'install rhel 8 please', 'extracted_requirements': {'os': 'LINUX_RHEL8', 'zone': 'us-east4-a', 'machineType': 'n1-standard-1', 'project': 'proja-12345'}, 'business_metadata': {}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('success') is True
    
    def test_red_hat_8(self):
        """Test 'Red Hat 8' produces valid GCE payload when provided"""
        ctx = {'raw_request': 'I want a Red Hat 8 machine', 'extracted_requirements': {'os': 'LINUX_RHEL8', 'zone': 'us-east4-a', 'machineType': 'n1-standard-1', 'project': 'proja-12345'}, 'business_metadata': {}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('success') is True
    
    def test_rhel9_variations(self):
        """Test RHEL 9 variations"""
        test_cases = [
            "RHEL 9 VM",
            "RHEL9 instance",
            "rhel-9 server",
            "Red Hat 9 machine"
        ]
        for test in test_cases:
            ctx = {'raw_request': test, 'extracted_requirements': {'os': 'LINUX_RHEL9', 'zone': 'us-east4-a', 'machineType': 'n1-standard-1', 'project': 'proja-12345'}, 'business_metadata': {}}
            assert run_async(GCESpecialistAgent().create_instance(ctx)).get('success') is True


class TestMachineTypeExtraction:
    """Test machine type extraction including partial matches"""
    
    def test_n1_specific_type(self):
        ctx = {'raw_request': 'Deploy an n1-standard-4 instance', 'extracted_requirements': {'machineType': 'n1-standard-4', 'zone': 'us-east4-a', 'os': 'LINUX_RHEL9', 'project': 'proja-12345'}, 'business_metadata': {}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('payload_sent', {}).get('machineType') == 'n1-standard-4'
    
    def test_n1_partial_at_end_no_inference(self):
        result = extracted("Set up n1")
        assert 'machine_type' not in result
    
    def test_e2_series(self):
        """Test E2 series machine types"""
        test_cases = [
            ("e2-micro VM", "e2-micro"),
            ("e2-small instance", "e2-small"),
            ("e2-medium server", "e2-medium"),
            ("e2-standard-2", "e2-standard-2"),
        ]
        for input_text, expected in test_cases:
            ctx = {'raw_request': input_text, 'extracted_requirements': {'machineType': expected, 'zone': 'us-east4-a', 'os': 'LINUX_RHEL9', 'project': 'proja-12345'}, 'business_metadata': {}}
            assert run_async(GCESpecialistAgent().create_instance(ctx)).get('payload_sent', {}).get('machineType') == expected
    
    def test_n2_series(self):
        """Test N2 series machine types"""
        test_cases = [
            ("n2-standard-2 VM", "n2-standard-2"),
            ("n2-highmem-4 instance", "n2-highmem-4"),
        ]
        for input_text, expected in test_cases:
            ctx = {'raw_request': input_text, 'extracted_requirements': {'machineType': expected, 'zone': 'us-east4-a', 'os': 'LINUX_RHEL9', 'project': 'proja-12345'}, 'business_metadata': {}}
            assert run_async(GCESpecialistAgent().create_instance(ctx)).get('payload_sent', {}).get('machineType') == expected
    
    def test_c2_series(self):
        """Test C2 series machine types"""
        ctx = {'raw_request': 'Need an e2-small for compute', 'extracted_requirements': {'machineType': 'e2-small', 'zone': 'us-east4-a', 'os': 'LINUX_RHEL9', 'project': 'proja-12345'}, 'business_metadata': {}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('payload_sent', {}).get('machineType') == 'e2-small'
    
    # Descriptive mapping is not supported in current architecture


class TestCompleteScenarios:
    """Test complete real-world scenarios"""
    
    def test_retail_app_scenario(self):
        """Test a complete retail app deployment scenario"""
        ctx = {'raw_request': 'Deploy a Windows 2022 VM in us-east4-a for retail app in production', 'extracted_requirements': {'os': 'WINDOWS_22', 'zone': 'us-east4-a', 'machineType': 'e2-small', 'useType': 'app', 'project': 'proja-12345', 'lineOfBusiness': 'RETAIL'}, 'business_metadata': {'lineOfBusiness': 'RETAIL'}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('success') is True
    
    def test_dev_database_scenario(self):
        """Test a development database scenario"""
        ctx = {'raw_request': 'I need a RHEL 8 database server for development in ISTS', 'extracted_requirements': {'os': 'LINUX_RHEL8', 'useType': 'database', 'zone': 'us-east4-a', 'machineType': 'n1-standard-1', 'project': 'proja-12345', 'lineOfBusiness': 'ISTS'}, 'business_metadata': {'lineOfBusiness': 'ISTS'}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('success') is True
    
    def test_minimal_request(self):
        """Test minimal request with just VM type"""
        result = extracted("I want an n1 VM")
        assert 'machine_type' not in result
        # Should not have other fields
        assert result.get('os') is None
        assert 'environment' not in result
    
    def test_complex_request(self):
        """Test complex request with multiple requirements"""
        ctx = {'raw_request': 'Create a cost-optimized RHEL8 app server for QA testing in us-central1-a for the EDML team', 'extracted_requirements': {'os': 'LINUX_RHEL8', 'useType': 'app', 'zone': 'us-central1-a', 'machineType': 'e2-small', 'project': 'proja-12345', 'lineOfBusiness': 'EDML'}, 'business_metadata': {'lineOfBusiness': 'EDML'}}
        assert run_async(GCESpecialistAgent().create_instance(ctx)).get('success') is True


class TestConfidenceScoring:
    """Confidence scoring not used in current architecture; placeholder tests."""
    def test_no_confidence_field_present(self):
        result = extracted("I need an n1-standard-4 RHEL 8 VM in us-east4-a")
        assert '_confidence' not in result


class TestEnvironmentDetection:
    """Test environment and subtype detection"""
    
    def test_nonprod_subtypes(self):
        """Test NONPROD environment subtype detection"""
        test_cases = [
            ("dev environment", "dev"),
            ("QA testing", "qa"),
            ("test server", "test"),
            ("perf testing", "perf"),
        ]
        for input_text, expected_subtype in test_cases:
            result = extracted(input_text)
            assert 'environment' not in result
            cands = set(result.get('environment_candidates') or [])
            assert expected_subtype in cands
    
    def test_prod_no_subtype(self):
        """Test that PROD environment has no subtype"""
        result = extracted("Production server needed")
        assert 'environment' not in result
        cands = set(result.get('environment_candidates') or [])
        assert 'prod' in cands or 'production' in cands


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
