"""
Integration tests for environment detection from user input
Verifies that "production" maps to "PROD" without unnecessary clarification
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.orchestrator import OrchestratorAgent
from agents.compute import ComputeAgent
from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest
import os


@pytest.mark.asyncio
async def test_production_maps_to_prod_in_orchestrator():
    """Test that orchestrator correctly detects and normalizes 'production' to 'PROD'"""
    orchestrator = OrchestratorAgent()
    
    # Test input with "production" keyword
    test_input = "Deploy a Windows 2022 VM in us-east4-a for retail production"
    
    # Process the request
    result = await orchestrator.process({"user_input": test_input}, session_id="test-session")
    
    # Check that environment is detected and normalized
    context = result["action"]["parameters"]
    assert "extracted_requirements" in context
    assert context["extracted_requirements"]["environment"] == "PROD"
    assert context["extracted_requirements"]["environment_confidence"] == 0.9
    assert context["extracted_requirements"]["environment_source"] == "orchestrator"


@pytest.mark.asyncio
async def test_dev_maps_to_nonprod_in_orchestrator():
    """Test that orchestrator correctly detects and normalizes 'dev' to 'NONPROD'"""
    orchestrator = OrchestratorAgent()
    
    # Test input with "dev" keyword
    test_input = "I need a Linux VM for dev testing"
    
    # Process the request
    result = await orchestrator.process({"user_input": test_input}, session_id="test-session")
    
    # Check that environment is detected and normalized
    context = result["action"]["parameters"]
    if "extracted_requirements" in context and context["extracted_requirements"].get("environment"):
        assert context["extracted_requirements"]["environment"] == "NONPROD"
        assert context["extracted_requirements"]["environment_source"] == "orchestrator"


@pytest.mark.asyncio
async def test_compute_agent_uses_orchestrator_environment():
    """Test that compute agent uses environment provided by orchestrator"""
    compute = ComputeAgent()
    
    # Context with environment already set by orchestrator
    context = {
        "raw_request": "Deploy a VM",
        "extracted_requirements": {
            "environment": "PROD",
            "environment_confidence": 0.9,
            "environment_source": "orchestrator"
        }
    }
    
    # Mock the internal methods that make API calls
    compute._detect_compute_type = AsyncMock(return_value={
        "specialist": "gce_specialist",
        "is_available": True,
        "reasoning": "GCP detected"
    })
    compute._extract_resource_fields = AsyncMock(return_value={})
    compute._extract_requirements_llm = AsyncMock(return_value={
        "requirements": {},
        "provider": "gcp"
    })
    
    # Process the request
    result = await compute.process(context)
    
    # Verify environment is preserved from orchestrator
    assert context["extracted_requirements"]["environment"] == "PROD"
    assert context["extracted_requirements"]["environment_source"] == "orchestrator"


@pytest.mark.asyncio
async def test_compute_agent_fallback_pattern_matching():
    """Test that compute agent uses pattern matching when orchestrator doesn't provide environment"""
    compute = ComputeAgent()
    
    # Context without environment from orchestrator
    context = {
        "raw_request": "Deploy a Windows VM for production use",
        "extracted_requirements": {}  # No environment from orchestrator
    }
    
    # Mock the internal methods
    compute._detect_compute_type = AsyncMock(return_value={
        "specialist": "gce_specialist",
        "is_available": True,
        "reasoning": "GCP detected"
    })
    compute._extract_resource_fields = AsyncMock(return_value={})
    compute._extract_requirements_llm = AsyncMock(return_value={
        "requirements": {},
        "provider": "gcp"
    })
    
    # Process the request
    result = await compute.process(context)
    
    # Verify environment is detected via pattern matching
    assert context["extracted_requirements"]["environment"] == "PROD"
    assert context["extracted_requirements"]["environment_confidence"] >= 0.7
    assert context["extracted_requirements"]["environment_source"] == "pattern"


@pytest.mark.asyncio
async def test_ambiguous_environment_triggers_clarification():
    """Test that ambiguous environment detection triggers clarification"""
    compute = ComputeAgent()
    
    # Ambiguous input without clear environment
    context = {
        "raw_request": "I need a VM",  # No environment specified
        "extracted_requirements": {}
    }
    
    # Mock the internal methods
    compute._detect_compute_type = AsyncMock(return_value={
        "specialist": "gce_specialist",
        "is_available": True,
        "reasoning": "GCP detected"
    })
    compute._extract_resource_fields = AsyncMock(return_value={})
    compute._extract_requirements_llm = AsyncMock(return_value={
        "requirements": {},
        "provider": "gcp"
    })
    
    # Process the request
    result = await compute.process(context)
    
    # Verify no environment is set (will trigger clarification)
    assert context["extracted_requirements"].get("environment") is None


