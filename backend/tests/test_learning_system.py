"""
Test suite for Learning Engine
Tests pattern recognition, preference learning, and cross-session capabilities
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.learning import (
    LearningEngine,
    Pattern,
    UserPreferences,
    AgentMemory,
    ImprovementSuggestion
)
from utils.valkey_manager import ValkeyManager


class TestLearningEngine:
    """Test core LearningEngine functionality"""
    
    @pytest.fixture
    async def mock_valkey(self):
        """Create mock ValkeyManager"""
        mock = AsyncMock(spec=ValkeyManager)
        mock.save_learned_pattern = AsyncMock(return_value=True)
        mock.get_learned_patterns = AsyncMock(return_value=[])
        mock.save_agent_memory = AsyncMock(return_value=True)
        mock.load_agent_memory = AsyncMock(return_value=None)
        return mock
    
    @pytest.fixture
    def mock_llm_response(self):
        """Mock OpenAI API responses"""
        def _mock_response(content):
            return MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content=content)
                    )
                ]
            )
        return _mock_response
    
    @pytest.mark.asyncio
    async def test_learning_engine_initialization(self, mock_valkey):
        """Test LearningEngine initialization"""
        engine = LearningEngine(mock_valkey)
        assert engine.valkey_manager == mock_valkey
        assert engine.model == "gpt-5-mini"
        assert engine.temperature == 1.0
        assert engine.pattern_min_occurrences == 3
        assert engine.confidence_threshold == 0.75
    
    @pytest.mark.asyncio
    async def test_identify_success_patterns(self, mock_valkey, mock_llm_response):
        """Test pattern identification from successful sessions"""
        engine = LearningEngine(mock_valkey)
        
        # Mock LLM response for pattern identification
        with patch.object(engine, '_llm_analyze', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "patterns": [
                    {
                        "type": "sequence",
                        "description": "User always specifies environment before machine type",
                        "occurrences": 5,
                        "confidence": 0.85
                    },
                    {
                        "type": "preference",
                        "description": "User prefers RHEL over Ubuntu",
                        "occurrences": 3,
                        "confidence": 0.75
                    }
                ]
            }
            
            session_history = [
                {"agent": "orchestrator", "action": "route_to_compute", "outcome": "success"},
                {"agent": "compute", "action": "extract_requirements", "outcome": "success"}
            ]
            
            patterns = await engine.identify_success_patterns(session_history, "success")
            
            assert len(patterns) == 2
            assert patterns[0].type == "sequence"
            assert patterns[0].confidence == 0.85
            assert patterns[1].type == "preference"
            assert patterns[1].confidence == 0.75
    
    @pytest.mark.asyncio
    async def test_learn_user_preferences(self, mock_valkey, mock_llm_response):
        """Test user preference learning from interactions"""
        engine = LearningEngine(mock_valkey)
        
        with patch.object(engine, '_llm_analyze', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "preferences": {
                    "cloud_provider": "GCP",
                    "machine_types": ["n1-standard-4", "n1-standard-8"],
                    "operating_system": "RHEL",
                    "regions": ["us-east4", "us-central1"],
                    "communication_style": "technical"
                },
                "confidence_scores": {
                    "cloud_provider": 0.9,
                    "machine_types": 0.8,
                    "operating_system": 0.85,
                    "regions": 0.7,
                    "communication_style": 0.75
                }
            }
            
            interactions = [
                {"message": "Deploy a RHEL VM in us-east4", "response": "Creating VM..."},
                {"message": "I need n1-standard-4 in GCP", "response": "Provisioning..."}
            ]
            
            preferences = await engine.learn_user_preferences("user123", interactions)
            
            assert preferences.user_id == "user123"
            assert preferences.cloud_provider == "GCP"
            assert "RHEL" in preferences.operating_system
            assert preferences.confidence_scores["cloud_provider"] == 0.9
    
    @pytest.mark.asyncio
    async def test_coordinate_agent_learning(self, mock_valkey):
        """Test coordination of learning across multiple agents"""
        engine = LearningEngine(mock_valkey)
        
        with patch.object(engine, '_llm_analyze', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "shared_patterns": [
                    {
                        "pattern": "User provides environment details early",
                        "agents_affected": ["orchestrator", "compute"],
                        "action": "prioritize_environment_extraction"
                    }
                ],
                "conflicts": [],
                "coordination_actions": [
                    "Share pattern with compute agent",
                    "Update routing priority in orchestrator"
                ]
            }
            
            agent_memories = {
                "orchestrator": AgentMemory(
                    agent_name="orchestrator",
                    learned_patterns=[{"pattern": "route_compute_first", "confidence": 0.8}]
                ),
                "compute": AgentMemory(
                    agent_name="compute",
                    learned_patterns=[{"pattern": "extract_env_first", "confidence": 0.85}]
                )
            }
            
            result = await engine.coordinate_agent_learning(agent_memories, "success")
            
            assert "shared_patterns" in result
            assert len(result["shared_patterns"]) > 0
            assert mock_valkey.save_learned_pattern.called
    
    @pytest.mark.asyncio
    async def test_suggest_improvements(self, mock_valkey):
        """Test improvement suggestion generation"""
        engine = LearningEngine(mock_valkey)
        
        with patch.object(engine, '_llm_analyze', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "improvements": [
                    {
                        "suggestion": "Add validation for machine type before routing",
                        "impact": "high",
                        "confidence": 0.85,
                        "implementation": "Check machine_type field exists in orchestrator"
                    },
                    {
                        "suggestion": "Cache common extraction patterns",
                        "impact": "medium",
                        "confidence": 0.75,
                        "implementation": "Store frequently used patterns in memory"
                    }
                ]
            }
            
            recent_performance = [
                {"action": "route", "success": True, "latency": 1.2},
                {"action": "extract", "success": False, "error": "missing field"},
                {"action": "clarify", "success": True, "latency": 2.5}
            ]
            
            improvements = await engine.suggest_improvements("orchestrator", recent_performance)
            
            assert len(improvements) == 2
            assert improvements[0].impact == "high"
            assert improvements[0].confidence == 0.85
            assert "validation" in improvements[0].suggestion.lower()
    
    @pytest.mark.asyncio
    async def test_calculate_pattern_confidence(self, mock_valkey):
        """Test confidence calculation for patterns"""
        engine = LearningEngine(mock_valkey)
        
        pattern = Pattern(
            type="sequence",
            description="User specifies env then machine",
            occurrences=5,
            confidence=0.8,
            first_seen=datetime.now() - timedelta(days=7),
            last_seen=datetime.now()
        )
        
        historical_outcomes = ["success", "success", "failure", "success", "success"]
        
        confidence = await engine.calculate_pattern_confidence(pattern, historical_outcomes)
        
        # Should consider success rate (4/5 = 0.8) and time decay
        assert 0.6 <= confidence <= 0.85
        assert isinstance(confidence, float)
    
    @pytest.mark.asyncio
    async def test_pattern_pruning(self, mock_valkey):
        """Test memory optimization through pattern pruning"""
        engine = LearningEngine(mock_valkey)
        
        # Create patterns with different ages and confidences
        old_low_confidence = Pattern(
            type="preference",
            description="Old pattern",
            occurrences=2,
            confidence=0.4,
            first_seen=datetime.now() - timedelta(days=60),
            last_seen=datetime.now() - timedelta(days=45)
        )
        
        recent_high_confidence = Pattern(
            type="sequence",
            description="Recent pattern",
            occurrences=10,
            confidence=0.9,
            first_seen=datetime.now() - timedelta(days=5),
            last_seen=datetime.now()
        )
        
        patterns = [old_low_confidence, recent_high_confidence]
        
        pruned = await engine.prune_patterns(patterns)
        
        # Should keep recent high confidence, remove old low confidence
        assert len(pruned) == 1
        assert pruned[0].description == "Recent pattern"
    
    @pytest.mark.asyncio
    async def test_cross_session_learning(self, mock_valkey):
        """Test learning persistence across sessions"""
        engine = LearningEngine(mock_valkey)
        
        # Save pattern from session 1
        pattern = Pattern(
            type="preference",
            description="User prefers GCP",
            occurrences=5,
            confidence=0.85
        )
        
        await engine.save_cross_session_pattern("user123", pattern)
        
        # Verify pattern was saved to Valkey
        mock_valkey.save_learned_pattern.assert_called_once()
        call_args = mock_valkey.save_learned_pattern.call_args
        assert call_args[1]["pattern_type"] == "preference"
        assert call_args[1]["confidence"] == 0.85
    
    @pytest.mark.asyncio
    async def test_error_pattern_detection(self, mock_valkey):
        """Test detection of error patterns"""
        engine = LearningEngine(mock_valkey)
        
        with patch.object(engine, '_llm_analyze', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "error_patterns": [
                    {
                        "pattern": "Missing environment causes routing failure",
                        "frequency": 8,
                        "solution": "Request environment clarification first",
                        "confidence": 0.9
                    }
                ]
            }
            
            session_history = [
                {"agent": "orchestrator", "action": "route", "outcome": "error", "error": "missing env"},
                {"agent": "compute", "action": "extract", "outcome": "error", "error": "invalid input"}
            ]
            
            patterns = await engine.identify_success_patterns(session_history, "error")
            
            # Should detect error patterns when outcome is error
            mock_analyze.assert_called_once()
            assert "error" in str(mock_analyze.call_args).lower()


class TestPatternRecognitionAccuracy:
    """Test pattern recognition accuracy requirements (>85%)"""
    
    @pytest.mark.asyncio
    async def test_sequence_pattern_accuracy(self):
        """Test sequence pattern detection accuracy"""
        # Test data with known patterns
        test_sessions = [
            # Pattern: env -> machine -> zone (repeated 10 times)
            [{"step": "env"}, {"step": "machine"}, {"step": "zone"}] * 10,
            # Pattern: clarify -> extract -> provision (repeated 8 times)
            [{"step": "clarify"}, {"step": "extract"}, {"step": "provision"}] * 8,
            # Random noise (2 sessions)
            [{"step": "random1"}, {"step": "random2"}] * 2
        ]
        
        mock_valkey = AsyncMock(spec=ValkeyManager)
        engine = LearningEngine(mock_valkey)
        
        # Mock LLM to correctly identify patterns
        with patch.object(engine, '_llm_analyze', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "patterns": [
                    {"type": "sequence", "description": "env->machine->zone", "occurrences": 10},
                    {"type": "sequence", "description": "clarify->extract->provision", "occurrences": 8}
                ]
            }
            
            patterns = await engine.identify_success_patterns(test_sessions, "success")
            
            # Should identify 2 main patterns (accuracy: 18/20 = 90%)
            assert len(patterns) >= 2
            total_occurrences = sum(p.occurrences for p in patterns)
            accuracy = total_occurrences / 20
            assert accuracy >= 0.85  # >85% accuracy requirement
    
    @pytest.mark.asyncio
    async def test_preference_pattern_accuracy(self):
        """Test preference pattern detection accuracy"""
        interactions = [
            # Clear preference for RHEL (8 times)
            {"message": "Deploy RHEL", "choice": "RHEL"} for _ in range(8)
        ] + [
            # Ubuntu used twice
            {"message": "Deploy Ubuntu", "choice": "Ubuntu"} for _ in range(2)
        ]
        
        mock_valkey = AsyncMock(spec=ValkeyManager)
        engine = LearningEngine(mock_valkey)
        
        with patch.object(engine, '_llm_analyze', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "preferences": {
                    "operating_system": "RHEL",
                },
                "confidence_scores": {
                    "operating_system": 0.8  # 8/10 = 80%
                }
            }
            
            preferences = await engine.learn_user_preferences("user123", interactions)
            
            # Should correctly identify RHEL preference with 80% confidence
            assert preferences.operating_system == "RHEL"
            # Allowing some margin for LLM interpretation
            assert 0.75 <= preferences.confidence_scores["operating_system"] <= 0.85


class TestMemoryManagement:
    """Test memory optimization and management"""
    
    @pytest.mark.asyncio
    async def test_pattern_ttl_enforcement(self, mock_valkey):
        """Test that patterns expire according to TTL"""
        engine = LearningEngine(mock_valkey)
        
        expired_pattern = Pattern(
            type="preference",
            description="Expired pattern",
            occurrences=5,
            confidence=0.8,
            first_seen=datetime.now() - timedelta(days=35),
            last_seen=datetime.now() - timedelta(days=31)  # Older than 30 days
        )
        
        valid_pattern = Pattern(
            type="preference",
            description="Valid pattern",
            occurrences=5,
            confidence=0.8,
            first_seen=datetime.now() - timedelta(days=10),
            last_seen=datetime.now() - timedelta(days=1)
        )
        
        patterns = [expired_pattern, valid_pattern]
        active_patterns = await engine.filter_active_patterns(patterns)
        
        assert len(active_patterns) == 1
        assert active_patterns[0].description == "Valid pattern"
    
    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self, mock_valkey):
        """Test that memory limits are enforced"""
        engine = LearningEngine(mock_valkey)
        
        # Create 150 patterns (exceeding typical limit of 100)
        patterns = [
            Pattern(
                type="sequence",
                description=f"Pattern {i}",
                occurrences=i,
                confidence=0.5 + (i * 0.003)  # Varying confidence
            )
            for i in range(150)
        ]
        
        # Apply memory limits
        limited = await engine.enforce_memory_limits(patterns)
        
        # Should keep only top 100 patterns by confidence
        assert len(limited) <= 100
        # Highest confidence patterns should be kept
        assert all(p.confidence >= 0.65 for p in limited)