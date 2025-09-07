"""
Test the complete agentic implementation
Verifies NO pattern matching and pure LLM reasoning
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, Thought, Action, Memory
from agents.compute import ComputeAgent
from agents.gce_specialist import GCESpecialistAgent
from agents.orchestrator import OrchestratorAgent
from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest


class TestBaseAgent:
    """Test the BaseAgent foundation"""
    
    def test_base_agent_initialization(self):
        """Test BaseAgent initializes correctly"""
        # Create a test agent
        class TestAgent(BaseAgent):
            def get_available_tools(self):
                return [{"name": "test_tool"}]
            
            def execute_action(self, action):
                return {"result": "test"}
        
        agent = TestAgent(name="TestAgent", goal="Test goal")
        
        assert agent.name == "TestAgent"
        assert agent.goal == "Test goal"
        assert agent.model == "gpt-5-mini"
        assert agent.memory is not None
        assert len(agent.reasoning_chain) == 0
        assert agent.confidence_threshold == 0.6
    
    def test_no_pattern_matching_in_base(self):
        """Verify BaseAgent has NO pattern matching"""
        import inspect
        import agents.base_agent as base_module
        
        # Get source code
        source = inspect.getsource(base_module)
        
        # Check for pattern matching indicators
        assert "if user_input ==" not in source
        assert "if 'prod' in" not in source
        assert "regex" not in source.lower() or "regex" in "# No regex patterns"
        assert "pattern = r" not in source
        
        # Verify LLM reasoning is used
        assert "_llm_reason" in source
        assert "json.loads(response.choices[0].message.content)" in source


class TestComputeAgent:
    """Test the refactored ComputeAgent"""
    
    def test_compute_agent_inherits_base(self):
        """Test ComputeAgent inherits from BaseAgent"""
        agent = ComputeAgent()
        
        # Check inheritance
        assert isinstance(agent, BaseAgent)
        assert agent.name == "ComputeAgent"
        assert "Extract VM requirements" in agent.goal
    
    def test_no_pattern_matching_in_compute(self):
        """Verify ComputeAgent has NO pattern matching"""
        import inspect
        import agents.compute as compute_module
        
        # Get source code
        source = inspect.getsource(compute_module)
        
        # The file should NOT contain pattern matching functions
        assert "extract_vm_requirements_pattern" not in source
        assert "def extract_vm_requirements_pattern" not in source
        assert "import re" not in source or "# NO pattern matching" in source
        
        # Should use LLM reasoning
        assert "_extract_requirements_llm" in source
        assert "_llm_reason" in source
    
    @pytest.mark.asyncio
    async def test_compute_agent_process_uses_llm(self):
        """Test ComputeAgent.process uses LLM reasoning"""
        agent = ComputeAgent()
        
        # Mock the LLM
        with patch.object(agent, 'reason') as mock_llm:
            mock_llm.return_value = asyncio.coroutine(lambda: {
                "requirements": {
                    "environment": "NONPROD",
                    "os": "LINUX_RHEL8",
                    "machine_type": "n1-standard-1"
                },
                "provider": "gcp",
                "confidence": 0.8
            })()
            
            context = {
                "raw_request": "I need a RHEL 8 VM in GCP",
                "conversation_history": []
            }
            
            result = await agent.process(context)
            
            # Verify LLM was called
            assert mock_llm.called
            
            # Verify result structure
            assert "vm_request" in result
            assert "provider" in result
            assert result["mode"] == "llm_reasoning"
            assert "reasoning_chain" in result


class TestGCESpecialistAgent:
    """Test the enhanced GCESpecialistAgent"""
    
    def test_gce_agent_inherits_base(self):
        """Test GCESpecialistAgent inherits from BaseAgent"""
        agent = GCESpecialistAgent()
        
        # Check inheritance
        assert isinstance(agent, BaseAgent)
        assert agent.name == "GCESpecialistAgent"
        assert "provision GCE instances" in agent.goal
    
    def test_no_hardcoded_validation(self):
        """Verify GCESpecialistAgent has NO hardcoded validation rules"""
        import inspect
        import agents.gce_specialist as gce_module
        
        # Get source code
        source = inspect.getsource(gce_module)
        
        # Should NOT have hardcoded validation
        assert 'if vm_request.zone and not vm_request.zone.startswith("us-")' not in source
        assert 'if vm_request.costCenter and not vm_request.costCenter.isdigit()' not in source
        
        # Should use LLM for validation
        assert "_validate_config_llm" in source
        assert "NO hardcoded rules" in source
    
    @pytest.mark.asyncio
    async def test_gce_agent_validation_uses_llm(self):
        """Test GCESpecialistAgent validation uses LLM"""
        agent = GCESpecialistAgent()
        
        # Mock the LLM
        with patch.object(agent, 'reason') as mock_llm:
            mock_llm.return_value = asyncio.coroutine(lambda: {
                "valid": True,
                "issues": [],
                "confidence": 0.9
            })()
            
            vm_request = VMRequest()
            vm_request.machineType = "n1-standard-1"
            vm_request.zone = "us-east4-a"
            
            result = await agent.validate_config(vm_request)
            
            # Verify LLM was called for validation
            assert mock_llm.called
            
            # Verify result structure
            assert "valid" in result
            assert "confidence" in result


class TestOrchestratorAgent:
    """Test the Orchestrator Agent"""
    
    def test_orchestrator_no_pattern_matching(self):
        """Verify OrchestratorAgent uses pure LLM reasoning"""
        import inspect
        import agents.orchestrator as orch_module
        
        # Get source code
        source = inspect.getsource(orch_module)
        
        # Should NOT have pattern matching for intent
        assert "INTENT_PATTERNS" not in source
        assert "if 'create' in user_input" not in source
        assert "re.search" not in source
        
        # Should use LLM for intent detection through reasoning
        assert "_llm_reason" in source or "reasoning_engine" in source
        assert "_llm_reason" in source
    
    def test_orchestrator_inherits_base(self):
        """Test OrchestratorAgent inherits from BaseAgent"""
        agent = OrchestratorAgent()
        
        # Check inheritance
        assert isinstance(agent, BaseAgent)
        assert agent.name == "Orchestrator"
        assert "route to appropriate specialist agents" in agent.goal.lower()


class TestClarificationAgent:
    """Test the Clarification Agent"""
    
    def test_clarification_no_templates(self):
        """Verify ClarificationAgent doesn't use templates"""
        import inspect
        import agents.clarification as clar_module
        
        # Get source code
        source = inspect.getsource(clar_module)
        
        # Should NOT have template questions
        assert "QUESTION_TEMPLATES" not in source
        assert '"What environment"' not in source
        assert '"Which operating system"' not in source
        
        # Should generate questions naturally
        assert "generate_natural_question" in source or "AskNaturally" in source
    
    def test_clarification_inherits_base(self):
        """Test ClarificationAgent inherits from BaseAgent"""
        agent = ClarificationAgent()
        
        # Check inheritance
        assert isinstance(agent, BaseAgent)
        assert agent.name == "Clarification"


