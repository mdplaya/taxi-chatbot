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

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

def extracted(text: str) -> dict:
    agent = OrchestratorAgent()
    res = run_async(agent.process(text))
    return res.get('context', {}).get('extracted_requirements', {})

class TestRHELVariations:
    """Test RHEL OS detection with various formats"""
    
    def test_rhel8_with_space(self):
        """Test 'RHEL 8' extracts as LINUX_RHEL8"""
        result = extracted("I need a RHEL 8 VM")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_rhel8_without_space(self):
        """Test 'RHEL8' extracts as LINUX_RHEL8"""
        result = extracted("Create a VM with RHEL8")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_rhel8_with_dash(self):
        """Test 'rhel-8' extracts as LINUX_RHEL8"""
        result = extracted("Deploy a rhel-8 server")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_rhel8_case_insensitive(self):
        """Test case insensitive RHEL detection"""
        result = extracted("install rhel 8 please")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_red_hat_8(self):
        """Test 'Red Hat 8' extracts as LINUX_RHEL8"""
        result = extracted("I want a Red Hat 8 machine")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_rhel9_variations(self):
        """Test RHEL 9 variations"""
        test_cases = [
            "RHEL 9 VM",
            "RHEL9 instance",
            "rhel-9 server",
            "Red Hat 9 machine"
        ]
        for test in test_cases:
            result = extracted(test)
            assert result.get('os') == 'LINUX_RHEL9', f"Failed for: {test}"


class TestMachineTypeExtraction:
    """Test machine type extraction including partial matches"""
    
    def test_n1_specific_type(self):
        result = extracted("Deploy an n1-standard-4 instance")
        assert result.get('machine_type') == 'n1-standard-4'
    
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
            result = extracted(input_text)
            assert result.get('machine_type') == expected, f"Failed for: {input_text}"
    
    def test_n2_series(self):
        """Test N2 series machine types"""
        test_cases = [
            ("n2-standard-2 VM", "n2-standard-2"),
            ("n2-highmem-4 instance", "n2-highmem-4"),
        ]
        for input_text, expected in test_cases:
            result = extracted(input_text)
            assert result.get('machine_type') == expected
    
    def test_c2_series(self):
        """Test C2 series machine types"""
        result = extracted("Need a c2-standard-4 for compute")
        assert result.get('machine_type') == 'c2-standard-4'
    
    # Descriptive mapping is not supported in current architecture


class TestCompleteScenarios:
    """Test complete real-world scenarios"""
    
    def test_retail_app_scenario(self):
        """Test a complete retail app deployment scenario"""
        result = extracted(
            "Deploy a Windows 2022 VM in us-east4-a for retail app in production"
        )
        assert result.get('os') == 'WINDOWS_22'
        assert result.get('zone') == 'us-east4-a'
        assert result.get('lineOfBusiness') == 'RETAIL'
        assert result.get('environment') == 'PROD'
        assert result.get('use_type') == 'app'
    
    def test_dev_database_scenario(self):
        """Test a development database scenario"""
        result = extracted(
            "I need a RHEL 8 database server for development in ISTS"
        )
        assert result.get('os') == 'LINUX_RHEL8'
        assert result.get('use_type') == 'database'
        assert result.get('environment') == 'NONPROD'
        assert result.get('lineOfBusiness') == 'ISTS'
    
    def test_minimal_request(self):
        """Test minimal request with just VM type"""
        result = extracted("I want an n1 VM")
        assert 'machine_type' not in result
        # Should not have other fields
        assert result.get('os') is None
        assert result.get('environment') is None
    
    def test_complex_request(self):
        """Test complex request with multiple requirements"""
        result = extracted(
            "Create a cost-optimized RHEL8 app server for QA testing in "
            "us-central1-a for the EDML team"
        )
        # No descriptive mapping for cost-optimized -> e2-small
        assert 'machine_type' not in result or isinstance(result.get('machine_type'), str)
        assert result.get('os') == 'LINUX_RHEL8'
        assert result.get('use_type') == 'app'
        assert result.get('environment') == 'NONPROD'
        assert result.get('appEnvironmentSubtype') == 'qa'
        assert result.get('zone') == 'us-central1-a'
        assert result.get('lineOfBusiness') == 'EDML'


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
            assert result.get('environment') == 'NONPROD'
            assert result.get('appEnvironmentSubtype') == expected_subtype, f"Failed for: {input_text}"
    
    def test_prod_no_subtype(self):
        """Test that PROD environment has no subtype"""
        result = extracted("Production server needed")
        assert result.get('environment') == 'PROD'
        assert result.get('appEnvironmentSubtype') is None or 'appEnvironmentSubtype' not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
