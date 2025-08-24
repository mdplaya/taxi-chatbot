"""
Clarification Agent - Natural conversation for gathering information
NO templates, pure LLM-driven conversation
"""

from typing import List, Dict, Any, Optional
import logging
import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, Action
from models.taxi_models import VMRequest
from utils.error_correction import ErrorCorrectionSystem

logger = logging.getLogger(__name__)


class ClarificationAgent(BaseAgent):
    """
    Handles gathering missing information through natural conversation
    Shows what's known, asks naturally, accepts corrections
    """
    
    def __init__(self, mcp_client=None):
        super().__init__(
            name="Clarification",
            goal="Gather missing information through natural, friendly conversation",
            model=os.getenv("AGENT_REASONING_MODEL", "gpt-5-mini")
        )
        
        self.mcp = mcp_client
        self.error_correction = ErrorCorrectionSystem(self.model)
        
        # Track conversation flow
        self.clarification_context = {
            "asked_fields": set(),
            "confirmed_values": {},
            "correction_count": 0,
            "conversation_style": "friendly"
        }
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Define clarification agent's tools"""
        return [
            {
                "name": "ShowKnownInfo",
                "description": "Display what we know so far to the user",
                "parameters": ["vm_request", "format"]
            },
            {
                "name": "AskNaturally",
                "description": "Ask for missing information in natural language",
                "parameters": ["missing_fields", "context", "style"]
            },
            {
                "name": "AcceptCorrection",
                "description": "Accept and process user corrections",
                "parameters": ["field", "old_value", "new_value", "reason"]
            },
            {
                "name": "ConfirmBeforeAction",
                "description": "Confirm all details before proceeding",
                "parameters": ["vm_request", "action_description"]
            },
            {
                "name": "SuggestValues",
                "description": "Suggest likely values based on context",
                "parameters": ["field", "context", "suggestions"]
            }
        ]
    
    async def get_clarifications(self, vm_request: VMRequest, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate natural clarification conversation
        NO templates - pure LLM reasoning
        """
        missing_fields = vm_request.get_missing_fields()
        
        # Show what we know first
        known_info = await self._show_known_info(vm_request, missing_fields)
        
        if not missing_fields:
            # Everything complete - confirm before proceeding
            confirmation = await self._confirm_before_action(vm_request, context)
            return confirmation
        
        # Generate natural questions
        questions = await self._generate_natural_questions(
            missing_fields,
            vm_request,
            context
        )
        
        # Check for potential corrections
        corrections = await self._check_for_corrections(vm_request, context)
        
        return {
            "complete": False,
            "known_info": known_info,
            "questions": questions,
            "corrections_available": corrections,
            "current_state": vm_request.dict(),
            "missing_count": len(missing_fields),
            "mode": "conversational"
        }
    
    async def _show_known_info(self, vm_request: VMRequest, missing_fields: List[str]) -> str:
        """
        Show what information we have in a natural way
        """
        show_prompt = f"""
        Create a natural summary of what we know about this VM request:
        
        Current values:
        {json.dumps({k: str(v) for k, v in vm_request.dict().items() if v is not None})}
        
        Missing fields:
        {json.dumps(missing_fields)}
        
        Generate a friendly, conversational summary that:
        1. Shows what we've understood so far
        2. Indicates what's still needed
        3. Allows the user to correct any mistakes
        
        Respond in JSON:
        {{
            "summary": "natural language summary",
            "editable_fields": ["list of fields user can edit"],
            "confidence": 0.0-1.0
        }}
        """
        
        result = self._llm_reason(show_prompt)
        
        # Store in memory for learning
        self.memory.short_term.append({
            "type": "shown_info",
            "vm_request": vm_request.dict(),
            "summary": result.get("summary", ""),
            "timestamp": datetime.now().isoformat()
        })
        
        return result.get("summary", "Here's what I understand so far...")
    
    async def _generate_natural_questions(self, missing_fields: List[str], vm_request: VMRequest, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Generate natural, contextual questions
        NO templates allowed
        """
        # Filter out already asked fields
        new_fields = [f for f in missing_fields if f not in self.clarification_context["asked_fields"]]
        
        if not new_fields:
            return []
        
        question_prompt = f"""
        Generate natural, conversational questions for missing information:
        
        Missing fields: {json.dumps(new_fields)}
        Current context: {json.dumps({k: str(v) for k, v in vm_request.dict().items() if v is not None})}
        User's original request: {context.get('raw_request', '')}
        Conversation history: {json.dumps(context.get('conversation_history', [])[-5:])}
        
        For each field, create a question that:
        1. Feels natural and conversational
        2. Provides helpful context or examples
        3. Suggests likely values if applicable
        4. Explains why we need this information
        5. Allows for flexibility in the answer
        
        Field context:
        - zone: GCP deployment location
        - os: Operating system (RHEL8/9, Windows 2019/2022)
        - costCenter: 5-digit billing code
        - appEnvironment: PROD or NONPROD
        - lineOfBusiness: RETAIL, ISTS, or EDML
        - machineType: VM size (e2-small, n1-standard-1, etc.)
        
        Respond in JSON:
        {{
            "questions": [
                {{
                    "field": "field_name",
                    "question": "natural question",
                    "suggestions": ["possible values"],
                    "why_needed": "brief explanation",
                    "allows_custom": true/false
                }}
            ]
        }}
        """
        
        result = self._llm_reason(question_prompt)
        
        questions = result.get("questions", [])
        
        # Mark fields as asked
        for q in questions:
            self.clarification_context["asked_fields"].add(q.get("field"))
        
        # Learn from question generation
        self.memory.learned_patterns.append({
            "type": "question_generation",
            "fields": new_fields,
            "questions": questions,
            "context": context.get('raw_request', ''),
            "timestamp": datetime.now().isoformat()
        })
        
        return questions
    
    async def _check_for_corrections(self, vm_request: VMRequest, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Proactively check if any values might need correction
        """
        if not any(v is not None for v in vm_request.dict().values()):
            return []
        
        correction_prompt = f"""
        Check if any values might need correction or validation:
        
        Current values: {json.dumps({k: str(v) for k, v in vm_request.dict().items() if v is not None})}
        User context: {context.get('raw_request', '')}
        
        Look for:
        1. Potential typos or misspellings
        2. Values that don't match the context
        3. Inconsistent combinations
        4. Better alternatives
        
        Respond in JSON:
        {{
            "potential_corrections": [
                {{
                    "field": "field_name",
                    "current_value": "value",
                    "suggested_value": "correction",
                    "reason": "why this might be better",
                    "confidence": 0.0-1.0
                }}
            ]
        }}
        """
        
        result = self._llm_reason(correction_prompt)
        
        corrections = result.get("potential_corrections", [])
        
        # Only return high-confidence corrections
        return [c for c in corrections if c.get("confidence", 0) > 0.6]
    
    async def process_answers(self, vm_request: VMRequest, answers: Dict[str, Any]) -> VMRequest:
        """
        Process user answers with intelligent understanding
        Handles variations, corrections, and natural language
        """
        from models.taxi_models import (
            AppEnvironment, AppEnvironmentSubtype, LineOfBusiness,
            OS, UseType, MachineType
        )
        
        for field, value in answers.items():
            if not value:
                continue
            
            # Apply error correction
            correction_result = await self.error_correction.detect_and_correct(
                value,
                {"field": field, "vm_request": vm_request.dict()}
            )
            
            if correction_result.corrected != value:
                logger.info(f"[Clarification] Corrected {field}: {value} -> {correction_result.corrected}")
                value = correction_result.corrected
            
            # Use LLM to understand and normalize the value
            normalized = await self._normalize_value(field, value, vm_request)
            
            if normalized:
                try:
                    # Set the value with proper type conversion
                    if field == "appEnvironment":
                        setattr(vm_request, field, AppEnvironment(normalized))
                    elif field == "appEnvironmentSubtype":
                        setattr(vm_request, field, AppEnvironmentSubtype(normalized))
                    elif field == "lineOfBusiness":
                        setattr(vm_request, field, LineOfBusiness(normalized))
                    elif field == "os":
                        setattr(vm_request, field, OS(normalized))
                    elif field == "useType":
                        setattr(vm_request, field, UseType(normalized))
                    elif field == "machineType":
                        setattr(vm_request, field, MachineType(normalized))
                    else:
                        setattr(vm_request, field, normalized)
                    
                    # Track confirmed values
                    self.clarification_context["confirmed_values"][field] = normalized
                    
                    logger.info(f"[Clarification] Set {field} = {normalized}")
                    
                except ValueError as e:
                    logger.error(f"[Clarification] Invalid value for {field}: {normalized}")
                    # Learn from this error
                    await self.error_correction.learn_from_feedback(
                        value,
                        normalized,
                        False,
                        str(e)
                    )
        
        return vm_request
    
    async def _normalize_value(self, field: str, value: str, vm_request: VMRequest) -> Optional[str]:
        """
        Normalize user input to expected format using LLM
        Handles variations, abbreviations, and natural language
        """
        normalize_prompt = f"""
        Normalize this user input for field '{field}':
        
        User input: {value}
        Field type: {field}
        Current VM request context: {json.dumps({k: str(v) for k, v in vm_request.dict().items() if v is not None})}
        
        Valid values by field:
        - appEnvironment: NONPROD, PROD
        - appEnvironmentSubtype: dev, qa, test, perf
        - lineOfBusiness: RETAIL, ISTS, EDML
        - os: LINUX_RHEL8, LINUX_RHEL9, WINDOWS_19, WINDOWS_22
        - useType: app, database
        - machineType: e2-small, n1-standard-1, n2-standard-2, c2-standard-4, etc.
        - zone: us-east4-a, us-central1-b, etc.
        
        Understand variations like:
        - "production" -> "PROD"
        - "rhel 8" -> "LINUX_RHEL8"
        - "windows server 2019" -> "WINDOWS_19"
        - "retail division" -> "RETAIL"
        - "application server" -> "app"
        
        Respond in JSON:
        {{
            "normalized_value": "the normalized value or null if invalid",
            "confidence": 0.0-1.0,
            "reasoning": "explanation"
        }}
        """
        
        result = self._llm_reason(normalize_prompt)
        
        normalized = result.get("normalized_value")
        confidence = result.get("confidence", 0)
        
        if confidence < 0.5:
            logger.warning(f"[Clarification] Low confidence normalization for {field}: {value} -> {normalized}")
        
        return normalized
    
    async def _confirm_before_action(self, vm_request: VMRequest, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Confirm all details before proceeding
        """
        confirmation_prompt = f"""
        Create a natural confirmation message for this VM request:
        
        Final configuration:
        {json.dumps({k: str(v) for k, v in vm_request.dict().items() if v is not None}, indent=2)}
        
        Generate a friendly confirmation that:
        1. Summarizes the configuration
        2. Highlights important details
        3. Asks for final confirmation
        4. Mentions they can still make changes
        
        Respond in JSON:
        {{
            "confirmation_message": "natural confirmation text",
            "key_points": ["important details"],
            "allows_edit": true
        }}
        """
        
        result = self._llm_reason(confirmation_prompt)
        
        return {
            "complete": True,
            "vm_request": vm_request.dict(),
            "confirmation": result.get("confirmation_message"),
            "key_points": result.get("key_points", []),
            "allows_edit": result.get("allows_edit", True),
            "mode": "conversational"
        }
    
    def execute_action(self, action: Action) -> Any:
        """Execute clarification actions"""
        if action.name == "ShowKnownInfo":
            return {
                "action": "show",
                "content": action.parameters.get("vm_request"),
                "format": action.parameters.get("format", "summary")
            }
        
        elif action.name == "AskNaturally":
            return {
                "action": "ask",
                "fields": action.parameters.get("missing_fields"),
                "style": action.parameters.get("style", "friendly")
            }
        
        elif action.name == "AcceptCorrection":
            field = action.parameters.get("field")
            new_value = action.parameters.get("new_value")
            
            # Track correction
            self.clarification_context["correction_count"] += 1
            
            # Learn from correction
            self.learn_from_correction(
                action.parameters.get("old_value"),
                new_value,
                f"User corrected {field}"
            )
            
            return {
                "action": "correct",
                "field": field,
                "new_value": new_value,
                "accepted": True
            }
        
        elif action.name == "ConfirmBeforeAction":
            return {
                "action": "confirm",
                "vm_request": action.parameters.get("vm_request"),
                "requires_confirmation": True
            }
        
        else:
            logger.warning(f"[Clarification] Unknown action: {action.name}")
            return None
    
    async def handle_user_correction(self, field: str, old_value: Any, new_value: Any, reason: Optional[str] = None):
        """
        Handle user corrections gracefully
        Learn from them for future interactions
        """
        correction_prompt = f"""
        Process this user correction:
        
        Field: {field}
        Old value: {old_value}
        New value: {new_value}
        Reason: {reason or "User preference"}
        
        Understand:
        1. Why the user made this correction
        2. What pattern to learn
        3. How to avoid this in future
        
        Respond in JSON:
        {{
            "acknowledged": "friendly acknowledgment",
            "lesson_learned": "what to remember",
            "pattern": "pattern to recognize",
            "apply_to_similar": true/false
        }}
        """
        
        result = self._llm_reason(correction_prompt)
        
        # Store correction pattern
        self.memory.corrections.append({
            "field": field,
            "old": old_value,
            "new": new_value,
            "reason": reason,
            "lesson": result.get("lesson_learned"),
            "pattern": result.get("pattern"),
            "timestamp": datetime.now().isoformat()
        })
        
        # Learn for future
        await self.error_correction.learn_from_feedback(
            old_value,
            new_value,
            True,
            result.get("lesson_learned", "")
        )
        
        return result.get("acknowledged", "Got it, I've updated that for you.")