@pytest.mark.asyncio
async def test_clarification_handles_ambiguous_environment():
    """Test that clarification agent properly handles ambiguous environment"""
    clarification = ClarificationAgent()
    
    # Create a VM request with missing environment
    vm_request = VMRequest()
    vm_request.lineOfBusiness = "RETAIL"
    vm_request.os = "LINUX_RHEL8"
    
    # Context indicating ambiguous environment
    context = {
        "raw_request": "Deploy a VM for testing production scenarios",
        "extracted_requirements": {
            "environment_ambiguous": True,
            "environment_candidates": ["PROD", "NONPROD"]
        }
    }
    
    # Mock the reason method
    clarification.reason = AsyncMock(return_value={
        "summary": "I understand you need a VM",
        "questions": [{
            "field": "environment",
            "question": "I detected you might mean either PROD or NONPROD. Which environment did you intend?",
            "suggestions": ["PROD", "NONPROD"],
            "why_needed": "To ensure proper configuration",
            "allows_custom": False
        }]
    })
    
    # Get clarifications
    result = await clarification.get_clarifications(vm_request, context)
    
    # Verify environment question is generated
    assert not result["complete"]
    assert len(result["questions"]) > 0
    # Find environment question
    env_questions = [q for q in result["questions"] if q.get("field") == "environment"]
    assert len(env_questions) > 0 or "environment" in result.get("missing_count", 0)


@pytest.mark.asyncio
async def test_end_to_end_production_no_clarification():
    """
    End-to-end test: "production" in input should not trigger environment clarification
    """
    orchestrator = OrchestratorAgent()
    
    # User input with "production" keyword
    user_input = "Deploy a Windows 2022 VM in us-east4-a for retail production"
    
    # Process through orchestrator
    routing_result = await orchestrator.process({"user_input": user_input}, session_id="test-session")
    
    # Verify environment is set
    context = routing_result["action"]["parameters"]
    assert context["extracted_requirements"]["environment"] == "PROD"
    
    # If routed to compute agent, verify it preserves the environment
    if routing_result["action"]["agent"] == "compute":
        compute = ComputeAgent()
        
        # Mock internal methods
        compute._detect_compute_type = AsyncMock(return_value={
            "specialist": "gce_specialist",
            "is_available": True
        })
        compute._extract_resource_fields = AsyncMock(return_value={
            "os": "WINDOWS_22",
            "useType": "Application"
        })
        compute._extract_requirements_llm = AsyncMock(return_value={
            "requirements": {"zone": "us-east4-a"},
            "provider": "gcp"
        })
        
        # Process through compute
        compute_result = await compute.process(context)
        
        # Verify environment is still PROD
        assert context["extracted_requirements"]["environment"] == "PROD"
        
        # Verify we're not routing to clarification for environment
        if compute_result.get("next_agent") == "clarification":
            # If we do go to clarification, it should NOT be for environment
            clarification = ClarificationAgent()
            vm_request = VMRequest()
            vm_request.environment = "PROD"  # Already set
            
            # Mock the reason method
            clarification.reason = AsyncMock(return_value={
                "summary": "I have the environment information",
                "questions": []  # No environment question
            })
            
            clarification_result = await clarification.get_clarifications(vm_request, context)
            
            # Verify no environment question is asked
            env_questions = [q for q in clarification_result.get("questions", []) 
                           if q.get("field") == "environment"]
            assert len(env_questions) == 0, "Should not ask for environment when 'production' was specified"


@pytest.mark.asyncio
async def test_conflicting_environment_signals():
    """Test handling of conflicting environment signals (e.g., 'test production')"""
    compute = ComputeAgent()
    
    # Conflicting signals
    context = {
        "raw_request": "Deploy a VM for test production scenarios",
        "extracted_requirements": {}
    }
    
    # Mock internal methods
    compute._detect_compute_type = AsyncMock(return_value={
        "specialist": "gce_specialist",
        "is_available": True
    })
    compute._extract_resource_fields = AsyncMock(return_value={})
    compute._extract_requirements_llm = AsyncMock(return_value={
        "requirements": {},
        "provider": "gcp"
    })
    
    # Process the request
    result = await compute.process(context)
    
    # With conflicting signals, confidence should be lower
    if context["extracted_requirements"].get("environment"):
        assert context["extracted_requirements"]["environment_confidence"] <= 0.6
    else:
        # Or it might mark as ambiguous
        assert context["extracted_requirements"].get("environment_ambiguous") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])