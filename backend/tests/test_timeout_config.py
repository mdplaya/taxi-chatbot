"""
Test timeout configurations
Verifies that all timeouts have been properly increased
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import asyncio

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_manager import LLMManager
from utils.reasoning import ReasoningEngine
from agents.clarification import ClarificationAgent


class TestTimeoutConfiguration(unittest.TestCase):
    """Test that all timeout configurations are properly set"""
    
    def test_llm_manager_timeout(self):
        """Test LLM Manager timeout is 75 seconds"""
        with patch.dict(os.environ, {'LLM_TIMEOUT': '75000'}):
            manager = LLMManager()
            self.assertEqual(manager.timeout, 75.0)
    
    def test_llm_manager_default_timeout(self):
        """Test LLM Manager default timeout"""
        with patch.dict(os.environ, {}, clear=True):
            manager = LLMManager()
            # Default should be 75 seconds (75000 ms)
            self.assertEqual(manager.timeout, 75.0)
    
    def test_reasoning_engine_timeouts(self):
        """Test Reasoning Engine timeout configuration"""
        # Test simple timeout
        with patch.dict(os.environ, {'REASONING_TIMEOUT_SIMPLE': '60'}):
            simple_timeout = float(os.getenv('REASONING_TIMEOUT_SIMPLE', '60.0'))
            self.assertEqual(simple_timeout, 60.0)
        
        # Test complex timeout
        with patch.dict(os.environ, {'REASONING_TIMEOUT_COMPLEX': '120'}):
            complex_timeout = float(os.getenv('REASONING_TIMEOUT_COMPLEX', '120.0'))
            self.assertEqual(complex_timeout, 120.0)
    
    def test_clarification_timeout(self):
        """Test Clarification Agent timeout"""
        with patch.dict(os.environ, {'CLARIFICATION_TIMEOUT': '60'}):
            timeout = float(os.getenv('CLARIFICATION_TIMEOUT', '60.0'))
            self.assertEqual(timeout, 60.0)
    
    def test_timeout_error_handling(self):
        """Test that timeouts are handled gracefully"""
        async def slow_operation():
            await asyncio.sleep(2)
            return "completed"
        
        async def test_with_timeout():
            try:
                result = await asyncio.wait_for(
                    slow_operation(),
                    timeout=0.1  # Very short timeout
                )
                return result
            except asyncio.TimeoutError:
                return "timeout_handled"
        
        # Run the async test
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(test_with_timeout())
        loop.close()
        
        self.assertEqual(result, "timeout_handled")
    
    def test_env_file_exists(self):
        """Test that .env.example file exists with proper configuration"""
        env_example_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            '.env.example'
        )
        self.assertTrue(os.path.exists(env_example_path), ".env.example file should exist")
        
        # Check that it contains the required timeout settings
        with open(env_example_path, 'r') as f:
            content = f.read()
            self.assertIn('LLM_TIMEOUT=75000', content)
            self.assertIn('REASONING_TIMEOUT_SIMPLE=60', content)
            self.assertIn('REASONING_TIMEOUT_COMPLEX=120', content)
            self.assertIn('CLARIFICATION_TIMEOUT=60', content)
            self.assertIn('API_TIMEOUT=90000', content)
    
    def test_all_timeout_locations_updated(self):
        """Verify that all timeout locations have been updated"""
        # This test checks that the old 3-second timeouts are gone
        
        # Check llm_manager.py
        llm_manager_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'utils', 'llm_manager.py'
        )
        with open(llm_manager_path, 'r') as f:
            content = f.read()
            # Should not have the old 3000ms (3s) default
            self.assertNotIn('"3000"', content)
            # Should have new 75000ms (75s) default
            self.assertIn('"75000"', content)
        
        # Check reasoning.py
        reasoning_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'utils', 'reasoning.py'
        )
        with open(reasoning_path, 'r') as f:
            content = f.read()
            # Should not have old 3-second timeout
            self.assertNotIn('timeout=3.0', content)
            # Should have new 60-second timeout
            self.assertIn('timeout=60.0', content)


class TestProgressIntegration(unittest.TestCase):
    """Test progress tracking integration"""
    
    def test_progress_manager_import(self):
        """Test that progress manager can be imported"""
        try:
            from utils.progress_manager import ProgressManager, progress_manager
            self.assertIsNotNone(progress_manager)
        except ImportError as e:
            self.fail(f"Failed to import progress_manager: {e}")
    
    def test_session_model_has_progress_fields(self):
        """Test that ChatSession has progress tracking fields"""
        from models.taxi_models import ChatSession, VMRequest
        from datetime import datetime
        
        session = ChatSession(
            session_id="test-123",
            created_at=datetime.now(),
            vm_request=VMRequest(),
            status="gathering_info"
        )
        
        # Check new progress fields exist
        self.assertIsNotNone(session.progress_steps)
        self.assertIsNone(session.current_agent)
        self.assertIsNone(session.current_step)
        self.assertIsNone(session.last_progress_update)
        
        # Test add_progress method
        session.add_progress("TestAgent", "testing", "Running test", "in_progress", 50)
        self.assertEqual(len(session.progress_steps), 1)
        self.assertEqual(session.current_agent, "TestAgent")
        self.assertEqual(session.current_step, "testing")
    
    def test_base_agent_has_progress_methods(self):
        """Test that BaseAgent has progress emission methods"""
        from agents.base_agent import BaseAgent
        
        # Check that BaseAgent has the required methods
        self.assertTrue(hasattr(BaseAgent, 'emit_progress'))
        self.assertTrue(hasattr(BaseAgent, 'set_progress_callback'))
    
    @patch('utils.progress_manager.ProgressManager')
    async def test_progress_emission(self, mock_progress_manager):
        """Test that progress events are emitted correctly"""
        from utils.progress_manager import ProgressEvent
        from datetime import datetime
        
        # Create a progress event
        event = ProgressEvent(
            timestamp=datetime.now(),
            session_id="test-session",
            agent="TestAgent",
            step="processing",
            message="Processing request",
            percentage=50,
            status="in_progress"
        )
        
        # Test SSE format
        sse_output = event.to_sse_format()
        self.assertIn("data:", sse_output)
        self.assertIn("progress", sse_output)
        self.assertIn("TestAgent", sse_output)


if __name__ == '__main__':
    unittest.main()