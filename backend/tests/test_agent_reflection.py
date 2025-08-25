"""
Test suite for Agent-Specific Reflection
Tests enhanced reflection capabilities for each agent type
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent
from agents.clarification import ClarificationAgent
from agents.compute import ComputeAgent
from agents.gce_specialist import GCESpecialistAgent
from utils.learning import Pattern, PatternType
from models.taxi_models import VMRequest


class TestOrchestratorReflection:
    """Test Orchestrator agent reflection capabilities"""
    
    @pytest.fixture
    def orchestrator_agent(self):
        """Create orchestrator agent instance"""
        with patch('agents.orchestrator.OpenAI'):
            agent = OrchestratorAgent()
            agent.learning_engine = AsyncMock()
            return agent
    
    @pytest.mark.asyncio
    async def test_reflect_on_routing(self, orchestrator_agent):
        """Test routing reflection analysis"""
        # Mock LLM response
        with patch.object(orchestrator_agent, '_llm_reason') as mock_llm:
            mock_llm.return_value = {
                "correct_routing": True,
                "better_agent": None,
                "routing_patterns": ["User always mentions cloud provider first"],
                "confidence_adjustment": {"compute": 0.1},
                "lessons": ["Route to compute when VM mentioned"],
                "user_type_pattern": "Technical user with GCP preference"
            }
            
            result = await orchestrator_agent.reflect_on_routing(
                routing_decision="compute",
                outcome="success",
                session_context={"user_input": "I need a VM in GCP"}
            )
            
            assert result["correct_routing"] is True
            assert result["better_agent"] is None
            assert len(result["routing_patterns"]) > 0
            assert "compute" in result["confidence_adjustment"]
    
    @pytest.mark.asyncio
    async def test_evaluate_conversation_flow(self, orchestrator_agent):
        """Test conversation flow evaluation"""
        conversation_history = [
            {"agent": "orchestrator", "action": "route", "result": "compute"},
            {"agent": "compute", "action": "extract", "result": "success"},
            {"agent": "clarification", "action": "ask", "result": "answered"}
        ]
        
        with patch.object(orchestrator_agent, '_llm_reason') as mock_llm:
            mock_llm.return_value = {
                "coherence_score": 9,
                "efficiency_score": 8,
                "unnecessary_steps": [],
                "missed_opportunities": [],
                "satisfaction_indicators": {
                    "positive": ["Clear flow", "Quick resolution"],
                    "negative": []
                },
                "improvements": ["Could skip clarification for expert users"]
            }
            
            result = await orchestrator_agent.evaluate_conversation_flow(conversation_history)
            
            assert result["coherence_score"] == 9
            assert result["efficiency_score"] == 8
            assert len(result["improvements"]) > 0
    
    @pytest.mark.asyncio
    async def test_routing_pattern_learning(self, orchestrator_agent):
        """Test that routing patterns are learned and shared"""
        with patch.object(orchestrator_agent, '_llm_reason') as mock_llm:
            mock_llm.return_value = {
                "correct_routing": True,
                "user_type_pattern": "Developer needing dev environment"
            }
            
            with patch.object(orchestrator_agent, 'share_learning', new_callable=AsyncMock) as mock_share:
                await orchestrator_agent.reflect_on_routing(
                    "compute", "success", {"environment": "dev"}
                )
                
                # Verify pattern was shared
                mock_share.assert_called_once()
                call_args = mock_share.call_args[0]
                assert isinstance(call_args[0], Pattern)
                assert call_args[0].type == PatternType.PREFERENCE


class TestClarificationReflection:
    """Test Clarification agent reflection capabilities"""
    
    @pytest.fixture
    def clarification_agent(self):
        """Create clarification agent instance"""
        with patch('agents.clarification.OpenAI'):
            agent = ClarificationAgent()
            agent.learning_engine = AsyncMock()
            return agent
    
    @pytest.mark.asyncio
    async def test_reflect_on_clarification(self, clarification_agent):
        """Test clarification effectiveness reflection"""
        questions = ["What environment do you need?", "Which zone?"]
        responses = ["production", "us-east4-a"]
        final_data = {"environment": "prod", "zone": "us-east4-a"}
        
        with patch.object(clarification_agent, '_llm_reason') as mock_llm:
            mock_llm.return_value = {
                "question_effectiveness": {
                    "clear_questions": questions,
                    "confusing_questions": [],
                    "effectiveness_score": 9
                },
                "better_phrasings": {
                    "What environment do you need?": "Which environment (dev/staging/prod)?"
                },
                "unnecessary_clarifications": [],
                "response_patterns": ["Users often abbreviate environment names"],
                "lessons": ["Provide options in questions"]
            }
            
            result = await clarification_agent.reflect_on_clarification(
                questions, responses, final_data
            )
            
            assert result["question_effectiveness"]["effectiveness_score"] == 9
            assert len(result["better_phrasings"]) > 0
            assert len(result["response_patterns"]) > 0
    
    @pytest.mark.asyncio
    async def test_learn_field_patterns(self, clarification_agent):
        """Test field-specific pattern learning"""
        field_name = "environment"
        user_inputs = ["prod", "production", "prd", "PROD"]
        corrections = ["production", "production", "production", "production"]
        
        with patch.object(clarification_agent, '_llm_reason') as mock_llm:
            mock_llm.return_value = {
                "field_variations": ["prod", "prd", "PROD", "production"],
                "common_values": ["production", "development", "staging"],
                "error_patterns": ["prd is often production"],
                "validation_rules": ["Must be one of: dev, staging, prod"],
                "default_preference": "production",
                "confidence_model": {
                    "high_confidence_indicators": ["explicit mention"],
                    "low_confidence_indicators": ["abbreviation"]
                }
            }
            
            result = await clarification_agent.learn_field_patterns(
                field_name, user_inputs, corrections
            )
            
            assert len(result["field_variations"]) == 4
            assert "production" in result["common_values"]
            assert result["default_preference"] == "production"
            
            # Check that pattern was stored in memory
            assert f"field_pattern_{field_name}" in clarification_agent.memory.long_term


class TestComputeReflection:
    """Test Compute agent reflection capabilities"""
    
    @pytest.fixture
    def compute_agent(self):
        """Create compute agent instance"""
        with patch('agents.compute.OpenAI'):
            agent = ComputeAgent()
            agent.learning_engine = AsyncMock()
            return agent
    
    @pytest.mark.asyncio
    async def test_reflect_on_extraction(self, compute_agent):
        """Test extraction accuracy reflection"""
        raw_input = "I need a RHEL VM in us-east4"
        extracted = {"os": "RHEL", "zone": "us-east4-a"}
        corrections = {"zone": "us-east4-b"}
        
        with patch.object(compute_agent, '_llm_reason') as mock_llm:
            mock_llm.return_value = {
                "extraction_accuracy": {
                    "correct_fields": ["os"],
                    "incorrect_fields": ["zone"],
                    "missed_fields": ["machine_type"],
                    "accuracy_score": 0.6
                },
                "new_patterns": [
                    {
                        "pattern": "Zone without suffix defaults to -a",
                        "example": "us-east4",
                        "extracts_to": {"zone": "us-east4-a"}
                    }
                ],
                "confidence_adjustments": {"zone": -0.1},
                "ambiguous_terms": ["us-east4"],
                "lessons": ["Ask for zone suffix clarification"]
            }
            
            result = await compute_agent.reflect_on_extraction(
                raw_input, extracted, corrections
            )
            
            assert result["extraction_accuracy"]["accuracy_score"] == 0.6
            assert "zone" in result["extraction_accuracy"]["incorrect_fields"]
            assert len(result["new_patterns"]) > 0
            assert "zone" in result["confidence_adjustments"]
    
    @pytest.mark.asyncio
    async def test_learn_cloud_patterns(self, compute_agent):
        """Test cloud provider pattern learning"""
        user_input = "Deploy on Google Cloud"
        detected_cloud = "gcp"
        was_correct = True
        
        with patch.object(compute_agent, '_llm_reason') as mock_llm:
            mock_llm.return_value = {
                "provider_indicators": {
                    "gcp": ["Google Cloud", "GCP", "GCE"],
                    "aws": ["AWS", "EC2", "Amazon"],
                    "azure": ["Azure", "Microsoft Cloud"]
                },
                "ambiguous_terms": [
                    {
                        "term": "cloud",
                        "could_mean": ["gcp", "aws", "azure"],
                        "disambiguation": "Ask for specific provider"
                    }
                ],
                "common_phrases": {
                    "gcp": ["Google Cloud", "on GCP", "GCE instance"]
                },
                "confidence_factors": {
                    "high_confidence": ["Explicit provider name"],
                    "low_confidence": ["Generic cloud terms"]
                }
            }
            
            result = await compute_agent.learn_cloud_patterns(
                user_input, detected_cloud, was_correct
            )
            
            assert "gcp" in result["provider_indicators"]
            assert len(result["ambiguous_terms"]) > 0
            assert "gcp" in result["common_phrases"]
            
            # Verify success pattern was created
            with patch.object(compute_agent, 'share_learning', new_callable=AsyncMock) as mock_share:
                await compute_agent.learn_cloud_patterns(
                    user_input, detected_cloud, was_correct
                )
                mock_share.assert_called()


class TestGCESpecialistReflection:
    """Test GCE Specialist agent reflection capabilities"""
    
    @pytest.fixture
    def gce_agent(self):
        """Create GCE specialist agent instance"""
        with patch('agents.gce_specialist.OpenAI'):
            agent = GCESpecialistAgent()
            agent.learning_engine = AsyncMock()
            return agent
    
    @pytest.mark.asyncio
    async def test_reflect_on_provisioning(self, gce_agent):
        """Test provisioning reflection"""
        requirements = {
            "machine_type": "n1-standard-4",
            "zone": "us-east4-a",
            "os": "rhel-8"
        }
        taxi_payload = {
            "instance_name": "vm-12345",
            "machine_type": "n1-standard-4",
            "zone": "us-east4-a"
        }
        provision_result = "success"
        
        with patch.object(gce_agent, '_llm_reason') as mock_llm:
            mock_llm.return_value = {
                "configuration_quality": {
                    "optimal": True,
                    "improvements": [],
                    "quality_score": 0.95
                },
                "success_patterns": [
                    {
                        "pattern": "n1-standard-4 works well in us-east4",
                        "configuration": requirements,
                        "success_rate": 0.9
                    }
                ],
                "best_practices": ["Use SSD for production workloads"],
                "common_combinations": [
                    {
                        "fields": ["n1-standard-4", "rhel-8"],
                        "frequency": "Very common"
                    }
                ],
                "lessons": ["This configuration is optimal for web apps"]
            }
            
            result = await gce_agent.reflect_on_provisioning(
                requirements, taxi_payload, provision_result
            )
            
            assert result["configuration_quality"]["optimal"] is True
            assert result["configuration_quality"]["quality_score"] == 0.95
            assert len(result["success_patterns"]) > 0
            assert len(result["best_practices"]) > 0
    
    @pytest.mark.asyncio
    async def test_learn_configuration_patterns(self, gce_agent):
        """Test configuration pattern learning"""
        successful_configs = [
            {"machine_type": "n1-standard-4", "zone": "us-east4-a"},
            {"machine_type": "n1-standard-8", "zone": "us-central1-a"}
        ]
        failed_configs = [
            {"machine_type": "n1-standard-96", "zone": "us-east4-a"}
        ]
        
        with patch.object(gce_agent, '_llm_reason') as mock_llm:
            mock_llm.return_value = {
                "success_patterns": [
                    {
                        "pattern": "Standard machine types work well",
                        "key_factors": ["appropriate sizing"],
                        "confidence": 0.85
                    }
                ],
                "failure_patterns": [
                    {
                        "pattern": "Very large instances often fail",
                        "avoid": "n1-standard-96 in small zones",
                        "alternative": "Use n1-standard-32 or smaller"
                    }
                ],
                "optimal_combinations": [
                    {
                        "machine_type": "n1-standard-4",
                        "os": "rhel-8",
                        "zone": "us-east4-a",
                        "reason": "Best price/performance"
                    }
                ],
                "sizing_recommendations": {
                    "web_app": {
                        "recommended_type": "n1-standard-4",
                        "min_resources": {"cpu": 4, "memory": "15GB"}
                    }
                },
                "zone_preferences": {
                    "us-east4-a": "Low latency, high availability"
                }
            }
            
            result = await gce_agent.learn_configuration_patterns(
                successful_configs, failed_configs
            )
            
            assert len(result["success_patterns"]) > 0
            assert len(result["failure_patterns"]) > 0
            assert len(result["optimal_combinations"]) > 0
            assert "web_app" in result["sizing_recommendations"]
            
            # Check that config model was stored
            assert "gce_config_model" in gce_agent.memory.long_term


class TestCrossAgentLearning:
    """Test learning coordination between agents"""
    
    @pytest.mark.asyncio
    async def test_agent_memory_snapshots(self):
        """Test that agents can generate memory snapshots"""
        with patch('agents.orchestrator.OpenAI'):
            orchestrator = OrchestratorAgent()
            snapshot = orchestrator.get_agent_memory_snapshot()
            
            assert snapshot.agent_name == "Orchestrator"
            assert "success_rate" in snapshot.performance_metrics
            assert "patterns_learned" in snapshot.performance_metrics
    
    @pytest.mark.asyncio
    async def test_pattern_sharing(self):
        """Test that patterns are shared between agents"""
        with patch('agents.compute.OpenAI'):
            compute_agent = ComputeAgent()
            compute_agent.learning_engine = AsyncMock()
            
            pattern = Pattern(
                type=PatternType.SUCCESS,
                description="Test pattern",
                occurrences=5,
                confidence=0.9
            )
            
            with patch('utils.valkey_manager.valkey_manager.save_learned_pattern', new_callable=AsyncMock) as mock_save:
                await compute_agent.share_learning(pattern, 0.9)
                
                mock_save.assert_called_once()
                call_kwargs = mock_save.call_args[1]
                assert call_kwargs["agent_name"] == "ComputeAgent"
                assert call_kwargs["confidence"] == 0.9


class TestReflectionIntegration:
    """Test reflection integration with base agent"""
    
    @pytest.mark.asyncio
    async def test_enhanced_reflect_with_learning(self):
        """Test that enhanced reflect integrates with learning engine"""
        with patch('agents.orchestrator.OpenAI'):
            agent = OrchestratorAgent()
            
            # Mock learning engine
            mock_learning = AsyncMock()
            mock_learning.identify_success_patterns = AsyncMock(return_value=[
                Pattern(
                    type=PatternType.SUCCESS,
                    description="Test success pattern",
                    occurrences=3,
                    confidence=0.85
                )
            ])
            mock_learning.confidence_threshold = 0.75
            agent.learning_engine = mock_learning
            
            # Mock LLM reason
            with patch.object(agent, '_llm_reason') as mock_llm:
                mock_llm.return_value = {
                    "reflection": "Action was successful",
                    "success": True,
                    "lessons": ["Learned something new"],
                    "patterns_observed": ["Pattern 1"],
                    "memory_updates": {"key": "value"},
                    "confidence_adjustment": 0.1
                }
                
                # Perform reflection
                from agents.base_agent import Action
                action = Action(
                    name="test_action",
                    parameters={},
                    reasoning="test",
                    confidence=0.8
                )
                
                thought = await agent.reflect(action, "success", {"context": "test"})
                
                assert thought.content == "Action was successful"
                assert thought.type.value == "reflection"
                
                # Verify learning engine was called
                mock_learning.identify_success_patterns.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_apply_learned_patterns(self):
        """Test application of previously learned patterns"""
        with patch('agents.compute.OpenAI'):
            agent = ComputeAgent()
            agent.learning_engine = AsyncMock()
            agent.learning_engine.pattern_min_confidence = 0.6
            
            # Mock pattern retrieval
            with patch('utils.valkey_manager.valkey_manager.get_learned_patterns', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = [
                    {
                        "type": "sequence",
                        "description": "Extract environment first",
                        "confidence": 0.8,
                        "occurrences": 5
                    }
                ]
                
                # Mock LLM relevance check
                with patch.object(agent, '_llm_reason') as mock_llm:
                    mock_llm.return_value = {"relevant": True, "confidence": 0.8}
                    
                    patterns = await agent.apply_learned_patterns({"input": "test"})
                    
                    assert len(patterns) == 1
                    assert patterns[0].description == "Extract environment first"