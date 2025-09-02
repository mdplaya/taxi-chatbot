import pytest
import sys
import re
sys.path.append('/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend')

def extract_vm_requirements(user_input: str) -> dict:
    """Direct copy of the function for testing without dependencies"""
    user_input_lower = user_input.lower()
    requirements = {}
    
    # Environment detection
    if any(term in user_input_lower for term in ['prod', 'production']):
        requirements['environment'] = 'PROD'
    elif any(term in user_input_lower for term in ['dev', 'development', 'test', 'testing', 'nonprod', 'non-prod', 'staging']):
        requirements['environment'] = 'NONPROD'
    
    # OS detection
    if 'windows' in user_input_lower:
        if any(term in user_input for term in ['22', '2022']):
            requirements['os'] = 'WINDOWS_22'
        elif any(term in user_input for term in ['19', '2019']):
            requirements['os'] = 'WINDOWS_19'
        else:
            requirements['os'] = 'WINDOWS_22'  # Default to latest
    elif any(term in user_input_lower for term in ['linux', 'rhel', 'red hat']):
        if '9' in user_input:
            requirements['os'] = 'LINUX_RHEL9'
        elif '8' in user_input:
            requirements['os'] = 'LINUX_RHEL8'
        else:
            requirements['os'] = 'LINUX_RHEL9'  # Default to RHEL9
    elif 'ubuntu' in user_input_lower:
        requirements['os'] = 'LINUX_RHEL9'  # Map Ubuntu to RHEL9 for now
    
    # Use type detection
    if any(term in user_input_lower for term in ['database', 'db', 'sql', 'mysql', 'postgres', 'mongodb']):
        requirements['use_type'] = 'database'
    elif any(term in user_input_lower for term in ['app', 'application', 'web', 'api', 'service']):
        requirements['use_type'] = 'app'
    
    # Machine type detection
    if 'n1-standard' in user_input_lower:
        # Extract number if specified (e.g., n1-standard-2)
        match = re.search(r'n1-standard-(\d+)', user_input_lower)
        if match:
            requirements['machine_type'] = f'n1-STANDARD-{match.group(1)}'
        else:
            requirements['machine_type'] = 'n1-STANDARD-1'
    elif 'n2-standard' in user_input_lower:
        match = re.search(r'n2-standard-(\d+)', user_input_lower)
        if match:
            requirements['machine_type'] = f'n2-STANDARD-{match.group(1)}'
        else:
            requirements['machine_type'] = 'n2-STANDARD-1'
    elif 'e2-medium' in user_input_lower:
        requirements['machine_type'] = 'e2-MEDIUM'
    elif 'e2-small' in user_input_lower:
        requirements['machine_type'] = 'e2-SMALL'
    
    # Zone detection (regex for GCP zones)
    zone_pattern = r'(us|europe|asia|australia|southamerica|northamerica)-(central|east|west|south|north|northeast|southeast)\d+-[a-z]'
    zone_match = re.search(zone_pattern, user_input_lower)
    if zone_match:
        requirements['zone'] = zone_match.group()
    
    # Line of business detection
    if 'retail' in user_input_lower:
        requirements['line_of_business'] = 'RETAIL'
    elif 'ists' in user_input_lower:
        requirements['line_of_business'] = 'ISTS'
    elif 'edml' in user_input_lower:
        requirements['line_of_business'] = 'EDML'
    
    return requirements

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
    
    def test_linux_rhel8_detection(self):
        """Test Linux RHEL8 detection"""
        result = extract_vm_requirements("Set up a Linux RHEL8 instance")
        assert result.get('os') == 'LINUX_RHEL8'
    
    def test_database_use_type(self):
        """Test database use type detection"""
        result = extract_vm_requirements("VM for our database server")
        assert result.get('use_type') == 'database'
    
    def test_app_use_type(self):
        """Test application use type detection"""
        result = extract_vm_requirements("Server for our web application")
        assert result.get('use_type') == 'app'
    
    def test_zone_detection(self):
        """Test GCP zone detection"""
        result = extract_vm_requirements("Deploy VM in us-east4-a zone")
        assert result.get('zone') == 'us-east4-a'
    
    def test_retail_line_of_business(self):
        """Test RETAIL line of business detection"""
        result = extract_vm_requirements("VM for retail application")
        assert result.get('line_of_business') == 'RETAIL'
    
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

if __name__ == "__main__":
    pytest.main([__file__, "-v"])