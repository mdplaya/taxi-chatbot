"""
Orchestrator Agent - Routes requests using pure LLM reasoning
NO pattern matching, NO hardcoded rules
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, Action
from utils.reasoning import ReasoningEngine, ReasoningContext
from utils.error_correction import ErrorCorrectionSystem

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Routes requests to appropriate specialist agents
    All routing decisions made through LLM reasoning
    Maintains conversation context and user preferences
    """
    
    def __init__(self, mcp_client=None):
        super().__init__(
            name="Orchestrator",
            goal="Understand user intent and route to appropriate specialist agents",
            model=os.getenv("AGENT_REASONING_MODEL", "gpt-4")
        )
        
        self.mcp = mcp_client
        self.reasoning_engine = ReasoningEngine(self.model)
        self.error_correction = ErrorCorrectionSystem(self.model)
        
        # Agent capabilities for routing
        self.available_agents = {
            "compute": "Handles VM/instance creation and configuration",
            "database": "Manages database provisioning and setup",
            "clarification": "Gathers missing information through natural conversation",
            "gce_specialist": "GCP-specific compute provisioning",
            "azure_specialist": "Azure-specific provisioning",
            "aws_specialist": "AWS-specific provisioning"
        }
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Define orchestrator's available actions"""
        return [
            {
                "name": "route_to_agent",
                "description": "Route request to a specialist agent",
                "parameters": ["agent_name", "context"]
            },
            {
                "name": "request_clarification",
                "description": "Request clarification from user",
                "parameters": ["question", "context"]
            },
            {
                "name": "analyze_intent",
                "description": "Deeply analyze user intent",
                "parameters": ["user_input", "conversation_history"]
            },
            {
                "name": "check_conversation_state",
                "description": "Check current conversation state and context",
                "parameters": ["session_id"]
            }
        ]
    
    async def process(self, user_input: str, session_id: str = None) -> Dict[str, Any]:
        """
        Process user request using pure LLM reasoning
        NO pattern matching allowed
        """
        logger.info(f"[Orchestrator] Processing: {user_input}")
        
        # Store in memory
        self.memory.short_term.append({
            "type": "user_input",
            "content": user_input,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
        # First, apply error correction if needed
        correction_result = await self.error_correction.detect_and_correct(
            user_input,
            {"session_id": session_id, "agent": "orchestrator"}
        )
        
        if correction_result.confidence > 0.7 and correction_result.corrected != user_input:
            logger.info(f"[Orchestrator] Applied correction: {correction_result.corrected}")
            if correction_result.requires_confirmation:
                # In production, would request user confirmation
                logger.info(f"[Orchestrator] Correction requires confirmation: {correction_result.reasoning}")
        
        # Use corrected input for processing
        processed_input = correction_result.corrected
        
        # Create reasoning context
        context = ReasoningContext(
            goal="Understand user intent and route to appropriate agent",
            constraints=[
                "Must identify the type of resource requested",
                "Must detect cloud provider if mentioned",
                "Must preserve all user requirements",
                "Must handle ambiguous requests gracefully"
            ],
            available_actions=list(self.available_agents.keys()) + ["request_clarification"],
            history=[],
            memory=self._get_session_memory(session_id)
        )
        
        # Use reasoning engine to determine routing
        routing_decision, reasoning_chain = await self.reasoning_engine.reason(
            context,
            {
                "user_input": processed_input,
                "original_input": user_input if user_input != processed_input else None,
                "session_id": session_id,
                "conversation_history": self._get_conversation_history(session_id)
            }
        )
        
        # If reasoning failed, use LLM directly
        if not routing_decision:
            routing_decision = await self._direct_reasoning(processed_input, session_id)
        
        # Store reasoning chain for audit
        self.memory.long_term[f"routing_{session_id}_{datetime.now().timestamp()}"] = {
            "input": user_input,
            "decision": routing_decision,
            "reasoning": [{"state": s.state.value, "content": s.content} for s in reasoning_chain]
        }
        
        return routing_decision
    
    async def _direct_reasoning(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """
        Direct LLM reasoning for routing decision
        Fallback when reasoning engine doesn't produce result
        """
        routing_prompt = f"""
        As an intelligent orchestrator, analyze this request and decide routing:
        
        User input: {user_input}
        Session ID: {session_id}
        Conversation history: {json.dumps(self._get_conversation_history(session_id))}
        
        Available agents:
        {json.dumps(self.available_agents)}
        
        Analyze:
        1. What is the user trying to accomplish?
        2. What type of resource do they want?
        3. Which cloud provider (if any) are they targeting?
        4. What information is present vs missing?
        5. Which agent is best suited to handle this?
        
        Respond in JSON:
        {{
            "intent": "description of user intent",
            "resource_type": "vm|database|network|storage|other",
            "provider": "gcp|aws|azure|onprem|unclear",
            "confidence": 0.0-1.0,
            "next_agent": "agent_name",
            "missing_info": [],
            "extracted_requirements": {{}},
            "reasoning": "explanation of routing decision"
        }}
        """
        
        result = self._llm_reason(routing_prompt)
        
        # Build routing response
        next_agent = result.get("next_agent", "clarification")
        
        # Learn from this routing for future
        self.memory.learned_patterns.append({
            "input_pattern": user_input[:100],
            "intent": result.get("intent"),
            "routed_to": next_agent,
            "confidence": result.get("confidence", 0.5),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "next_agent": next_agent,
            "context": {
                "intent": result.get("intent"),
                "resource_type": result.get("resource_type"),
                "provider": result.get("provider"),
                "raw_request": user_input,
                "session_id": session_id,
                "extracted_requirements": result.get("extracted_requirements", {}),
                "missing_info": result.get("missing_info", []),
                "conversation_history": self._get_conversation_history(session_id),
                "confidence": result.get("confidence", 0.5)
            },
            "reasoning": result.get("reasoning", ""),
            "mode": "agentic"
        }
    
    def execute_action(self, action: Action) -> Any:
        """Execute routing action"""
        if action.name == "route_to_agent":
            agent_name = action.parameters.get("agent_name")
            context = action.parameters.get("context", {})
            
            return {
                "next_agent": agent_name,
                "context": context,
                "reasoning": action.reasoning,
                "confidence": action.confidence
            }
        
        elif action.name == "request_clarification":
            return {
                "next_agent": "clarification",
                "context": {
                    "question": action.parameters.get("question"),
                    "original_context": action.parameters.get("context", {})
                },
                "reasoning": action.reasoning
            }
        
        else:
            logger.warning(f"[Orchestrator] Unknown action: {action.name}")
            return None
    
    def _get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history for session"""
        if not session_id:
            return []
        
        history = []
        for item in self.memory.short_term:
            if item.get("session_id") == session_id:
                history.append({
                    "role": "user" if item.get("type") == "user_input" else "assistant",
                    "content": item.get("content", "")
                })
        
        return history[-10:]  # Last 10 messages
    
    def _get_session_memory(self, session_id: str) -> Dict[str, Any]:
        """Get session-specific memory"""
        if not session_id:
            return {}
        
        session_memory = {
            "user_preferences": self.memory.user_preferences.get(session_id, {}),
            "previous_intents": [],
            "previous_providers": []
        }
        
        # Extract patterns from previous routings
        for key, value in self.memory.long_term.items():
            if f"routing_{session_id}" in key:
                decision = value.get("decision", {})
                if decision:
                    intent = decision.get("context", {}).get("intent")
                    provider = decision.get("context", {}).get("provider")
                    
                    if intent:
                        session_memory["previous_intents"].append(intent)
                    if provider:
                        session_memory["previous_providers"].append(provider)
        
        return session_memory
    
    async def learn_from_outcome(self, session_id: str, outcome: Dict[str, Any], success: bool):
        """
        Learn from routing outcome
        Updates patterns and preferences
        """
        learning_prompt = f"""
        Learn from this routing outcome:
        
        Session: {session_id}
        Outcome: {json.dumps(outcome)}
        Success: {success}
        
        Session memory: {json.dumps(self._get_session_memory(session_id))}
        
        Extract learnings:
        1. What worked well?
        2. What could be improved?
        3. Any user preferences detected?
        4. Patterns to remember?
        
        Respond in JSON:
        {{
            "lessons": [],
            "user_preferences": {{}},
            "routing_improvements": [],
            "confidence_adjustment": -0.1 to 0.1
        }}
        """
        
        learning = self._llm_reason(learning_prompt)
        
        # Update user preferences
        if learning.get("user_preferences"):
            if session_id not in self.memory.user_preferences:
                self.memory.user_preferences[session_id] = {}
            self.memory.user_preferences[session_id].update(learning["user_preferences"])
        
        # Store lessons
        for lesson in learning.get("lessons", []):
            self.memory.learned_patterns.append({
                "type": "routing_outcome",
                "lesson": lesson,
                "success": success,
                "timestamp": datetime.now().isoformat()
            })
        
        # Adjust confidence
        confidence_adj = learning.get("confidence_adjustment", 0)
        self.confidence_threshold = min(1.0, max(0.3, self.confidence_threshold + confidence_adj))
    
    async def get_conversation_state(self, session_id: str) -> Dict[str, Any]:
        """
        Get current conversation state
        Used for context awareness
        """
        state_prompt = f"""
        Analyze the conversation state for session {session_id}:
        
        History: {json.dumps(self._get_conversation_history(session_id))}
        Memory: {json.dumps(self._get_session_memory(session_id))}
        
        Determine:
        1. Current conversation phase
        2. User's apparent goal
        3. Progress toward goal
        4. Next expected interaction
        
        Respond in JSON:
        {{
            "phase": "greeting|gathering|confirming|executing|complete",
            "user_goal": "description",
            "progress_percentage": 0-100,
            "next_expected": "description",
            "context_summary": "brief summary"
        }}
        """
        
        state = self._llm_reason(state_prompt)
        
        return {
            "session_id": session_id,
            "state": state,
            "history_length": len(self._get_conversation_history(session_id)),
            "has_preferences": session_id in self.memory.user_preferences
        }