"""
LLM Manager Module
Handles online/offline mode detection and LLM integration with fallback support.
"""
import os
import time
import asyncio
from typing import Optional, Literal, Any, Callable, Dict
import contextvars
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class LLMManager:
    """Manages LLM availability and provides fallback mechanisms."""
    
    def __init__(self):
        """Initialize the LLM Manager."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Model configuration for gpt-5-mini
        self.model = os.getenv("AGENT_REASONING_MODEL", "gpt-5-mini")
        self.temperature = float(os.getenv("REASONING_TEMPERATURE", "1.0"))  # gpt-5-mini only supports 1.0
        
        # Validate model constraints
        if self.model == "gpt-5-mini" and self.temperature != 1.0:
            logger.warning(f"Model {self.model} only supports temperature=1.0, adjusting from {self.temperature}")
            self.temperature = 1.0
        
        # Production timeout: 75 seconds to handle complex LLM operations
        self.timeout = int(os.getenv("LLM_TIMEOUT", "75000")) / 1000  # Convert to seconds (default: 75s)
        self.cache_ttl = int(os.getenv("LLM_CACHE_TTL", "300"))  # 5 minutes default
        self._mode_cache = {"mode": None, "timestamp": 0}
        self._check_initial_mode()
    
    def _check_initial_mode(self):
        """Check initial LLM availability on startup."""
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not configured. Running in offline mode.")
            self._mode_cache = {"mode": "offline", "timestamp": time.time()}
        else:
            # Try a simple API check
            try:
                import openai
                openai.api_key = self.api_key
                # Just verify the key format is valid
                if self.api_key.startswith("sk-") and len(self.api_key) > 20:
                    self._mode_cache = {"mode": "online", "timestamp": time.time()}
                    logger.info("LLM Manager initialized in online mode")
                else:
                    self._mode_cache = {"mode": "offline", "timestamp": time.time()}
                    logger.warning("Invalid API key format. Running in offline mode.")
            except Exception as e:
                logger.error(f"Error checking LLM availability: {e}")
                self._mode_cache = {"mode": "offline", "timestamp": time.time()}
    
    def get_mode(self) -> Literal["online", "offline"]:
        """
        Get current operation mode with 5-minute cache.
        
        Returns:
            "online" if LLM is available, "offline" otherwise
        """
        current_time = time.time()
        
        # Check if cache is still valid
        if (self._mode_cache["mode"] and 
            current_time - self._mode_cache["timestamp"] < self.cache_ttl):
            return self._mode_cache["mode"]
        
        # Re-check mode
        self._check_initial_mode()
        return self._mode_cache["mode"]
    
    async def call_with_timeout(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        """
        Call a function with timeout and fallback handling.
        
        Args:
            func: The function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Function result or None if timeout/error
        """
        try:
            # Create a task with timeout
            result = await asyncio.wait_for(
                asyncio.create_task(self._async_wrapper(func, *args, **kwargs)),
                timeout=self.timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"LLM call timed out after {self.timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Error in LLM call: {e}")
            return None
    
    async def _async_wrapper(self, func: Callable, *args, **kwargs):
        """Wrap synchronous functions for async execution."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # Run in executor for blocking calls
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)
    
    def with_fallback(self, online_func: Callable, offline_func: Callable):
        """
        Decorator to provide automatic fallback between online and offline functions.
        
        Args:
            online_func: Function to use when LLM is available
            offline_func: Function to use as fallback
            
        Returns:
            Wrapped function that automatically selects the appropriate implementation
        """
        @wraps(online_func)
        async def wrapper(*args, **kwargs):
            mode = self.get_mode()
            
            if mode == "online":
                result = await self.call_with_timeout(online_func, *args, **kwargs)
                if result is not None:
                    return result
                else:
                    # Fallback to offline if online fails
                    logger.info("Online function failed, falling back to offline mode")
                    return await self._async_wrapper(offline_func, *args, **kwargs)
            else:
                return await self._async_wrapper(offline_func, *args, **kwargs)
        
        return wrapper
    
    def retry_with_backoff(self, func: Callable, max_retries: int = 3):
        """
        Retry a function with exponential backoff.
        
        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts
            
        Returns:
            Decorated function with retry logic
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    result = await self._async_wrapper(func, *args, **kwargs)
                    if result is not None:
                        return result
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed after {max_retries} attempts: {e}")
                        raise
                    
                    # Exponential backoff: 1s, 2s, 4s...
                    wait_time = 2 ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
            
            return None
        
        return wrapper
    
    def get_model_config(self) -> Dict[str, Any]:
        """
        Get current model configuration
        
        Returns:
            Dictionary with model name and temperature
        """
        return {
            "model": self.model,
            "temperature": self.temperature,
            "mode": self.get_mode()
        }


# Global instance
llm_manager = LLMManager()

# Context-scoped debug flag used to control OpenAI payload logging
_LLM_DEBUG: contextvars.ContextVar[bool] = contextvars.ContextVar("LLM_DEBUG", default=False)

def set_llm_debug(enabled: bool) -> None:
    _LLM_DEBUG.set(bool(enabled))

def is_llm_debug_enabled() -> bool:
    try:
        return bool(_LLM_DEBUG.get())
    except Exception:
        return False
