"""
Test Suite for Valkey Integration
Tests memory persistence, session management, and cross-session learning
"""

import pytest
import asyncio
import json
from datetime import datetime
import os
import sys

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.valkey_manager import ValkeyManager
from models.agent_session import AgentSession, ConversationState, Message, AgentMemorySnapshot
from agents.base_agent import BaseAgent, Action, Thought, ThoughtType

# Mock environment variables for testing
os.environ['VALKEY_HOST'] = 'localhost'
os.environ['VALKEY_PORT'] = '6379'
os.environ['VALKEY_AGENT_DB'] = '2'  # Use separate DB for tests
os.environ['AGENT_REASONING_MODEL'] = 'gpt-5-mini'
os.environ['REASONING_TEMPERATURE'] = '1.0'

class TestValkeyManager:
    """Test Valkey Manager functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.valkey_manager = ValkeyManager()
        self.test_session_id = "test-session-123"
        self.test_agent_name = "test-agent"
        
        # Clean up any existing test data
        yield
        
        # Cleanup after test
        try:
            client = self.valkey_manager.get_sync_client()
            # Delete all test keys
            for key in client.keys("*test*"):
                client.delete(key)
        except:
            pass
    
    @pytest.mark.asyncio
    async def test_valkey_connection(self):
        """Test Valkey connection and health check"""
        health = await self.valkey_manager.health_check()
        assert health is True, "Valkey should be healthy"
    
    @pytest.mark.asyncio
    async def test_save_and_load_agent_memory(self):
        """Test saving and loading agent memory"""
        # Test data
        memory_data = {
            "context": "test context",
            "observations": ["obs1", "obs2"],
            "timestamp": datetime.now().isoformat()
        }
        
        # Save memory
        saved = await self.valkey_manager.save_agent_memory(
            agent_name=self.test_agent_name,
            session_id=self.test_session_id,
            memory_type="short_term",
            data=memory_data,
            ttl=300
        )
        assert saved is True, "Memory should be saved successfully"
        
        # Load memory
        loaded = await self.valkey_manager.load_agent_memory(
            agent_name=self.test_agent_name,
            session_id=self.test_session_id,
            memory_type="short_term"
        )
        assert loaded is not None, "Memory should be loaded"
        assert loaded["context"] == "test context"
        assert loaded["observations"] == ["obs1", "obs2"]
    
    @pytest.mark.asyncio
    async def test_learned_patterns(self):
        """Test saving and retrieving learned patterns"""
        # Save pattern with high confidence
        pattern_data = {
            "input": "create a VM in GCP",
            "extracted": {"provider": "gcp", "resource": "vm"},
            "success": True
        }
        
        saved = await self.valkey_manager.save_learned_pattern(
            agent_name=self.test_agent_name,
            pattern_type="extraction",
            pattern_data=pattern_data,
            confidence=0.9
        )
        assert saved is True, "Pattern should be saved"
        
        # Save pattern with low confidence (should not save)
        low_conf_saved = await self.valkey_manager.save_learned_pattern(
            agent_name=self.test_agent_name,
            pattern_type="extraction",
            pattern_data={"test": "low"},
            confidence=0.3
        )
        assert low_conf_saved is False, "Low confidence pattern should not be saved"
        
        # Get patterns
        patterns = await self.valkey_manager.get_learned_patterns(
            agent_name=self.test_agent_name,
            pattern_type="extraction",
            min_confidence=0.8
        )
        assert len(patterns) == 1, "Should retrieve one high-confidence pattern"
        assert patterns[0]["input"] == "create a VM in GCP"
        assert patterns[0]["confidence"] == 0.9
    
    @pytest.mark.asyncio
    async def test_session_management(self):
        """Test session save and load"""
        session_data = {
            "session_id": self.test_session_id,
            "created_at": datetime.now().isoformat(),
            "state": "gathering_info",
            "current_intent": "create_compute",
            "vm_request": {"os": "LINUX_RHEL8", "zone": "us-central1-a"}
        }
        
        # Save session
        saved = await self.valkey_manager.save_session(
            session_id=self.test_session_id,
            session_data=session_data,
            ttl=600
        )
        assert saved is True, "Session should be saved"
        
        # Load session
        loaded = await self.valkey_manager.load_session(self.test_session_id)
        assert loaded is not None, "Session should be loaded"
        assert loaded["session_id"] == self.test_session_id
        assert loaded["current_intent"] == "create_compute"
        assert loaded["vm_request"]["os"] == "LINUX_RHEL8"
    
    @pytest.mark.asyncio
    async def test_conversation_history(self):
        """Test conversation history management"""
        # Add messages
        messages = [
            {"role": "user", "content": "I need a VM", "timestamp": datetime.now().isoformat()},
            {"role": "assistant", "content": "What OS?", "timestamp": datetime.now().isoformat()},
            {"role": "user", "content": "RHEL 8", "timestamp": datetime.now().isoformat()}
        ]
        
        for msg in messages:
            added = await self.valkey_manager.append_conversation(
                session_id=self.test_session_id,
                message=msg
            )
            assert added is True, f"Message should be added: {msg}"
        
        # Get recent history
        history = await self.valkey_manager.get_conversation_history(
            session_id=self.test_session_id,
            limit=2
        )
        assert len(history) == 2, "Should get 2 recent messages"
        assert history[1]["content"] == "RHEL 8"
        assert history[0]["content"] == "What OS?"
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test expired session cleanup"""
        # Create test session
        await self.valkey_manager.save_session(
            session_id="expired-session-1",
            session_data={"test": "data"},
            ttl=1  # 1 second TTL
        )
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # Clean up expired sessions
        cleaned = await self.valkey_manager.cleanup_expired_sessions()
        assert cleaned >= 0, "Cleanup should complete without error"


