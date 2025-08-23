import pytest
import sys
sys.path.append('/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend')

from agents.compute import extract_vm_requirements

class TestExtractVMRequirements:
    """Test suite for extract_vm_requirements function"""
    
    def test_development_environment(self):
        """Test development environment detection"""
        result = extract_vm_requirements("I need a VM for development")
        assert result.get('environment') == 'NONPROD'
    
    def test_production_environment(self):
        """Test production environment detection"""
        result = extract_vm_requirements("Deploy a production server")
        assert result.get('environment') == 'PROD'
    
    def test_windows_22_detection(self):
        """Test Windows Server 2022 detection"""
        result = extract_vm_requirements("Create a Windows 2022 VM")
        assert result.get('os') == 'WINDOWS_22'
    
    def test_windows_19_detection(self):
        """Test Windows Server 2019 detection"""
        result = extract_vm_requirements("Need a Windows 2019 server")
        assert result.get('os') == 'WINDOWS_19'
    
    def test_linux_rhel8_detection(self):
        """Test Linux RHEL8 detection"""
        result = extract_vm_requirements("Set up a Linux RHEL8 instance")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_linux_rhel9_detection(self):
        """Test Linux RHEL9 detection"""
        result = extract_vm_requirements("Deploy RHEL 9 server")
        assert result.get('os') == 'LINUX_RHEL9'
    
    def test_database_use_type(self):
        """Test database use type detection"""
        result = extract_vm_requirements("VM for our database server")
        assert result.get('use_type') == 'database'
    
    def test_app_use_type(self):
        """Test application use type detection"""
        result = extract_vm_requirements("Server for our web application")
        assert result.get('use_type') == 'app'
    
    def test_machine_type_n1_standard(self):
        """Test n1-standard machine type detection"""
        result = extract_vm_requirements("Create VM with n1-standard-2 machine type")
        assert result.get('machine_type') == 'n1-STANDARD-2'
    
    def test_machine_type_n2_standard(self):
        """Test n2-standard machine type detection"""
        result = extract_vm_requirements("Need n2-standard-4 instance")
        assert result.get('machine_type') == 'n2-STANDARD-4'
    
    def test_zone_detection(self):
        """Test GCP zone detection"""
        result = extract_vm_requirements("Deploy VM in us-east4-a zone")
        assert result.get('zone') == 'us-east4-a'
    
    def test_retail_line_of_business(self):
        """Test RETAIL line of business detection"""
        result = extract_vm_requirements("VM for retail application")
        assert result.get('line_of_business') == 'RETAIL'
    
    def test_ists_line_of_business(self):
        """Test ISTS line of business detection"""
        result = extract_vm_requirements("Server for ISTS team")
        assert result.get('line_of_business') == 'ISTS'
    
    def test_edml_line_of_business(self):
        """Test EDML line of business detection"""
        result = extract_vm_requirements("Create instance for EDML project")
        assert result.get('line_of_business') == 'EDML'
    
    def test_complex_request(self):
        """Test complex request with multiple requirements"""
        result = extract_vm_requirements(
            "Deploy a Windows 2022 VM in us-east4-a for retail app in production"
        )
        assert result.get('os') == 'WINDOWS_22'
        assert result.get('zone') == 'us-east4-a'
        assert result.get('line_of_business') == 'RETAIL'
        assert result.get('use_type') == 'app'
        assert result.get('environment') == 'PROD'
    
    def test_partial_requirements(self):
        """Test request with only some requirements"""
        result = extract_vm_requirements("I need a Linux server")
        assert result.get('os') == 'LINUX_RHEL8'  # Default
        assert 'environment' not in result
        assert 'zone' not in result
    
    def test_ubuntu_maps_to_rhel(self):
        """Test Ubuntu maps to RHEL"""
        result = extract_vm_requirements("Create an Ubuntu server")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_staging_is_nonprod(self):
        """Test staging maps to NONPROD"""
        result = extract_vm_requirements("Deploy to staging environment")
        assert result.get('environment') == 'NONPROD'
    
    def test_empty_request(self):
        """Test empty request returns empty dict"""
        result = extract_vm_requirements("")
        assert result == {}
    
    def test_case_insensitive_detection(self):
        """Test case insensitive detection"""
        result = extract_vm_requirements("DEPLOY A WINDOWS VM FOR RETAIL IN PROD")
        assert result.get('os') == 'WINDOWS_22'
        assert result.get('line_of_business') == 'RETAIL'
        assert result.get('environment') == 'PROD'

if __name__ == "__main__":
    pytest.main([__file__, "-v"])