"""
ReAct Pattern Implementation
Reasoning and Action framework for agents
"""

from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from enum import Enum
import asyncio
from openai import OpenAI
import os

logger = logging.getLogger(__name__)


class ReasoningState(str, Enum):
    OBSERVING = "observing"
    THINKING = "thinking"
    ACTING = "acting"
    REFLECTING = "reflecting"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ReasoningStep:
    state: ReasoningState
    content: str
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class ReasoningContext:
    goal: str
    constraints: List[str]
    available_actions: List[str]
    history: List[ReasoningStep]
    memory: Dict[str, Any]
    max_iterations: int = 5
    current_iteration: int = 0
    simple_request: bool = False  # Flag for simple requests to reduce iterations


class ReasoningEngine:
    """
    Implements the ReAct (Reasoning and Acting) pattern
    All decisions through LLM reasoning - no hardcoded rules
    """
    
    def __init__(self, model: str = "gpt-5-mini"):
        self.model = model
        self.reasoning_chains: Dict[str, List[ReasoningStep]] = {}
        self.safety_checks: List[Callable] = []
        
        # Initialize LLM
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = OpenAI(api_key=api_key)
        else:
            logger.warning("No OpenAI API key - reasoning engine will have limited capabilities")
            self.llm = None
    
    async def reason(self, context: ReasoningContext, input_data: Any) -> Tuple[Any, List[ReasoningStep]]:
        """
        Execute reasoning loop
        Returns result and reasoning chain
        """
        chain_id = f"{context.goal}_{datetime.now().timestamp()}"
        self.reasoning_chains[chain_id] = []
        
        # Reduce iterations for simple requests
        if context.simple_request:
            context.max_iterations = min(2, context.max_iterations)
        
        # Add timeout protection
        import asyncio
        max_time = 5.0 if context.simple_request else 10.0  # 5s for simple, 10s for complex
        start_time = asyncio.get_event_loop().time()
        
        while context.current_iteration < context.max_iterations:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > max_time:
                logger.warning(f"Reasoning engine timeout after {max_time}s for goal: {context.goal}")
                break
            context.current_iteration += 1
            
            # Observe
            logger.info(f"[ReAct] Starting observation phase, iteration {context.current_iteration}")
            observation = await self._observe(context, input_data)
            self.reasoning_chains[chain_id].append(observation)
            logger.info(f"[ReAct] Observation complete: {observation.confidence}")
            
            if observation.state == ReasoningState.FAILED:
                break
            
            # Think
            logger.info(f"[ReAct] Starting thinking phase")
            thought = await self._think(context, observation)
            self.reasoning_chains[chain_id].append(thought)
            logger.info(f"[ReAct] Thinking complete: proposed action = {thought.metadata.get('proposed_action')}")
            
            # Decide if action needed
            if self._should_act(thought):
                # Act
                action_result = await self._act(context, thought)
                self.reasoning_chains[chain_id].append(action_result)
                
                # Reflect
                reflection = await self._reflect(context, action_result)
                self.reasoning_chains[chain_id].append(reflection)
                
                # Check if complete
                if reflection.state == ReasoningState.COMPLETE:
                    return reflection.metadata.get("result"), self.reasoning_chains[chain_id]
                
                # Update input for next iteration
                input_data = reflection.metadata.get("next_input", input_data)
            
            # Check if stuck
            if self._is_stuck(self.reasoning_chains[chain_id]):
                break
        
        # Max iterations reached
        logger.warning(f"Reasoning engine reached max iterations for goal: {context.goal}")
        return None, self.reasoning_chains[chain_id]
    
    async def _observe(self, context: ReasoningContext, input_data: Any) -> ReasoningStep:
        """
        Observation phase - understand the input
        """
        prompt = f"""
        Goal: {context.goal}
        
        Observe and analyze this input:
        {json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)}
        
        Previous observations:
        {self._format_history(context.history, ReasoningState.OBSERVING)}
        
        Provide observation in JSON:
        {{
            "observation": "What you observe",
            "key_facts": [],
            "uncertainties": [],
            "relevant_context": {{}},
            "confidence": 0.0-1.0
        }}
        """
        
        result = await self._llm_reason(prompt)
        
        return ReasoningStep(
            state=ReasoningState.OBSERVING,
            content=result.get("observation", ""),
            confidence=result.get("confidence", 0.5),
            timestamp=datetime.now(),
            metadata=result
        )
    
    async def _think(self, context: ReasoningContext, observation: ReasoningStep) -> ReasoningStep:
        """
        Thinking phase - reason about what to do
        """
        prompt = f"""
        Goal: {context.goal}
        Constraints: {json.dumps(context.constraints)}
        
        Based on observation:
        {observation.content}
        {json.dumps(observation.metadata)}
        
        Available actions:
        {json.dumps(context.available_actions)}
        
        Think step by step:
        1. What is the current situation?
        2. What needs to be achieved?
        3. What are the options?
        4. What is the best approach?
        
        Provide reasoning in JSON:
        {{
            "reasoning": "Your step-by-step thinking",
            "proposed_action": "action_name or null",
            "action_parameters": {{}},
            "alternatives": [],
            "risks": [],
            "confidence": 0.0-1.0
        }}
        """
        
        result = await self._llm_reason(prompt)
        
        # Safety check
        if not await self._safety_check(result):
            result["proposed_action"] = None
            result["reasoning"] += " [BLOCKED BY SAFETY CHECK]"
        
        return ReasoningStep(
            state=ReasoningState.THINKING,
            content=result.get("reasoning", ""),
            confidence=result.get("confidence", 0.5),
            timestamp=datetime.now(),
            metadata=result
        )
    
    async def _act(self, context: ReasoningContext, thought: ReasoningStep) -> ReasoningStep:
        """
        Acting phase - execute the chosen action
        """
        action = thought.metadata.get("proposed_action")
        parameters = thought.metadata.get("action_parameters", {})
        
        if not action:
            return ReasoningStep(
                state=ReasoningState.ACTING,
                content="No action taken",
                confidence=1.0,
                timestamp=datetime.now(),
                metadata={"action": None, "result": None}
            )
        
        # Validate action
        validation_prompt = f"""
        Validate this action before execution:
        Action: {action}
        Parameters: {json.dumps(parameters)}
        Goal: {context.goal}
        
        Check:
        1. Is this action safe?
        2. Will it help achieve the goal?
        3. Are parameters valid?
        
        Respond in JSON:
        {{
            "is_valid": true/false,
            "validation_result": "explanation",
            "adjusted_parameters": {{}}
        }}
        """
        
        validation = await self._llm_reason(validation_prompt)
        
        if not validation.get("is_valid", False):
            return ReasoningStep(
                state=ReasoningState.ACTING,
                content=f"Action blocked: {validation.get('validation_result')}",
                confidence=0.0,
                timestamp=datetime.now(),
                metadata={"action": action, "blocked": True, "reason": validation}
            )
        
        # Use adjusted parameters if provided
        final_parameters = validation.get("adjusted_parameters") or parameters
        
        return ReasoningStep(
            state=ReasoningState.ACTING,
            content=f"Executing: {action}",
            confidence=thought.confidence,
            timestamp=datetime.now(),
            metadata={
                "action": action,
                "parameters": final_parameters,
                "validation": validation
            }
        )
    
    async def _reflect(self, context: ReasoningContext, action_result: ReasoningStep) -> ReasoningStep:
        """
        Reflection phase - learn from the action
        """
        prompt = f"""
        Reflect on this action and its outcome:
        
        Goal: {context.goal}
        Action taken: {json.dumps(action_result.metadata)}
        
        Full reasoning chain:
        {self._format_full_chain(context.history + [action_result])}
        
        Reflect on:
        1. Did the action help achieve the goal?
        2. What was learned?
        3. Is the goal complete?
        4. What should happen next?
        
        Provide reflection in JSON:
        {{
            "reflection": "Your reflection",
            "goal_complete": true/false,
            "progress_made": true/false,
            "lessons_learned": [],
            "next_step": "description or null",
            "result": "final result if complete, else null",
            "confidence": 0.0-1.0
        }}
        """
        
        result = await self._llm_reason(prompt)
        
        state = ReasoningState.COMPLETE if result.get("goal_complete") else ReasoningState.REFLECTING
        
        return ReasoningStep(
            state=state,
            content=result.get("reflection", ""),
            confidence=result.get("confidence", 0.5),
            timestamp=datetime.now(),
            metadata=result
        )
    
    def _should_act(self, thought: ReasoningStep) -> bool:
        """
        Determine if an action should be taken
        Based on LLM reasoning, not rules
        """
        return thought.metadata.get("proposed_action") is not None
    
    def _is_stuck(self, chain: List[ReasoningStep]) -> bool:
        """
        Detect if reasoning is stuck in a loop
        """
        if len(chain) < 6:
            return False
        
        # Check for repeating patterns
        recent_contents = [step.content for step in chain[-6:]]
        if len(set(recent_contents)) < 3:
            logger.warning("Reasoning appears stuck - repeating patterns detected")
            return True
        
        # Check for declining confidence
        recent_confidences = [step.confidence for step in chain[-4:]]
        if all(c < 0.3 for c in recent_confidences):
            logger.warning("Reasoning confidence too low")
            return True
        
        return False
    
    async def _llm_reason(self, prompt: str) -> Dict[str, Any]:
        """
        Core LLM reasoning call
        """
        if not self.llm:
            logger.warning("No LLM available for reasoning")
            return {}
        
        try:
            import time
            start = time.time()
            logger.debug(f"[LLM] Starting API call with prompt length: {len(prompt)}")
            
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an intelligent reasoning engine. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1.0,  # gpt-5-mini only supports temperature=1.0
                response_format={"type": "json_object"},
                timeout=3.0  # Add 3 second timeout per API call
            )
            
            elapsed = time.time() - start
            logger.info(f"[LLM] API call completed in {elapsed:.2f}s")
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
            return {}
    
    async def _safety_check(self, reasoning_result: Dict[str, Any]) -> bool:
        """
        Run safety checks on proposed actions
        """
        for check in self.safety_checks:
            if not await check(reasoning_result):
                logger.warning(f"Safety check failed for action: {reasoning_result.get('proposed_action')}")
                return False
        return True
    
    def _format_history(self, history: List[ReasoningStep], state_filter: Optional[ReasoningState] = None) -> str:
        """
        Format reasoning history for context
        """
        filtered = [h for h in history if not state_filter or h.state == state_filter]
        return json.dumps([
            {
                "state": step.state.value,
                "content": step.content[:200],
                "confidence": step.confidence
            }
            for step in filtered[-3:]
        ], default=str)
    
    def _format_full_chain(self, chain: List[ReasoningStep]) -> str:
        """
        Format full reasoning chain
        """
        return json.dumps([
            {
                "step": i + 1,
                "state": step.state.value,
                "content": step.content,
                "confidence": step.confidence
            }
            for i, step in enumerate(chain)
        ], default=str)
    
    def add_safety_check(self, check: Callable) -> None:
        """
        Add a safety check function
        """
        self.safety_checks.append(check)
    
    def get_reasoning_chain(self, chain_id: str) -> List[ReasoningStep]:
        """
        Get a specific reasoning chain
        """
        return self.reasoning_chains.get(chain_id, [])