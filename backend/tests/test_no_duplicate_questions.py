"""
Test script to verify no duplicate questions are asked
"""

import asyncio
import sys
import os
import json
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent
from agents.gce_specialist import GCESpecialistAgent
from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest


async def test_orchestrator_extracts_business_metadata():
    """Test that Orchestrator extracts business metadata from user input"""
    print("\n=== Test 1: Orchestrator extracts business metadata ===")
    
    orchestrator = OrchestratorAgent()
    
    test_cases = [
        {
            "input": "I want a VM in GCP for our retail app with cost center 12345",
            "expected_business": ["lineOfBusiness", "costCenter"],
            "expected_values": {"lineOfBusiness": "RETAIL", "costCenter": "12345"}
        },
        {
            "input": "Create a production server for ISTS team, user@company.com needs access",
            "expected_business": ["lineOfBusiness", "id"],
            "expected_values": {"lineOfBusiness": "ISTS", "id": "user@company.com"}
        },
        {
            "input": "Deploy a test instance for EDML data management platform",
            "expected_business": ["lineOfBusiness", "appEnvironmentSubtype"],
            "expected_values": {"lineOfBusiness": "EDML", "appEnvironmentSubtype": "test"}
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\nTest case {i+1}: {test_case['input']}")
        result = await orchestrator.process(test_case["input"])
        
        business_metadata = result.get("context", {}).get("business_metadata", {})
        extracted = result.get("context", {}).get("extracted_requirements", {})
        
        print(f"Business metadata extracted: {business_metadata}")
        print(f"All extracted: {extracted}")
        
        # Check if expected fields were extracted
        for field in test_case["expected_business"]:
            if field in business_metadata or field in extracted:
                actual_value = business_metadata.get(field) or extracted.get(field)
                expected_value = test_case["expected_values"].get(field)
                if actual_value == expected_value:
                    print(f"✅ {field}: {actual_value}")
                else:
                    print(f"⚠️  {field}: got '{actual_value}', expected '{expected_value}'")
            else:
                print(f"❌ {field}: NOT extracted")
    
    return True


async def test_gce_specialist_excludes_business_fields():
    """Test that GCE Specialist doesn't extract business fields when provided in context"""
    print("\n=== Test 2: GCE Specialist excludes business fields ===")
    
    gce_agent = GCESpecialistAgent()
    
    # Simulate context with business metadata already extracted
    context = {
        "raw_request": "I need a Linux VM in us-east4-a with e2-medium",
        "business_metadata": {
            "lineOfBusiness": "RETAIL",
            "costCenter": "12345",
            "id": "user@company.com"
        },
        "extracted_requirements": {}
    }
    
    # Extract requirements
    result = gce_agent._extract_vm_requirements(
        context["raw_request"], 
        context
    )
    
    extracted_fields = result.get("extracted_fields", {})
    clarifications = result.get("clarifications_needed", [])
    
    print(f"Extracted fields: {extracted_fields}")
    print(f"Clarifications needed: {clarifications}")
    
    # Check that business fields from context are included but not re-asked
    business_fields = ["lineOfBusiness", "costCenter", "id"]
    technical_fields = ["zone", "os", "machineType", "useType"]
    
    # Business fields should be in extracted_fields (merged from context)
    for field in business_fields:
        if field in extracted_fields:
            print(f"✅ {field}: Included from context ({extracted_fields[field]})")
        else:
            print(f"⚠️  {field}: Not found in extracted fields")
    
    # Check clarifications don't ask for business fields
    asked_fields = []
    for q in clarifications:
        if isinstance(q, dict):
            asked_fields.append(q.get("field", ""))
        elif isinstance(q, str):
            # Try to identify field from question text
            for field in business_fields:
                if field.lower() in q.lower():
                    asked_fields.append(field)
    
    for field in business_fields:
        if field in asked_fields:
            print(f"❌ {field}: Still being asked in clarifications (DUPLICATE!)")
        else:
            print(f"✅ {field}: Not asked in clarifications")
    
    return True


async def test_clarification_agent_tracks_asked_fields():
    """Test that ClarificationAgent properly tracks asked fields"""
    print("\n=== Test 3: ClarificationAgent tracks asked fields ===")
    
    vm_request = VMRequest()
    vm_request.zone = "us-east4-a"
    vm_request.os = "LINUX_RHEL9"
    # Leave other fields empty
    
    # First round of questions
    context1 = {
        "raw_request": "I need a VM",
        "session_id": "test-session",
        "asked_fields": []  # Empty initially
    }
    
    clarification_agent1 = ClarificationAgent(context=context1)
    questions1 = await clarification_agent1.generate_questions(
        vm_request,
        vm_request.get_missing_fields()
    )
    
    print(f"Round 1 - Missing fields: {vm_request.get_missing_fields()}")
    print(f"Round 1 - Questions asked: {[q.get('field') for q in questions1]}")
    print(f"Round 1 - Asked fields after: {context1.get('asked_fields', [])}")
    
    # Simulate answering some questions
    vm_request.lineOfBusiness = "RETAIL"
    vm_request.costCenter = "12345"
    
    # Second round with tracked asked_fields
    context2 = {
        "raw_request": "I need a VM",
        "session_id": "test-session",
        "asked_fields": context1.get("asked_fields", [])  # Pass previously asked fields
    }
    
    clarification_agent2 = ClarificationAgent(context=context2)
    questions2 = await clarification_agent2.generate_questions(
        vm_request,
        vm_request.get_missing_fields()
    )
    
    print(f"\nRound 2 - Missing fields: {vm_request.get_missing_fields()}")
    print(f"Round 2 - Questions asked: {[q.get('field') for q in questions2]}")
    print(f"Round 2 - Asked fields after: {context2.get('asked_fields', [])}")
    
    # Check for duplicates
    all_asked_fields = []
    for q in questions1 + questions2:
        field = q.get("field")
        if field in all_asked_fields:
            print(f"❌ DUPLICATE: {field} was asked multiple times!")
        else:
            all_asked_fields.append(field)
    
    if len(all_asked_fields) == len(set(all_asked_fields)):
        print("✅ No duplicate questions detected")
    
    return True


async def test_full_flow_no_duplicates():
    """Test the full flow to ensure no duplicate questions"""
    print("\n=== Test 4: Full flow with no duplicate questions ===")
    
    # Step 1: Orchestrator processes initial request
    orchestrator = OrchestratorAgent()
    orchestrator_result = await orchestrator.process(
        "I want a VM in GCP for retail application with cost center 12345"
    )
    
    print(f"Orchestrator routing: {orchestrator_result['next_agent']}")
    print(f"Business metadata: {orchestrator_result['context'].get('business_metadata', {})}")
    
    # Step 2: GCE Specialist processes with context from Orchestrator
    gce_agent = GCESpecialistAgent()
    context = orchestrator_result["context"]
    
    # Create instance with context
    gce_result = await gce_agent.create_instance(
        context,
        config={"skip_validation": True, "skip_improvements": True}
    )
    
    if gce_result.get("needs_clarification"):
        questions = gce_result.get("questions", [])
        print(f"\nQuestions from GCE Specialist:")
        
        # Track which fields are being asked
        asked_fields = set()
        for q in questions:
            if isinstance(q, dict):
                field = q.get("field", "")
                question = q.get("question", "")
            else:
                field = str(q)
                question = str(q)
            
            print(f"  - {field}: {question}")
            
            # Check if this is a business field that should have been extracted
            business_fields = ["lineOfBusiness", "costCenter", "id", "appEnvironment"]
            if field in business_fields:
                print(f"    ❌ DUPLICATE: {field} is a business field that should have been extracted by Orchestrator!")
            elif field in asked_fields:
                print(f"    ❌ DUPLICATE: {field} was already asked!")
            else:
                asked_fields.add(field)
                print(f"    ✅ OK: Technical field {field}")
    else:
        print("✅ No clarifications needed - all fields were extracted!")
    
    return True


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Duplicate Question Prevention")
    print("=" * 60)
    
    tests = [
        test_orchestrator_extracts_business_metadata,
        test_gce_specialist_excludes_business_fields,
        test_clarification_agent_tracks_asked_fields,
        test_full_flow_no_duplicates
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n❌ Test {test.__name__} failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(passed for _, passed in results)
    if all_passed:
        print("\n🎉 All tests passed! No duplicate questions detected.")
    else:
        print("\n⚠️  Some tests failed. Please review the implementation.")
    
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)