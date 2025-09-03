"""Simple synchronous tests for clarification agent"""
import sys
import asyncio
sys.path.append('/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend')

from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest, AppEnvironment, AppEnvironmentSubtype, OS, UseType, MachineType, LineOfBusiness

def run_async(coro):
    """Helper to run async functions in sync context"""
    return asyncio.get_event_loop().run_until_complete(coro)

def test_process_answers_with_enums():
    """Test that enum fields are properly converted"""
    agent = ClarificationAgent()
    vm_request = VMRequest()
    
    answers = {
        "appEnvironment": "PROD",
        "appEnvironmentSubtype": "dev",
        "os": "LINUX_RHEL8",
        "useType": "app",
        "machineType": "n1-STANDARD-1",
        "lineOfBusiness": "RETAIL",
        "costCenter": "12345",
        "zone": "us-east4-a"
    }
    
    updated = run_async(agent.process_answers(vm_request, answers))
    
    # Check enum fields are properly converted
    assert isinstance(updated.appEnvironment, AppEnvironment)
    # When a NONPROD subtype is provided, env should be NONPROD
    assert updated.appEnvironment == AppEnvironment.NONPROD
    assert isinstance(updated.appEnvironmentSubtype, AppEnvironmentSubtype)
    assert updated.appEnvironmentSubtype == AppEnvironmentSubtype.DEV
    assert isinstance(updated.os, OS)
    assert updated.os == OS.LINUX_RHEL8
    assert isinstance(updated.useType, UseType)
    assert updated.useType == UseType.APP
    
    # Check string fields
    assert updated.costCenter == "12345"
    assert updated.zone == "us-east4-a"
    
    print("✅ test_process_answers_with_enums passed")

def test_process_answers_invalid_enum():
    """Test that invalid enum values raise errors"""
    agent = ClarificationAgent()
    vm_request = VMRequest()
    
    answers = {
        "appEnvironment": "INVALID_ENV"
    }
    
    try:
        run_async(agent.process_answers(vm_request, answers))
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid value" in str(e)
        print("✅ test_process_answers_invalid_enum passed")

def test_to_taxi_payload_with_enums():
    """Test that to_taxi_payload works with enum instances"""
    vm_request = VMRequest(
        appEnvironment=AppEnvironment.PROD,
        os=OS.LINUX_RHEL8,
        useType=UseType.APP,
        machineType=MachineType.N1_STANDARD_1,
        lineOfBusiness=LineOfBusiness.RETAIL,
        costCenter="12345",
        zone="us-east4-a"
    )
    
    payload = vm_request.to_taxi_payload()
    
    assert payload["resourceMetadata"]["appEnvironment"] == "PROD"
    assert payload["os"] == "LINUX_RHEL8"
    assert payload["useType"] == "app"
    assert payload["machineType"] == "n1-STANDARD-1"
    
    print("✅ test_to_taxi_payload_with_enums passed")

def test_to_taxi_payload_with_strings():
    """Test that to_taxi_payload handles string values (defensive check)"""
    vm_request = VMRequest()
    
    # Manually set string values (simulating old behavior)
    vm_request.appEnvironment = "PROD"  # String instead of enum
    vm_request.os = "LINUX_RHEL8"  # String instead of enum
    vm_request.costCenter = "12345"
    
    # Should not raise error due to defensive checks
    payload = vm_request.to_taxi_payload()
    
    assert payload["resourceMetadata"]["appEnvironment"] == "PROD"
    assert payload["os"] == "LINUX_RHEL8"
    
    print("✅ test_to_taxi_payload_with_strings passed (defensive checks working)")

if __name__ == "__main__":
    print("Running clarification agent tests...\n")
    test_process_answers_with_enums()
    test_process_answers_invalid_enum()
    test_to_taxi_payload_with_enums()
    test_to_taxi_payload_with_strings()
    print("\n✅ All tests passed!")
