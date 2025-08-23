import pytest
import sys
import asyncio
sys.path.append('/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend')

from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest, AppEnvironment, AppEnvironmentSubtype, OS, UseType, MachineType, LineOfBusiness

class TestClarificationAgent:
    """Test suite for clarification agent"""
    
    @pytest.mark.asyncio
    async def test_process_answers_with_enums(self):
        """Test that enum fields are properly converted"""
        agent = ClarificationAgent()
        vm_request = VMRequest()
        
        answers = {
            "appEnvironment": "PROD",
            "appEnvironmentSubtype": "qa",
            "os": "LINUX_RHEL8",
            "useType": "app",
            "machineType": "n1-STANDARD-1",
            "lineOfBusiness": "RETAIL",
            "costCenter": "12345",
            "zone": "us-east4-a",
            "project": "test-project",
            "id": "test@example.com"
        }
        
        updated = await agent.process_answers(vm_request, answers)
        
        # Check enum fields are properly converted
        assert isinstance(updated.appEnvironment, AppEnvironment)
        assert updated.appEnvironment == AppEnvironment.PROD
        assert isinstance(updated.appEnvironmentSubtype, AppEnvironmentSubtype)
        assert updated.appEnvironmentSubtype == AppEnvironmentSubtype.QA
        assert isinstance(updated.os, OS)
        assert updated.os == OS.LINUX_RHEL8
        assert isinstance(updated.useType, UseType)
        assert updated.useType == UseType.APP
        assert isinstance(updated.machineType, MachineType)
        assert updated.machineType == MachineType.N1_STANDARD_1
        assert isinstance(updated.lineOfBusiness, LineOfBusiness)
        assert updated.lineOfBusiness == LineOfBusiness.RETAIL
        
        # Check string fields remain as strings
        assert updated.costCenter == "12345"
        assert updated.zone == "us-east4-a"
        assert updated.project == "test-project"
        assert updated.id == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_process_answers_invalid_enum(self):
        """Test that invalid enum values raise errors"""
        agent = ClarificationAgent()
        vm_request = VMRequest()
        
        answers = {
            "appEnvironment": "INVALID_ENV"
        }
        
        with pytest.raises(ValueError) as exc_info:
            await agent.process_answers(vm_request, answers)
        
        assert "Invalid value" in str(exc_info.value)
        assert "appEnvironment" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_process_answers_partial(self):
        """Test processing partial answers"""
        agent = ClarificationAgent()
        vm_request = VMRequest()
        
        # Only provide some answers
        answers = {
            "os": "WINDOWS_22",
            "costCenter": "54321"
        }
        
        updated = await agent.process_answers(vm_request, answers)
        
        assert isinstance(updated.os, OS)
        assert updated.os == OS.WINDOWS_22
        assert updated.costCenter == "54321"
        assert updated.appEnvironment is None  # Not provided
        assert updated.zone is None  # Not provided
    
    @pytest.mark.asyncio
    async def test_process_answers_empty_values(self):
        """Test that empty values are skipped"""
        agent = ClarificationAgent()
        vm_request = VMRequest()
        
        answers = {
            "os": "",  # Empty string should be skipped
            "costCenter": "12345"
        }
        
        updated = await agent.process_answers(vm_request, answers)
        
        assert updated.os is None  # Should remain None
        assert updated.costCenter == "12345"
    
    @pytest.mark.asyncio
    async def test_to_taxi_payload_with_enums(self):
        """Test that to_taxi_payload works with enum instances"""
        vm_request = VMRequest(
            appEnvironment=AppEnvironment.PROD,
            appEnvironmentSubtype=AppEnvironmentSubtype.QA,
            os=OS.LINUX_RHEL8,
            useType=UseType.APP,
            machineType=MachineType.N1_STANDARD_1,
            lineOfBusiness=LineOfBusiness.RETAIL,
            costCenter="12345",
            zone="us-east4-a",
            project="test-project",
            id="test@example.com"
        )
        
        payload = vm_request.to_taxi_payload()
        
        # Check that enum values are properly extracted
        assert payload["resourceMetadata"]["appEnvironment"] == "PROD"
        assert payload["resourceMetadata"]["appEnvironmentSubtype"] == "qa"
        assert payload["resourceMetadata"]["lineOfBusiness"] == "RETAIL"
        assert payload["os"] == "LINUX_RHEL8"
        assert payload["useType"] == "app"
        assert payload["machineType"] == "n1-STANDARD-1"
        
        # Check string fields
        assert payload["resourceMetadata"]["costCenter"] == "12345"
        assert payload["zone"] == "us-east4-a"
        assert payload["project"] == "test-project"
    
    @pytest.mark.asyncio
    async def test_to_taxi_payload_with_strings(self):
        """Test that to_taxi_payload handles string values (defensive check)"""
        vm_request = VMRequest()
        
        # Manually set string values (simulating old behavior)
        vm_request.appEnvironment = "PROD"  # String instead of enum
        vm_request.os = "LINUX_RHEL8"  # String instead of enum
        vm_request.costCenter = "12345"
        vm_request.zone = "us-east4-a"
        
        # Should not raise error due to defensive checks
        payload = vm_request.to_taxi_payload()
        
        assert payload["resourceMetadata"]["appEnvironment"] == "PROD"
        assert payload["os"] == "LINUX_RHEL8"
        assert payload["resourceMetadata"]["costCenter"] == "12345"
        assert payload["zone"] == "us-east4-a"
    
    @pytest.mark.asyncio
    async def test_get_clarifications_complete(self):
        """Test get_clarifications when all fields are complete"""
        agent = ClarificationAgent()
        
        # Create a complete VM request
        vm_request = VMRequest(
            appEnvironment=AppEnvironment.PROD,
            lineOfBusiness=LineOfBusiness.RETAIL,
            costCenter="12345",
            project="test-project",
            zone="us-east4-a",
            os=OS.LINUX_RHEL8,
            useType=UseType.APP,
            machineType=MachineType.N1_STANDARD_1,
            id="test@example.com"
        )
        
        result = await agent.get_clarifications(vm_request, "")
        
        assert result["complete"] == True
        assert "vm_request" in result
    
    @pytest.mark.asyncio
    async def test_get_clarifications_missing_fields(self):
        """Test get_clarifications generates questions for missing fields"""
        agent = ClarificationAgent()
        
        # Create partial VM request
        vm_request = VMRequest(
            os=OS.LINUX_RHEL8,
            costCenter="12345"
        )
        
        result = await agent.get_clarifications(vm_request, "")
        
        assert result["complete"] == False
        assert len(result["questions"]) > 0
        
        # Check that questions are generated for missing fields
        question_fields = [q["field"] for q in result["questions"]]
        assert "appEnvironment" in question_fields
        assert "lineOfBusiness" in question_fields
        assert "project" in question_fields
        assert "zone" in question_fields
        assert "useType" in question_fields
        assert "machineType" in question_fields
        assert "id" in question_fields
        
        # Should not ask about provided fields
        assert "os" not in question_fields
        assert "costCenter" not in question_fields

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])