class TestAgentSession:
    """Test AgentSession model"""
    
    def test_agent_session_creation(self):
        """Test creating an agent session"""
        session = AgentSession(
            session_id="test-123",
            state=ConversationState.INITIAL
        )
        assert session.session_id == "test-123"
        assert session.state == ConversationState.INITIAL
        assert len(session.conversation_history) == 0
    
    def test_add_message(self):
        """Test adding messages to session"""
        session = AgentSession(session_id="test-123")
        
        session.add_message("user", "Hello", {"intent": "greeting"})
        session.add_message("assistant", "Hi there!")
        
        assert len(session.conversation_history) == 2
        assert session.conversation_history[0].role == "user"
        assert session.conversation_history[0].content == "Hello"
        assert session.conversation_history[1].role == "assistant"
    
    def test_save_agent_memory(self):
        """Test saving agent memory snapshot"""
        session = AgentSession(session_id="test-123")
        
        memory = AgentMemorySnapshot(
            agent_name="test-agent",
            short_term={"recent": "interaction"},
            long_term={"learned": "pattern"},
            confidence_scores={"extraction": 0.9}
        )
        
        session.save_agent_memory("test-agent", memory)
        assert "test-agent" in session.agent_memories
        assert session.agent_memories["test-agent"].short_term["recent"] == "interaction"
    
    def test_add_correction(self):
        """Test tracking corrections"""
        session = AgentSession(session_id="test-123")
        
        session.add_correction(
            field="os",
            old_value="WINDOWS",
            new_value="LINUX_RHEL8",
            corrected_by="user"
        )
        
        assert len(session.corrections_history) == 1
        assert session.corrections_history[0]["field"] == "os"
        assert session.corrections_history[0]["new_value"] == "LINUX_RHEL8"
    
    def test_session_serialization(self):
        """Test converting session to/from Valkey dict"""
        session = AgentSession(session_id="test-123")
        session.add_message("user", "Test message")
        session.current_intent = "create_compute"
        session.user_preferences = {"provider": "gcp"}
        
        # Convert to dict
        session_dict = session.to_valkey_dict()
        assert session_dict["session_id"] == "test-123"
        assert session_dict["current_intent"] == "create_compute"
        assert len(session_dict["conversation_history"]) == 1
        
        # Recreate from dict
        restored = AgentSession.from_valkey_dict(session_dict)
        assert restored.session_id == "test-123"
        assert restored.current_intent == "create_compute"
        assert len(restored.conversation_history) == 1
        assert restored.conversation_history[0].content == "Test message"


