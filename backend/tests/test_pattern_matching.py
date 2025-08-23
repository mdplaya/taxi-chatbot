"""
Test suite for enhanced pattern matching functionality
Tests the critical requirements from the TODO list
"""
import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.compute import extract_vm_requirements_pattern

class TestRHELVariations:
    """Test RHEL OS detection with various formats"""
    
    def test_rhel8_with_space(self):
        """Test 'RHEL 8' extracts as LINUX_RHEL8"""
        result = extract_vm_requirements_pattern("I need a RHEL 8 VM")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_rhel8_without_space(self):
        """Test 'RHEL8' extracts as LINUX_RHEL8"""
        result = extract_vm_requirements_pattern("Create a VM with RHEL8")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_rhel8_with_dash(self):
        """Test 'rhel-8' extracts as LINUX_RHEL8"""
        result = extract_vm_requirements_pattern("Deploy a rhel-8 server")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_rhel8_case_insensitive(self):
        """Test case insensitive RHEL detection"""
        result = extract_vm_requirements_pattern("install rhel 8 please")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_red_hat_8(self):
        """Test 'Red Hat 8' extracts as LINUX_RHEL8"""
        result = extract_vm_requirements_pattern("I want a Red Hat 8 machine")
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
            result = extract_vm_requirements_pattern(test)
            assert result.get('os') == 'LINUX_RHEL9', f"Failed for: {test}"


class TestMachineTypeExtraction:
    """Test machine type extraction including partial matches"""
    
    def test_n1_alone_maps_to_n1_standard_1(self):
        """Test 'n1' alone maps to n1-standard-1"""
        result = extract_vm_requirements_pattern("I want an n1 machine")
        assert result.get('machine_type') == 'n1-standard-1'
    
    def test_n1_specific_type(self):
        """Test specific n1 machine type"""
        result = extract_vm_requirements_pattern("Deploy an n1-standard-4 instance")
        assert result.get('machine_type') == 'n1-standard-4'
    
    def test_n1_partial_at_end(self):
        """Test 'n1' at end of sentence"""
        result = extract_vm_requirements_pattern("Set up n1")
        assert result.get('machine_type') == 'n1-standard-1'
    
    def test_e2_series(self):
        """Test E2 series machine types"""
        test_cases = [
            ("e2-micro VM", "e2-micro"),
            ("e2-small instance", "e2-small"),
            ("e2-medium server", "e2-medium"),
            ("e2-standard-2", "e2-standard-2"),
        ]
        for input_text, expected in test_cases:
            result = extract_vm_requirements_pattern(input_text)
            assert result.get('machine_type') == expected, f"Failed for: {input_text}"
    
    def test_n2_series(self):
        """Test N2 series machine types"""
        test_cases = [
            ("n2-standard-2 VM", "n2-standard-2"),
            ("n2-highmem-4 instance", "n2-highmem-4"),
        ]
        for input_text, expected in test_cases:
            result = extract_vm_requirements_pattern(input_text)
            assert result.get('machine_type') == expected
    
    def test_c2_series(self):
        """Test C2 series machine types"""
        result = extract_vm_requirements_pattern("Need a c2-standard-4 for compute")
        assert result.get('machine_type') == 'c2-standard-4'
    
    def test_descriptive_machine_types(self):
        """Test descriptive machine type requests"""
        test_cases = [
            ("I need a cost optimized VM", "e2-small"),
            ("Give me a compute optimized instance", "c2-standard-4"),
            ("I want a high memory machine", "n2-highmem-4"),
            ("Create a balanced VM", "n2-standard-2"),
        ]
        for input_text, expected in test_cases:
            result = extract_vm_requirements_pattern(input_text)
            assert result.get('machine_type') == expected, f"Failed for: {input_text}"


class TestCompleteScenarios:
    """Test complete real-world scenarios"""
    
    def test_retail_app_scenario(self):
        """Test a complete retail app deployment scenario"""
        result = extract_vm_requirements_pattern(
            "Deploy a Windows 2022 VM in us-east4-a for retail app in production"
        )
        assert result.get('os') == 'WINDOWS_22'
        assert result.get('zone') == 'us-east4-a'
        assert result.get('line_of_business') == 'RETAIL'
        assert result.get('environment') == 'PROD'
        assert result.get('use_type') == 'app'
    
    def test_dev_database_scenario(self):
        """Test a development database scenario"""
        result = extract_vm_requirements_pattern(
            "I need a RHEL 8 database server for development in ISTS"
        )
        assert result.get('os') == 'LINUX_RHEL8'
        assert result.get('use_type') == 'database'
        assert result.get('environment') == 'NONPROD'
        assert result.get('line_of_business') == 'ISTS'
    
    def test_minimal_request(self):
        """Test minimal request with just VM type"""
        result = extract_vm_requirements_pattern("I want an n1 VM")
        assert result.get('machine_type') == 'n1-standard-1'
        # Should not have other fields
        assert result.get('os') is None
        assert result.get('environment') is None
    
    def test_complex_request(self):
        """Test complex request with multiple requirements"""
        result = extract_vm_requirements_pattern(
            "Create a cost-optimized RHEL8 app server for QA testing in "
            "us-central1-a for the EDML team"
        )
        assert result.get('machine_type') == 'e2-small'
        assert result.get('os') == 'LINUX_RHEL8'
        assert result.get('use_type') == 'app'
        assert result.get('environment') == 'NONPROD'
        assert result.get('environment_subtype') == 'qa'
        assert result.get('zone') == 'us-central1-a'
        assert result.get('line_of_business') == 'EDML'


class TestConfidenceScoring:
    """Test confidence scoring in pattern matching"""
    
    def test_high_confidence_extraction(self):
        """Test that clear requests have high confidence"""
        result = extract_vm_requirements_pattern(
            "I need an n1-standard-4 RHEL 8 VM in us-east4-a"
        )
        confidence = result.get('_confidence', 0)
        assert confidence > 0.8, f"Expected high confidence, got {confidence}"
    
    def test_low_confidence_extraction(self):
        """Test that vague requests have lower confidence"""
        result = extract_vm_requirements_pattern("I might need something")
        confidence = result.get('_confidence', 0)
        # Should have no matches, so no confidence score
        assert confidence == 0 or '_confidence' not in result


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
            result = extract_vm_requirements_pattern(input_text)
            assert result.get('environment') == 'NONPROD'
            assert result.get('environment_subtype') == expected_subtype, f"Failed for: {input_text}"
    
    def test_prod_no_subtype(self):
        """Test that PROD environment has no subtype"""
        result = extract_vm_requirements_pattern("Production server needed")
        assert result.get('environment') == 'PROD'
        assert result.get('environment_subtype') is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])