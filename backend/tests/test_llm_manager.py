"""
Test suite for LLM Manager functionality
"""
import pytest
import asyncio
import os
import time
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from utils.llm_manager import LLMManager


class TestLLMManager:
    """Test LLM Manager core functionality"""
    
    def test_offline_mode_without_api_key(self):
        """Test that system runs in offline mode without API key"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            manager = LLMManager()
            assert manager.get_mode() == "offline"
    
    def test_online_mode_with_valid_key(self):
        """Test that system detects online mode with valid-looking key"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-valid-test-key-1234567890'}):
            manager = LLMManager()
            assert manager.get_mode() == "online"
    
    def test_offline_mode_with_invalid_key_format(self):
        """Test that invalid key format results in offline mode"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'invalid-key'}):
            manager = LLMManager()
            assert manager.get_mode() == "offline"
    
    def test_mode_caching(self):
        """Test that mode is cached for the configured TTL"""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-valid-test-key-1234567890',
            'LLM_CACHE_TTL': '1'  # 1 second cache
        }):
            manager = LLMManager()
            
            # First call should set the cache
            mode1 = manager.get_mode()
            assert mode1 == "online"
            
            # Change the API key (simulating it becoming invalid)
            manager.api_key = ""
            
            # Should still return cached value
            mode2 = manager.get_mode()
            assert mode2 == "online"  # Still cached
            
            # Wait for cache to expire
            time.sleep(1.1)
            
            # Now should re-check and return offline
            manager._check_initial_mode()  # Force recheck
            mode3 = manager.get_mode()
            assert mode3 == "offline"
    
    @pytest.mark.asyncio
    async def test_timeout_functionality(self):
        """Test that calls timeout after configured duration"""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-valid-test-key-1234567890',
            'LLM_TIMEOUT': '100'  # 100ms timeout
        }):
            manager = LLMManager()
            
            # Create a slow function
            async def slow_function():
                await asyncio.sleep(1)  # Sleep for 1 second
                return "completed"
            
            # Should timeout
            result = await manager.call_with_timeout(slow_function)
            assert result is None  # Timeout returns None
    
    @pytest.mark.asyncio
    async def test_successful_call_within_timeout(self):
        """Test that fast calls complete successfully"""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-valid-test-key-1234567890',
            'LLM_TIMEOUT': '1000'  # 1 second timeout
        }):
            manager = LLMManager()
            
            # Create a fast function
            async def fast_function():
                await asyncio.sleep(0.01)  # Sleep for 10ms
                return "success"
            
            # Should complete
            result = await manager.call_with_timeout(fast_function)
            assert result == "success"
    
    @pytest.mark.asyncio
    async def test_fallback_mechanism(self):
        """Test automatic fallback from online to offline function"""
        manager = LLMManager()
        
        # Mock online function that fails
        async def online_func():
            raise Exception("API error")
        
        # Mock offline function that works
        def offline_func():
            return "offline_result"
        
        # Create wrapped function
        wrapped = manager.with_fallback(online_func, offline_func)
        
        # Should fallback to offline
        with patch.object(manager, 'get_mode', return_value='online'):
            result = await wrapped()
            assert result == "offline_result"
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff(self):
        """Test retry logic with exponential backoff"""
        manager = LLMManager()
        
        call_count = 0
        
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return "success"
        
        # Wrap with retry
        wrapped = manager.retry_with_backoff(flaky_function, max_retries=3)
        
        # Should succeed after retries
        result = await wrapped()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        """Test that retry gives up after max attempts"""
        manager = LLMManager()
        
        async def always_fails():
            raise Exception("Permanent error")
        
        # Wrap with retry
        wrapped = manager.retry_with_backoff(always_fails, max_retries=2)
        
        # Should raise after max retries
        with pytest.raises(Exception) as exc_info:
            await wrapped()
        assert "Permanent error" in str(exc_info.value)


class TestModeDetection:
    """Test mode detection logic"""
    
    def test_env_var_variations(self):
        """Test different environment variable configurations"""
        test_cases = [
            ('', 'offline'),  # Empty
            ('sk-your-api-key-here', 'offline'),  # Template value
            ('sk-abc123', 'offline'),  # Too short
            ('sk-' + 'a' * 30, 'online'),  # Valid format
            ('not-an-api-key', 'offline'),  # Wrong format
        ]
        
        for api_key, expected_mode in test_cases:
            with patch.dict(os.environ, {'OPENAI_API_KEY': api_key}):
                manager = LLMManager()
                assert manager.get_mode() == expected_mode, f"Failed for key: {api_key}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])