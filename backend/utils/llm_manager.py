"""
Simple LLM Manager
Basic LLM configuration and availability checking
"""

import os
import time
import logging
from typing import Literal, Dict, Any

logger = logging.getLogger(__name__)


class SimpleLLMManager:
    """Manages LLM configuration and availability."""
    
    def __init__(self):
        """Initialize the LLM Manager."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Model configuration for gpt-5-mini
        self.model = os.getenv("AGENT_REASONING_MODEL", "gpt-5-mini")
        self.temperature = 1.0  # gpt-5-mini only supports 1.0
        
        # Check mode
        self._mode = self._check_mode()
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not configured. Running in offline mode.")
        else:
            logger.info(f"LLM Manager initialized with model: {self.model}")
    
    def _check_mode(self) -> Literal["online", "offline"]:
        """Check LLM availability."""
        if not self.api_key:
            return "offline"
        
        # Check API key format
        if self.api_key.startswith("sk-") and len(self.api_key) > 20:
            return "online"
        
        return "offline"
    
    def get_mode(self) -> Literal["online", "offline"]:
        """
        Get current operation mode.
        
        Returns:
            "online" if LLM is available, "offline" otherwise
        """
        return self._mode
    
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
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self.get_mode() == "online"


# Global instance
_llm_manager = None

def get_llm_manager() -> SimpleLLMManager:
    """Get or create LLM manager instance"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = SimpleLLMManager()
    return _llm_manager

# For backward compatibility
llm_manager = get_llm_manager()


# Debug flag functions for compatibility
def set_llm_debug(enabled: bool) -> None:
    """Set debug mode (kept for compatibility)"""
    pass

def is_llm_debug_enabled() -> bool:
    """Check if debug mode is enabled"""
    return os.getenv("LLM_DEBUG", "").lower() == "true"