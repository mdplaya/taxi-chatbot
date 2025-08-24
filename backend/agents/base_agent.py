"""
Base Agent Class - Foundation for all agentic behavior
No pattern matching, pure LLM reasoning
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import logging
from openai import OpenAI
from pydantic import BaseModel, Field
import os
from enum import Enum

logger = logging.getLogger(__name__)


class ThoughtType(str, Enum):
    OBSERVATION = "observation"
    REASONING = "reasoning"
    ACTION = "action"
    REFLECTION = "reflection"
    LEARNING = "learning"


class Thought(BaseModel):
    type: ThoughtType
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    name: str
    parameters: Dict[str, Any]
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool = False


class Memory(BaseModel):
    short_term: List[Dict[str, Any]] = Field(default_factory=list)
    long_term: Dict[str, Any] = Field(default_factory=dict)
    corrections: List[Dict[str, Any]] = Field(default_factory=list)
    learned_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all agents - implements ReAct pattern
    All decisions made through LLM reasoning, no hardcoded rules
    """
    
    def __init__(self, name: str, goal: str, model: str = "gpt-5-mini"):
        self.name = name
        self.goal = goal
        self.model = model
        self.memory = Memory()
        self.reasoning_chain: List[Thought] = []
        self.action_history: List[Action] = []
        self.max_reasoning_depth = int(os.getenv("MAX_REASONING_DEPTH", "5"))
        self.confidence_threshold = float(os.getenv("DECISION_CONFIDENCE_THRESHOLD", "0.6"))
        
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = OpenAI(api_key=api_key)
        else:
            logger.warning(f"[{self.name}] No OpenAI API key configured - agent will have limited capabilities")
            self.llm = None
    
    def observe(self, input_data: Any) -> Thought:
        """
        Observe and understand the input using LLM
        NO pattern matching - pure reasoning
        """
        observation_prompt = f"""
        As {self.name} agent with goal: {self.goal}
        
        Observe and understand this input:
        {json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)}
        
        Previous context:
        {self._get_relevant_memory()}
        
        Provide your observation in JSON format:
        {{
            "observation": "What you observe",
            "relevant_context": "Any relevant context from memory",
            "confidence": 0.0-1.0,
            "key_points": []
        }}
        """
        
        observation = self._llm_reason(observation_prompt)
        thought = Thought(
            type=ThoughtType.OBSERVATION,
            content=observation.get("observation", ""),
            confidence=observation.get("confidence", 0.5),
            metadata=observation
        )
        
        self.reasoning_chain.append(thought)
        return thought
    
    def think(self, observation: Thought) -> Thought:
        """
        Think about what to do based on observation
        Pure LLM reasoning - no if/then rules
        """
        thinking_prompt = f"""
        As {self.name} agent with goal: {self.goal}
        
        Based on this observation:
        {observation.content}
        
        And this context:
        {json.dumps(observation.metadata)}
        
        Think about:
        1. What needs to be done
        2. What actions are available
        3. What information might be missing
        4. What could go wrong
        
        Previous reasoning:
        {self._get_reasoning_chain()}
        
        Provide your reasoning in JSON format:
        {{
            "reasoning": "Your chain of thought",
            "possible_actions": [],
            "missing_information": [],
            "risks": [],
            "confidence": 0.0-1.0
        }}
        """
        
        reasoning = self._llm_reason(thinking_prompt)
        thought = Thought(
            type=ThoughtType.REASONING,
            content=reasoning.get("reasoning", ""),
            confidence=reasoning.get("confidence", 0.5),
            metadata=reasoning
        )
        
        self.reasoning_chain.append(thought)
        return thought
    
    def act(self, reasoning: Thought) -> Optional[Action]:
        """
        Decide on and execute action based on reasoning
        All actions determined by LLM, no hardcoded logic
        """
        action_prompt = f"""
        As {self.name} agent with goal: {self.goal}
        
        Based on this reasoning:
        {reasoning.content}
        {json.dumps(reasoning.metadata)}
        
        Available tools/actions:
        {json.dumps(self.get_available_tools())}
        
        Decide on the best action in JSON format:
        {{
            "action": "action_name",
            "parameters": {{}},
            "reasoning": "Why this action",
            "confidence": 0.0-1.0,
            "requires_confirmation": true/false
        }}
        
        Return null if no action needed yet.
        """
        
        action_decision = self._llm_reason(action_prompt)
        
        if not action_decision or action_decision.get("action") == "none":
            return None
        
        action = Action(
            name=action_decision.get("action", ""),
            parameters=action_decision.get("parameters", {}),
            reasoning=action_decision.get("reasoning", ""),
            confidence=action_decision.get("confidence", 0.5),
            requires_confirmation=action_decision.get("requires_confirmation", False)
        )
        
        # Only execute if confidence meets threshold
        if action.confidence >= self.confidence_threshold:
            self.action_history.append(action)
            return action
        else:
            logger.info(f"[{self.name}] Action confidence {action.confidence} below threshold {self.confidence_threshold}")
            return None
    
    def reflect(self, action: Optional[Action], outcome: Any) -> Thought:
        """
        Reflect on action outcome and learn
        Updates memory with lessons learned
        """
        reflection_prompt = f"""
        As {self.name} agent, reflect on this:
        
        Action taken: {json.dumps(action.dict()) if action else "No action"}
        Outcome: {json.dumps(outcome) if isinstance(outcome, dict) else str(outcome)}
        
        Previous reasoning chain:
        {self._get_reasoning_chain()}
        
        Reflect on:
        1. Was the action successful?
        2. What worked well?
        3. What could be improved?
        4. What should be remembered?
        
        Provide reflection in JSON format:
        {{
            "reflection": "Your reflection",
            "success": true/false,
            "lessons": [],
            "memory_updates": {{}},
            "confidence_adjustment": -0.1 to 0.1
        }}
        """
        
        reflection = self._llm_reason(reflection_prompt)
        
        # Update memory with lessons
        if reflection.get("lessons"):
            self.memory.learned_patterns.extend([
                {"lesson": l, "timestamp": datetime.now().isoformat()}
                for l in reflection.get("lessons", [])
            ])
        
        # Update long-term memory
        if reflection.get("memory_updates"):
            self.memory.long_term.update(reflection["memory_updates"])
        
        thought = Thought(
            type=ThoughtType.REFLECTION,
            content=reflection.get("reflection", ""),
            confidence=min(1.0, max(0.0, self.confidence_threshold + reflection.get("confidence_adjustment", 0))),
            metadata=reflection
        )
        
        self.reasoning_chain.append(thought)
        return thought
    
    def learn_from_correction(self, original: Any, correction: Any, context: str) -> None:
        """
        Learn from user corrections
        Stores in memory for future use
        """
        learning_prompt = f"""
        Learn from this correction:
        
        Original: {json.dumps(original) if isinstance(original, dict) else str(original)}
        Correction: {json.dumps(correction) if isinstance(correction, dict) else str(correction)}
        Context: {context}
        
        Extract the pattern and lesson in JSON format:
        {{
            "pattern": "What pattern to recognize",
            "correction_rule": "How to correct it",
            "context_clues": [],
            "confidence": 0.0-1.0
        }}
        """
        
        learning = self._llm_reason(learning_prompt)
        
        self.memory.corrections.append({
            "original": original,
            "correction": correction,
            "pattern": learning.get("pattern"),
            "rule": learning.get("correction_rule"),
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "confidence": learning.get("confidence", 0.5)
        })
        
        thought = Thought(
            type=ThoughtType.LEARNING,
            content=f"Learned: {learning.get('pattern', 'New correction pattern')}",
            confidence=learning.get("confidence", 0.5),
            metadata=learning
        )
        
        self.reasoning_chain.append(thought)
    
    def _llm_reason(self, prompt: str) -> Dict[str, Any]:
        """
        Core LLM reasoning - all decisions go through here
        NO hardcoded logic allowed
        """
        if not self.llm:
            # Fallback for testing without API key
            logger.warning(f"[{self.name}] No LLM available, returning empty reasoning")
            return {}
        
        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"You are {self.name}, an intelligent agent. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=float(os.getenv("REASONING_TEMPERATURE", "0.7")),
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"[{self.name}] LLM reasoning failed: {e}")
            return {}
    
    def _get_relevant_memory(self) -> str:
        """Get relevant context from memory"""
        relevant = {
            "recent_observations": self.memory.short_term[-3:] if self.memory.short_term else [],
            "learned_patterns": self.memory.learned_patterns[-5:] if self.memory.learned_patterns else [],
            "user_preferences": self.memory.user_preferences
        }
        return json.dumps(relevant, default=str)
    
    def _get_reasoning_chain(self) -> str:
        """Get recent reasoning chain for context"""
        recent_thoughts = [
            {
                "type": t.type.value,
                "content": t.content[:200],  # Truncate for context
                "confidence": t.confidence
            }
            for t in self.reasoning_chain[-5:]
        ]
        return json.dumps(recent_thoughts, default=str)
    
    @abstractmethod
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Define available tools/actions for this agent
        Must be implemented by each specific agent
        """
        pass
    
    @abstractmethod
    def execute_action(self, action: Action) -> Any:
        """
        Execute the chosen action
        Must be implemented by each specific agent
        """
        pass
    
    def process(self, input_data: Any) -> Tuple[Any, List[Thought]]:
        """
        Main processing loop - implements ReAct pattern
        Observe -> Think -> Act -> Reflect
        """
        # Clear reasoning chain for new process
        self.reasoning_chain = []
        
        # Observe
        observation = self.observe(input_data)
        
        # Think (iterate up to max depth)
        current_thought = observation
        for depth in range(self.max_reasoning_depth):
            reasoning = self.think(current_thought)
            
            # Act if ready
            action = self.act(reasoning)
            if action:
                # Execute action
                if action.requires_confirmation:
                    logger.info(f"[{self.name}] Action requires confirmation: {action.name}")
                    # In real implementation, would request confirmation
                
                outcome = self.execute_action(action)
                
                # Reflect on outcome
                reflection = self.reflect(action, outcome)
                
                # Add to short-term memory
                self.memory.short_term.append({
                    "input": input_data,
                    "action": action.dict(),
                    "outcome": outcome,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Keep memory size manageable
                if len(self.memory.short_term) > 100:
                    self.memory.short_term = self.memory.short_term[-50:]
                
                return outcome, self.reasoning_chain
            
            current_thought = reasoning
        
        # No action taken after max depth
        logger.warning(f"[{self.name}] Reached max reasoning depth without action")
        return None, self.reasoning_chain
    
    def save_memory(self, session_id: str) -> None:
        """Save agent memory to persistent storage"""
        # This will be implemented with Valkey integration
        pass
    
    def load_memory(self, session_id: str) -> None:
        """Load agent memory from persistent storage"""
        # This will be implemented with Valkey integration
        pass