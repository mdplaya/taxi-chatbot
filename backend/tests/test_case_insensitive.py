import pytest
from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest, AppEnvironment, AppEnvironmentSubtype, LineOfBusiness, OS, UseType, MachineType


class TestCaseInsensitiveProcessing:
    """Test case-insensitive handling of enum values"""
    
    @pytest.mark.asyncio
    async def test_process_answers_case_variations(self):
        """Test that answers in various cases are normalized correctly"""
        agent = ClarificationAgent()
        vm_request = VMRequest()
        
        # Test with mixed case inputs
        answers = {
            "appEnvironment": "prod",  # Should become PROD
            "lineOfBusiness": "retail",  # Should become RETAIL
            "os": "linux-rhel8",  # Should become LINUX_RHEL8
            "useType": "APP",  # Should become app
            "machineType": "n1-standard-1",  # Should become n1-STANDARD-1
            "zone": "us-east4-a",
            "costCenter": "12345",
            "project": "my-project",
            "id": "user@example.com"
        }
        
        updated_vm = await agent.process_answers(vm_request, answers)
        
        # Verify enums were set correctly
        assert updated_vm.appEnvironment == AppEnvironment.PROD
        assert updated_vm.lineOfBusiness == "RETAIL"
        assert updated_vm.os == OS.LINUX_RHEL8
        assert updated_vm.useType == UseType.APP
        assert updated_vm.machineType == MachineType.N1_STANDARD_1
        
        # Verify string fields remain unchanged
        assert updated_vm.zone == "us-east4-a"
        assert updated_vm.costCenter == "12345"
        assert updated_vm.project == "my-project"
        assert updated_vm.id == "user@example.com"
    
    @pytest.mark.asyncio
    async def test_process_answers_uppercase_variations(self):
        """Test uppercase input variations"""
        agent = ClarificationAgent()
        vm_request = VMRequest()
        
        answers = {
            "appEnvironment": "NONPROD",  # Already uppercase
            "lineOfBusiness": "ISTS",  # Already uppercase
            "os": "WINDOWS_22",  # Already correct format
            "useType": "DATABASE",  # Should become database
            "appEnvironmentSubtype": "QA"  # Should become qa
        }
        
        updated_vm = await agent.process_answers(vm_request, answers)
        
        assert updated_vm.appEnvironment == AppEnvironment.NONPROD
        assert updated_vm.lineOfBusiness == "ISTS"
        assert updated_vm.os == OS.WINDOWS_22
        assert updated_vm.useType == UseType.DATABASE
        assert updated_vm.appEnvironmentSubtype == AppEnvironmentSubtype.QA
    
    @pytest.mark.asyncio
    async def test_process_answers_mixed_case_variations(self):
        """Test mixed case input variations"""
        agent = ClarificationAgent()
        vm_request = VMRequest()
        
        answers = {
            "appEnvironment": "Prod",  # Mixed case
            "lineOfBusiness": "Retail",  # Mixed case
            "os": "Windows-19",  # Mixed case with dash
            "machineType": "N1-Standard-1",  # Mixed case machine type (using valid enum)
            "appEnvironmentSubtype": "Dev"  # Should become dev
        }
        
        updated_vm = await agent.process_answers(vm_request, answers)
        
        assert updated_vm.appEnvironment == AppEnvironment.PROD
        assert updated_vm.lineOfBusiness == "RETAIL"
        assert updated_vm.os == OS.WINDOWS_19
        assert updated_vm.machineType == MachineType.N1_STANDARD_1
        assert updated_vm.appEnvironmentSubtype == AppEnvironmentSubtype.DEV
    
    @pytest.mark.asyncio
    async def test_process_answers_os_dash_underscore(self):
        """Test OS field handles both dashes and underscores"""
        agent = ClarificationAgent()
        
        # Test with dashes
        vm_request1 = VMRequest()
        answers1 = {"os": "linux-rhel9"}
        updated_vm1 = await agent.process_answers(vm_request1, answers1)
        assert updated_vm1.os == OS.LINUX_RHEL9
        
        # Test with underscores
        vm_request2 = VMRequest()
        answers2 = {"os": "windows_19"}
        updated_vm2 = await agent.process_answers(vm_request2, answers2)
        assert updated_vm2.os == OS.WINDOWS_19
        
        # Test mixed case with dashes
        vm_request3 = VMRequest()
        answers3 = {"os": "Windows-22"}
        updated_vm3 = await agent.process_answers(vm_request3, answers3)
        assert updated_vm3.os == OS.WINDOWS_22
    
    @pytest.mark.asyncio
    async def test_process_answers_machine_type_variations(self):
        """Test machine type normalization for various patterns"""
        agent = ClarificationAgent()
        
        test_cases = [
            ("n1-standard-1", MachineType.N1_STANDARD_1),
            ("n1-STANDARD-1", MachineType.N1_STANDARD_1),
            ("N1-Standard-1", MachineType.N1_STANDARD_1),
            ("n2-standard-1", MachineType.N2_STANDARD_1),  # Changed to valid enum value
        ]
        
        for input_value, expected in test_cases:
            vm_request = VMRequest()
            answers = {"machineType": input_value}
            updated_vm = await agent.process_answers(vm_request, answers)
            assert updated_vm.machineType == expected, f"Failed for input: {input_value}"