class TestBaseAgentMemoryPersistence:
    """Test BaseAgent memory persistence with Valkey"""
    
    class TestAgent(BaseAgent):
        """Concrete test agent"""
        def get_available_tools(self):
            return [{"name": "test_tool", "description": "Test"}]
        
        def execute_action(self, action: Action):
            return {"result": "test"}
    
    @pytest.mark.asyncio
    async def test_agent_save_load_memory(self):
        """Test agent saving and loading memory via Valkey"""
        agent = self.TestAgent(name="test-agent", goal="test")
        session_id = "test-session-456"
        
        # Add some test data to memory
        agent.memory.short_term = [
            {"input": "test", "timestamp": datetime.now().isoformat()}
        ]
        agent.memory.long_term = {"pattern": "learned"}
        agent.memory.corrections = [
            {"original": "wrong", "correction": "right"}
        ]
        agent.memory.user_preferences = {"style": "concise"}
        
        # Save memory
        await agent.save_memory(session_id)
        
        # Create new agent and load memory
        new_agent = self.TestAgent(name="test-agent", goal="test")
        await new_agent.load_memory(session_id)
        
        # Verify memory loaded correctly
        assert len(new_agent.memory.short_term) == 1
        assert new_agent.memory.short_term[0]["input"] == "test"
        assert new_agent.memory.long_term["pattern"] == "learned"
        assert len(new_agent.memory.corrections) == 1
        assert new_agent.memory.corrections[0]["correction"] == "right"
        assert new_agent.memory.user_preferences["style"] == "concise"
    
    @pytest.mark.asyncio
    async def test_process_with_session(self):
        """Test processing with session awareness"""
        agent = self.TestAgent(name="test-agent", goal="test")
        session_id = "test-session-789"
        
        # Add initial memory
        agent.memory.user_preferences = {"initial": True}
        await agent.save_memory(session_id)
        
        # Process with session (this would normally update memory)
        # Note: This test is limited without a real LLM
        result = await agent.process_with_session(
            input_data={"test": "input"},
            session_id=session_id
        )
        
        # Memory should be saved after processing
        # Create new agent to verify persistence
        verification_agent = self.TestAgent(name="test-agent", goal="test")
        await verification_agent.load_memory(session_id)
        assert verification_agent.memory.user_preferences["initial"] is True


@pytest.mark.asyncio
async def test_full_integration():
    """Test full integration of Valkey with session and agents"""
    valkey_manager = ValkeyManager()
    
    # Create and save a session
    session = AgentSession(
        session_id="integration-test-123",
        state=ConversationState.GATHERING_INFO
    )
    session.add_message("user", "I need a VM in GCP")
    session.current_intent = "create_compute"
    session.current_agent = "compute"
    
    # Save session
    saved = await valkey_manager.save_session(
        session_id=session.session_id,
        session_data=session.to_valkey_dict()
    )
    assert saved is True
    
    # Save agent memory for the session
    await valkey_manager.save_agent_memory(
        agent_name="compute",
        session_id=session.session_id,
        memory_type="short_term",
        data={"extracted": {"provider": "gcp", "resource": "vm"}}
    )
    
    # Save a learned pattern
    await valkey_manager.save_learned_pattern(
        agent_name="compute",
        pattern_type="provider_detection",
        pattern_data={"keywords": ["GCP", "Google Cloud"], "provider": "gcp"},
        confidence=0.95
    )
    
    # Load everything back
    loaded_session = await valkey_manager.load_session(session.session_id)
    assert loaded_session is not None
    assert loaded_session["current_intent"] == "create_compute"
    
    loaded_memory = await valkey_manager.load_agent_memory(
        agent_name="compute",
        session_id=session.session_id,
        memory_type="short_term"
    )
    assert loaded_memory["extracted"]["provider"] == "gcp"
    
    patterns = await valkey_manager.get_learned_patterns(
        agent_name="compute",
        pattern_type="provider_detection",
        min_confidence=0.9
    )
    assert len(patterns) == 1
    assert patterns[0]["provider"] == "gcp"
    
    # Cleanup
    client = valkey_manager.get_sync_client()
    for key in client.keys("*integration-test*"):
        client.delete(key)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])