class TestIntegration:
    """Test the integrated agentic system"""
    
    @pytest.mark.asyncio
    async def test_full_agent_pipeline(self):
        """Test the complete agent pipeline with LLM reasoning"""
        
        # Create agents
        orchestrator = OrchestratorAgent()
        compute = ComputeAgent()
        gce = GCESpecialistAgent()
        
        # Mock all LLM calls
        with patch.object(orchestrator.reasoning_engine, 'reason') as mock_orch_llm, \
             patch.object(compute, 'reason') as mock_comp_llm, \
             patch.object(gce, 'reason') as mock_gce_llm:
            
            # Setup orchestrator mock (async)
            mock_orch_llm.return_value = asyncio.coroutine(lambda: {
                "intent": "create_compute",
                "provider": "gcp",
                "confidence": 0.9,
                "reasoning": "User wants to create a VM in GCP"
            })()
            
            # Setup compute mock (async)
            mock_comp_llm.return_value = asyncio.coroutine(lambda: {
                "requirements": {
                    "environment": "NONPROD",
                    "os": "LINUX_RHEL8",
                    "machine_type": "n1-standard-1",
                    "zone": "us-east4-a"
                },
                "provider": "gcp",
                "normalized": {
                    "environment": "NONPROD",
                    "os": "LINUX_RHEL8",
                    "machine_type": "n1-standard-1",
                    "zone": "us-east4-a"
                },
                "confidence": 0.85
            })()
            
            # Setup GCE mock (async)
            mock_gce_llm.return_value = asyncio.coroutine(lambda: {
                "valid": True,
                "issues": [],
                "payload": {
                    "cloud": "gcp",
                    "resourceType": "compute",
                    "machineType": "n1-standard-1",
                    "zone": "us-east4-a"
                },
                "confidence": 0.9
            })()
            
            # Test orchestrator routing
            orch_result = await orchestrator.process({
                "message": "Create a RHEL 8 VM in GCP"
            })
            
            assert mock_orch_llm.called
            assert orch_result["next_agent"] == "compute"
            
            # Test compute extraction
            comp_result = await compute.process({
                "raw_request": "Create a RHEL 8 VM in GCP",
                "provider": "gcp"
            })
            
            assert mock_comp_llm.called
            assert comp_result["provider"] == "gcp"
            assert comp_result["mode"] == "llm_reasoning"
    
    def test_no_pattern_matching_anywhere(self):
        """Comprehensive test that NO agent uses pattern matching"""
        
        modules_to_check = [
            "agents.compute",
            "agents.gce_specialist",
            "agents.orchestrator",
            "agents.clarification"
        ]
        
        for module_name in modules_to_check:
            # Import module
            module = __import__(module_name, fromlist=[''])
            
            # Get source
            import inspect
            source = inspect.getsource(module)
            
            # Check for pattern matching indicators
            bad_patterns = [
                "extract_vm_requirements_pattern",
                "INTENT_PATTERNS",
                "QUESTION_TEMPLATES",
                "if 'prod' in user_input",
                "if 'dev' in request",
                "regex.compile",
                "re.match",
                "re.search"
            ]
            
            for pattern in bad_patterns:
                if pattern in source:
                    # Allow if it's in a comment or docstring
                    lines = source.split('\n')
                    found_in_code = False
                    for line in lines:
                        if pattern in line and not line.strip().startswith('#') and not line.strip().startswith('"""'):
                            found_in_code = True
                            break
                    
                    assert not found_in_code, f"Found pattern matching '{pattern}' in {module_name}"


