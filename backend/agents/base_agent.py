"""
Base Agent Class - Foundation for all agentic behavior
No pattern matching, pure LLM reasoning
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
import json
import logging
from openai import OpenAI
from pydantic import BaseModel, Field
import os
from enum import Enum
import asyncio
from utils.valkey_manager import valkey_manager
from utils.learning import LearningEngine, Pattern, AgentMemory, PatternType

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
        
        # Progress tracking
        self.progress_callback: Optional[Callable] = None
        self.current_step = 0
        self.total_steps = 0
        
        # Learning Engine integration
        self.learning_engine: Optional[LearningEngine] = None
        self._init_learning_engine()
        
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                # Try to initialize OpenAI client
                self.llm = OpenAI(api_key=api_key)
            except TypeError as e:
                # Handle version compatibility issues
                logger.warning(f"OpenAI client init error (trying fallback): {e}")
                try:
                    # Fallback: set env var and init without params
                    os.environ["OPENAI_API_KEY"] = api_key
                    self.llm = OpenAI()
                except Exception as e2:
                    logger.error(f"Failed to initialize OpenAI client: {e2}")
                    self.llm = None
        else:
            logger.warning(f"[{self.name}] No OpenAI API key configured - agent will have limited capabilities")
            self.llm = None
    
    def _init_learning_engine(self):
        """Initialize learning engine for advanced pattern recognition"""
        try:
            self.learning_engine = LearningEngine(valkey_manager)
            logger.info(f"[{self.name}] Learning engine initialized")
        except Exception as e:
            logger.warning(f"[{self.name}] Could not initialize learning engine: {e}")
            self.learning_engine = None
    
    def set_progress_callback(self, callback: Callable[[str, str, int], None]):
        """
        Set a callback for progress updates
        callback(agent_name, message, percentage)
        """
        self.progress_callback = callback
    
    async def emit_progress(self, step: str, message: str, percentage: Optional[int] = None):
        """
        Emit a progress update
        
        Args:
            step: Current step being performed
            message: User-friendly message about what's happening
            percentage: Optional progress percentage (0-100)
        """
        if self.progress_callback:
            try:
                # Calculate percentage if not provided
                if percentage is None and self.total_steps > 0:
                    percentage = int((self.current_step / self.total_steps) * 100)
                
                # Call the progress callback
                await self.progress_callback(self.name, step, message, percentage)
                
                logger.info(f"[{self.name}] Progress: {step} - {message} ({percentage}%)")
            except Exception as e:
                logger.error(f"Error emitting progress: {e}")
    
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
    
    async def reflect(self, action: Optional[Action], outcome: Any, domain_specific_data: Dict[str, Any] = None) -> Thought:
        """
        Enhanced reflection with domain awareness and learning engine integration.
        Updates memory with lessons learned and coordinates with learning engine.
        """
        # Base reflection using LLM
        reflection_prompt = f"""
        As {self.name} agent, reflect on this:
        
        Action taken: {json.dumps(action.model_dump()) if action else "No action"}
        Outcome: {json.dumps(outcome) if isinstance(outcome, dict) else str(outcome)}
        Domain context: {json.dumps(domain_specific_data) if domain_specific_data else "None"}
        
        Previous reasoning chain:
        {self._get_reasoning_chain()}
        
        Reflect on:
        1. Was the action successful?
        2. What worked well?
        3. What could be improved?
        4. What should be remembered?
        5. Any patterns observed?
        
        Provide reflection in JSON format:
        {{
            "reflection": "Your reflection",
            "success": true/false,
            "lessons": [],
            "patterns_observed": [],
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
        
        # Integrate with learning engine if available
        if self.learning_engine and reflection.get("patterns_observed"):
            session_history = self._get_session_history()
            outcome_str = "success" if reflection.get("success") else "failure"
            
            # Identify and save patterns
            patterns = await self.learning_engine.identify_success_patterns(
                session_history, 
                outcome_str
            )
            
            # Save high-confidence patterns
            for pattern in patterns:
                if pattern.confidence >= self.learning_engine.confidence_threshold:
                    await self.share_learning(pattern, pattern.confidence)
        
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
    
    async def share_learning(self, pattern: Pattern, confidence: float) -> None:
        """
        Share learned patterns with other agents through learning engine.
        Publishes patterns to shared learning store.
        """
        if not self.learning_engine:
            return
        
        try:
            # Save pattern to shared store
            await valkey_manager.save_learned_pattern(
                agent_name=self.name,
                pattern_type=pattern.type.value,
                pattern_data={
                    "description": pattern.description,
                    "occurrences": pattern.occurrences,
                    "metadata": pattern.metadata,
                    "source_agent": self.name,
                    "timestamp": datetime.now().isoformat()
                },
                confidence=confidence
            )
            
            logger.info(f"[{self.name}] Shared pattern: {pattern.description} (confidence: {confidence:.2f})")
        except Exception as e:
            logger.error(f"[{self.name}] Error sharing pattern: {e}")
    
    async def apply_learned_patterns(self, context: Dict[str, Any]) -> List[Pattern]:
        """
        Apply previously learned patterns to current context.
        Retrieves relevant patterns from learning engine.
        """
        if not self.learning_engine:
            return []
        
        try:
            # Get patterns for this agent
            patterns = await valkey_manager.get_learned_patterns(
                agent_name=self.name,
                pattern_type="all",
                min_confidence=self.learning_engine.pattern_min_confidence
            )
            
            # Filter patterns relevant to current context
            relevant_patterns = []
            for pattern_data in patterns:
                # Use LLM to determine relevance
                relevance_prompt = f"""
                Is this pattern relevant to the current context?
                Pattern: {json.dumps(pattern_data)}
                Context: {json.dumps(context)}
                
                Respond with JSON:
                {{"relevant": true/false, "confidence": 0.0-1.0}}
                """
                
                relevance = self._llm_reason(relevance_prompt)
                if relevance.get("relevant") and relevance.get("confidence", 0) > 0.6:
                    pattern = Pattern(
                        type=PatternType(pattern_data.get("type", "sequence")),
                        description=pattern_data.get("description", ""),
                        occurrences=pattern_data.get("occurrences", 1),
                        confidence=pattern_data.get("confidence", 0.5),
                        metadata=pattern_data.get("metadata", {})
                    )
                    relevant_patterns.append(pattern)
            
            return relevant_patterns
        except Exception as e:
            logger.error(f"[{self.name}] Error applying patterns: {e}")
            return []
    
    def get_agent_memory_snapshot(self) -> AgentMemory:
        """
        Get current agent memory snapshot for learning coordination.
        """
        return AgentMemory(
            agent_name=self.name,
            learned_patterns=self.memory.learned_patterns,
            corrections=self.memory.corrections,
            performance_metrics=self._calculate_performance_metrics(),
            last_reflection=datetime.now()
        )
    
    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """
        Calculate agent performance metrics for learning analysis.
        """
        successful_actions = sum(1 for a in self.action_history if a.confidence > 0.7)
        total_actions = len(self.action_history)
        
        return {
            "success_rate": successful_actions / total_actions if total_actions > 0 else 0,
            "total_actions": total_actions,
            "average_confidence": sum(a.confidence for a in self.action_history) / total_actions if total_actions > 0 else 0,
            "corrections_received": len(self.memory.corrections),
            "patterns_learned": len(self.memory.learned_patterns)
        }
    
    def _get_session_history(self) -> List[Dict[str, Any]]:
        """
        Get session history for pattern analysis.
        """
        history = []
        for action in self.action_history:
            history.append({
                "agent": self.name,
                "action": action.name,
                "parameters": action.parameters,
                "confidence": action.confidence,
                "timestamp": datetime.now().isoformat()
            })
        return history
    
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
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": f"You are {self.name}, an intelligent agent. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 1.0,
                "response_format": {"type": "json_object"}
            }
            logger.info(f"[OpenAI Request] {json.dumps(payload, default=str)[:4000]}")
            response = self.llm.chat.completions.create(**payload)
            
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
    
    async def process_with_session(self, input_data: Any, session_id: str) -> Tuple[Any, List[Thought]]:
        """
        Main processing loop with session awareness
        Loads memory, processes, and saves memory
        """
        # Load memory for this session
        await self.load_memory(session_id)
        
        # Process the input
        result = await self.process(input_data)
        
        # Save updated memory
        await self.save_memory(session_id)
        
        return result
    
    async def process(self, input_data: Any) -> Tuple[Any, List[Thought]]:
        """
        Main processing loop - implements ReAct pattern
        Observe -> Think -> Act -> Reflect
        """
        # Clear reasoning chain for new process
        self.reasoning_chain = []
        self.total_steps = 4  # Observe, Think, Act, Reflect
        self.current_step = 0
        
        # Observe
        self.current_step += 1
        await self.emit_progress("observing", "Analyzing input and understanding context", 25)
        observation = self.observe(input_data)
        
        # Think (iterate up to max depth)
        self.current_step += 1
        await self.emit_progress("thinking", "Processing information and planning next steps", 50)
        current_thought = observation
        for depth in range(self.max_reasoning_depth):
            reasoning = self.think(current_thought)
            
            # Act if ready
            action = self.act(reasoning)
            if action:
                self.current_step += 1
                await self.emit_progress("acting", f"Executing action: {action.name}", 75)
                
                # Execute action
                if action.requires_confirmation:
                    logger.info(f"[{self.name}] Action requires confirmation: {action.name}")
                    # In real implementation, would request confirmation
                
                outcome = self.execute_action(action)
                
                # Reflect on outcome
                self.current_step += 1
                await self.emit_progress("reflecting", "Evaluating results and learning", 90)
                reflection = await self.reflect(action, outcome)
                
                # Add to short-term memory
                self.memory.short_term.append({
                    "input": input_data,
                    "action": action.model_dump(),
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
    
    async def save_memory(self, session_id: str) -> None:
        """Save agent memory to persistent storage via Valkey"""
        try:
            # Save short-term memory
            if self.memory.short_term:
                await valkey_manager.save_agent_memory(
                    agent_name=self.name,
                    session_id=session_id,
                    memory_type="short_term",
                    data={"items": self.memory.short_term},
                    ttl=valkey_manager.short_term_ttl
                )
            
            # Save long-term memory
            if self.memory.long_term:
                await valkey_manager.save_agent_memory(
                    agent_name=self.name,
                    session_id=session_id,
                    memory_type="long_term",
                    data=self.memory.long_term,
                    ttl=valkey_manager.long_term_ttl
                )
            
            # Save corrections
            if self.memory.corrections:
                await valkey_manager.save_agent_memory(
                    agent_name=self.name,
                    session_id=session_id,
                    memory_type="corrections",
                    data={"corrections": self.memory.corrections},
                    ttl=valkey_manager.correction_ttl
                )
            
            # Save learned patterns with confidence
            if self.memory.learned_patterns:
                for idx, pattern in enumerate(self.memory.learned_patterns):
                    await valkey_manager.save_learned_pattern(
                        agent_name=self.name,
                        pattern_type="general",
                        pattern_data=pattern,
                        confidence=pattern.get('confidence', 0.8)
                    )
            
            # Save user preferences
            if self.memory.user_preferences:
                await valkey_manager.save_agent_memory(
                    agent_name=self.name,
                    session_id=session_id,
                    memory_type="user_preferences",
                    data=self.memory.user_preferences,
                    ttl=valkey_manager.long_term_ttl
                )
            
            logger.info(f"{self.name}: Memory saved to Valkey for session {session_id}")
            
        except Exception as e:
            logger.error(f"{self.name}: Failed to save memory: {e}")
    
    async def load_memory(self, session_id: str) -> None:
        """Load agent memory from persistent storage via Valkey"""
        try:
            # Load short-term memory
            short_term = await valkey_manager.load_agent_memory(
                agent_name=self.name,
                session_id=session_id,
                memory_type="short_term"
            )
            if short_term and "items" in short_term:
                self.memory.short_term = short_term["items"]
            
            # Load long-term memory
            long_term = await valkey_manager.load_agent_memory(
                agent_name=self.name,
                session_id=session_id,
                memory_type="long_term"
            )
            if long_term:
                self.memory.long_term = long_term
            
            # Load corrections
            corrections = await valkey_manager.load_agent_memory(
                agent_name=self.name,
                session_id=session_id,
                memory_type="corrections"
            )
            if corrections and "corrections" in corrections:
                self.memory.corrections = corrections["corrections"]
            
            # Load user preferences
            user_prefs = await valkey_manager.load_agent_memory(
                agent_name=self.name,
                session_id=session_id,
                memory_type="user_preferences"
            )
            if user_prefs:
                self.memory.user_preferences = user_prefs
            
            # Load learned patterns
            patterns = await valkey_manager.get_learned_patterns(
                agent_name=self.name,
                pattern_type="general",
                min_confidence=0.6
            )
            if patterns:
                self.memory.learned_patterns = patterns
            
            logger.info(f"{self.name}: Memory loaded from Valkey for session {session_id}")
            
        except Exception as e:
            logger.error(f"{self.name}: Failed to load memory: {e}")
