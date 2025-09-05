"""
Simple LLM reasoning wrapper
Provides basic LLM interaction without complex patterns
"""

from typing import Dict, Any
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger(__name__)


class SimpleReasoning:
    """Basic LLM wrapper for simple reasoning tasks"""
    
    def __init__(self, model: str = "gpt-5-mini"):
        self.model = model
        
        # Initialize LLM
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = OpenAI(api_key=api_key)
        else:
            logger.warning("No OpenAI API key - reasoning will have limited capabilities")
            self.llm = None
    
    async def reason(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """
        Simple LLM reasoning call
        Returns parsed JSON response or empty dict on error
        """
        if not self.llm:
            logger.warning("No LLM available for reasoning")
            return {}
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            else:
                messages.append({"role": "system", "content": "You are an intelligent assistant. Always respond with valid JSON."})
            
            messages.append({"role": "user", "content": prompt})
            
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=1.0,  # Required for gpt-5-mini
                response_format={"type": "json_object"},
                timeout=30.0
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
            return {}
    
    def format_prompt(self, template: str, **kwargs) -> str:
        """Simple prompt formatting"""
        return template.format(**kwargs)


# Global instance for backward compatibility
_reasoning_engine = None

def get_reasoning_engine(model: str = "gpt-5-mini") -> SimpleReasoning:
    """Get or create reasoning engine instance"""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = SimpleReasoning(model)
    return _reasoning_engine