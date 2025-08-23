import pytest
import sys
sys.path.append('/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend')

from agents.orchestrator import analyze_user_request, UserIntent

class TestAnalyzeUserRequest:
    """Test suite for analyze_user_request function"""
    
    def test_gcp_vm_request(self):
        """Test GCP VM detection"""
        result = analyze_user_request("I want a VM in GCP")
        assert result.intent == "create_compute"
        assert result.provider == "gcp"
        assert result.resource_type == "vm"
    
    def test_google_cloud_variation(self):
        """Test Google Cloud variation"""
        result = analyze_user_request("Set up a virtual machine in Google Cloud")
        assert result.intent == "create_compute"
        assert result.provider == "gcp"
        assert result.resource_type == "vm"
    
    def test_azure_vm_request(self):
        """Test Azure detection"""
        result = analyze_user_request("Create a server in Azure")
        assert result.intent == "create_compute"
        assert result.provider == "azure"
    
    def test_aws_instance_request(self):
        """Test AWS detection"""
        result = analyze_user_request("Launch an EC2 instance")
        assert result.intent == "create_compute"
        assert result.provider == "aws"
        assert result.resource_type == "vm"
    
    def test_generic_vm_request(self):
        """Test generic VM request without provider"""
        result = analyze_user_request("Create a Linux server")
        assert result.intent == "create_compute"
        assert result.provider is None
        assert result.resource_type == "vm"
    
    def test_database_request(self):
        """Test database detection"""
        result = analyze_user_request("Deploy a PostgreSQL database")
        assert result.intent == "create_database"
        assert result.resource_type == "database"
    
    def test_delete_request(self):
        """Test delete intent"""
        result = analyze_user_request("Delete the VM we created yesterday")
        assert result.intent == "delete_resource"
    
    def test_modify_request(self):
        """Test modify intent"""
        result = analyze_user_request("Resize my virtual machine")
        assert result.intent == "modify_resource"
    
    def test_unclear_request(self):
        """Test unclear intent"""
        result = analyze_user_request("I need help with cloud resources")
        assert result.intent == "unclear"
        assert result.provider is None
        assert result.resource_type is None
    
    def test_case_insensitive(self):
        """Test case insensitivity"""
        result = analyze_user_request("I WANT A VM IN GCP")
        assert result.intent == "create_compute"
        assert result.provider == "gcp"
    
    def test_multiple_keywords(self):
        """Test multiple keywords in request"""
        result = analyze_user_request("Create a new virtual machine instance in Google Cloud Platform")
        assert result.intent == "create_compute"
        assert result.provider == "gcp"
        assert result.resource_type == "vm"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])