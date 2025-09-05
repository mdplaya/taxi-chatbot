"""
Simple Base Agent Class
Core functionality for all agents without complex patterns
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
import json
import logging
from openai import OpenAI
from pydantic import BaseModel, Field
import os

logger = logging.getLogger(__name__)


class Action(BaseModel):
    """Simple action representation"""
    name: str
    parameters: Dict[str, Any]
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool = False


class SimpleBaseAgent(ABC):
    """
    Simplified base class for all agents
    Direct LLM interaction without complex patterns
    """
    
    def __init__(self, name: str, goal: str, model: str = "gpt-5-mini"):
        self.name = name
        self.goal = goal
        self.model = model
        self.config = {}
        
        # Simple memory storage
        self.memory = {
            "short_term": {},
            "long_term": {},
            "session_data": {}
        }
        
        # Progress tracking
        self.progress_callback: Optional[Callable] = None
        
        # Learning engine (simplified)
        self.learning_engine = None
        
        # Setup default config
        self._setup_default_config()
        
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                self.llm = OpenAI(api_key=api_key)
                logger.info(f"[{self.name}] Initialized with model {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.llm = None
        else:
            logger.warning(f"[{self.name}] No OpenAI API key - limited capabilities")
            self.llm = None
    
    def _setup_default_config(self):
        """Setup default configuration"""
        self.config = {
            'temperature': 1.0,  # Required for gpt-5-mini
            'max_tokens': 2000,
            'timeout': 30
        }
    
    @abstractmethod
    async def prepare_context(self, input_data: Any) -> Dict[str, Any]:
        """
        Prepare context for processing
        Must be implemented by subclasses
        """
        pass
    
    @abstractmethod
    async def process(self, context: Any, session_id: str = None, progress_callback=None) -> Dict[str, Any]:
        """
        Main processing logic
        Must be implemented by subclasses
        """
        pass
    
    async def reason(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """
        Simple LLM reasoning call
        Returns parsed JSON response
        """
        if not self.llm:
            logger.error(f"[{self.name}] No LLM available for reasoning")
            return {}
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            else:
                messages.append({"role": "system", "content": f"You are {self.name}, an AI assistant. Goal: {self.goal}"})
            
            messages.append({"role": "user", "content": prompt})
            
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=1.0,  # Required for gpt-5-mini
                response_format={"type": "json_object"},
                max_tokens=self.config.get('max_tokens', 2000),
                timeout=self.config.get('timeout', 30)
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.debug(f"[{self.name}] Reasoning completed")
            return result
            
        except Exception as e:
            logger.error(f"[{self.name}] Reasoning failed: {e}")
            return {}
    
    async def execute_action(self, action: Action, session_id: str = None) -> Dict[str, Any]:
        """
        Execute an action
        Can be overridden by subclasses
        """
        logger.info(f"[{self.name}] Executing action: {action.name}")
        
        # Default implementation just returns the action
        return {
            "status": "executed",
            "action": action.name,
            "parameters": action.parameters,
            "reasoning": action.reasoning
        }
    
    async def validate_action(self, action: Action) -> Tuple[bool, str]:
        """
        Validate an action before execution
        Returns (is_valid, reason)
        """
        # Basic validation
        if not action.name:
            return False, "Action name is required"
        
        if action.confidence < 0.3:
            return False, f"Confidence too low: {action.confidence}"
        
        return True, "Valid"
    
    async def update_memory(self, key: str, value: Any, memory_type: str = "short_term"):
        """Update agent memory"""
        if memory_type in self.memory:
            self.memory[memory_type][key] = value
    
    async def get_memory(self, key: str, memory_type: str = "short_term") -> Any:
        """Retrieve from agent memory"""
        if memory_type in self.memory:
            return self.memory[memory_type].get(key)
        return None
    
    async def emit_progress(self, stage: str, message: str, percentage: int):
        """Emit progress update if callback is set"""
        if self.progress_callback:
            try:
                await self.progress_callback({
                    "stage": stage,
                    "message": message,
                    "percentage": percentage,
                    "agent": self.name,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to emit progress: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            "name": self.name,
            "goal": self.goal,
            "model": self.model,
            "llm_available": self.llm is not None,
            "memory_stats": {
                "short_term_items": len(self.memory["short_term"]),
                "long_term_items": len(self.memory["long_term"])
            }
        }


# For backward compatibility
BaseAgent = SimpleBaseAgent