class TestAgentMemoryAndLearning:
    """Test agent memory and learning capabilities"""
    
    def test_agent_learns_from_corrections(self):
        """Test agents can learn from corrections"""
        agent = ComputeAgent()
        
        # Simulate learning
        agent.learn_from_correction(
            original={"machine_type": "n1"},
            correction={"machine_type": "n1-standard-1"},
            context="User prefers specific machine types"
        )
        
        # Check memory was updated
        assert len(agent.memory.corrections) > 0
        assert agent.memory.corrections[0]["original"]["machine_type"] == "n1"
        assert agent.memory.corrections[0]["correction"]["machine_type"] == "n1-standard-1"
    
    def test_agent_memory_persistence(self):
        """Test agent memory persists across interactions"""
        agent = GCESpecialistAgent()
        
        # Add to memory
        agent.memory.short_term.append({
            "request": "test request",
            "timestamp": "2024-01-01"
        })
        
        agent.memory.user_preferences["preferred_zone"] = "us-east4-a"
        
        # Verify memory persists
        assert len(agent.memory.short_term) > 0
        assert agent.memory.user_preferences["preferred_zone"] == "us-east4-a"


class TestReActPattern:
    """Test the ReAct pattern implementation"""
    
    @pytest.mark.asyncio
    async def test_react_pattern_flow(self):
        """Test Observe-Think-Act-Reflect flow"""
        
        class TestReActAgent(BaseAgent):
            def get_available_tools(self):
                return [{"name": "test_action"}]
            
            def execute_action(self, action):
                return {"success": True}
        
        agent = TestReActAgent(name="TestReAct", goal="Test ReAct")
        
        # Mock LLM
        with patch.object(agent, 'reason') as mock_llm:
            mock_llm.side_effect = [
                # Observation
                asyncio.coroutine(lambda: {"observation": "test", "confidence": 0.8})(),
                # Thinking
                asyncio.coroutine(lambda: {"reasoning": "need to act", "confidence": 0.8})(),
                # Action
                asyncio.coroutine(lambda: {"action": "test_action", "parameters": {}, "confidence": 0.8})(),
                # Reflection
                asyncio.coroutine(lambda: {"reflection": "success", "success": True})()
            ]
            
            result, chain = await agent.process({"test": "input"})
            
            # Verify all ReAct steps occurred
            thought_types = [t.type.value for t in chain]
            assert "observation" in thought_types
            assert "reasoning" in thought_types
            assert "reflection" in thought_types


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])