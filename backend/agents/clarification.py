"""
Clarification Agent - Natural conversation for gathering information
NO templates, pure LLM-driven conversation
"""

from typing import List, Dict, Any, Optional, Union
import logging
import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, Action
from models.taxi_models import VMRequest
from pydantic import ValidationError
from utils.error_correction import ErrorCorrectionSystem
from utils.learning import Pattern, PatternType
from utils.gcp_catalog import get_all_machine_types, is_valid_machine_type, is_valid_zone, parse_region, is_valid_region

logger = logging.getLogger(__name__)


class ClarificationAgent(BaseAgent):
    """
    Handles gathering missing information through natural conversation
    Shows what's known, asks naturally, accepts corrections
    """
    
    def __init__(self, mcp_client=None, context=None):
        super().__init__(
            name="Clarification",
            goal="Gather missing information through natural, friendly conversation",
            model=os.getenv("AGENT_REASONING_MODEL", "gpt-5-mini")
        )
        
        self.mcp = mcp_client
        self.error_correction = ErrorCorrectionSystem(self.model)
        
        # Track conversation flow - accept asked_fields from context if provided
        asked_fields = set()
        if context and isinstance(context, dict):
            # Accept asked_fields from context
            context_asked_fields = context.get('asked_fields', set())
            if isinstance(context_asked_fields, list):
                asked_fields = set(context_asked_fields)
            elif isinstance(context_asked_fields, set):
                asked_fields = context_asked_fields
        
        self.clarification_context = {
            "asked_fields": asked_fields,
            "confirmed_values": {},
            "correction_count": 0,
            "conversation_style": "friendly"
        }
    
    async def prepare_context(self, input_data: Any) -> Dict[str, Any]:
        """Prepare context for clarification process"""
        if isinstance(input_data, dict):
            return input_data
        return {"user_input": str(input_data)}
    
    async def process(self, context: Any, session_id: str = None, progress_callback=None) -> Dict[str, Any]:
        """Process clarification request - delegates to get_clarifications"""
        self.progress_callback = progress_callback
        
        # Extract VM request from context if available
        vm_request = context.get('vm_request') if isinstance(context, dict) else None
        if not vm_request:
            # Create empty VM request if not provided
            from models.taxi_models import VMRequest
            vm_request = VMRequest()
        
        # Call the existing get_clarifications method
        result = await self.get_clarifications(vm_request, session_id)
        return result
    
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
    
    async def generate_questions(self, vm_request: VMRequest, missing_fields: List[str], progress_callback=None) -> List[Dict[str, str]]:
        """
        Generate questions for missing fields (simplified wrapper for SSE endpoint)
        """
        if progress_callback:
            self.progress_callback = progress_callback
            await self.emit_progress("analyzing", "Analyzing missing information...", 10)
        
        # Use the existing _generate_natural_questions method
        context = {"missing_fields": missing_fields}
        questions = await self._generate_natural_questions(missing_fields, vm_request, context)
        
        if progress_callback:
            await self.emit_progress("complete", "Questions generated", 100)
        
        return questions
    
    async def get_clarifications(self, vm_request: VMRequest, context: Union[Dict[str, Any], str], progress_callback=None) -> Dict[str, Any]:
        """
        Generate natural clarification conversation
        NO templates - pure LLM reasoning
        """
        # Defensive type checking for backward compatibility
        if isinstance(context, str):
            logger.warning(f"Context passed as string instead of dict: '{context[:50]}...'")
            context = {
                'raw_request': context if context else '',
                'conversation_history': [],
                'session_id': None
            }
        elif not isinstance(context, dict):
            logger.error(f"Invalid context type: {type(context)}")
            context = {
                'raw_request': '',
                'conversation_history': [],
                'session_id': None
            }
        
        # Set progress callback if provided
        if progress_callback:
            self.progress_callback = progress_callback
            await self.emit_progress("reviewing", "Reviewing current information...", 20)
        
        missing_fields = vm_request.get_missing_fields()

        # Try LLM-powered guess for business metadata (lineOfBusiness) if missing
        # This is probabilistic; only apply when confidence crosses a threshold.
        try:
            if "lineOfBusiness" in missing_fields:
                threshold_str = os.getenv("CLARIFICATION_LOB_GUESS_THRESHOLD", "0.75")
                try:
                    lob_threshold = float(threshold_str)
                except ValueError:
                    lob_threshold = 0.75

                raw_text = context.get('raw_request', '') if isinstance(context, dict) else ''
                guess = await self._guess_business_metadata(raw_text)
                guessed_lob = guess.get("lineOfBusiness")
                confidence = float(guess.get("confidence", 0) or 0)

                if guessed_lob in {"RETAIL", "ISTS", "EDML"} and confidence >= lob_threshold:
                    from models.taxi_models import LineOfBusiness
                    try:
                        vm_request.lineOfBusiness = LineOfBusiness(guessed_lob)
                        self.clarification_context["confirmed_values"]["lineOfBusiness"] = guessed_lob
                        missing_fields = vm_request.get_missing_fields()
                        self.memory.short_term.append({
                            "type": "lob_guess",
                            "value": guessed_lob,
                            "confidence": confidence,
                            "timestamp": datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.warning(f"[Clarification] Failed to set guessed LOB: {e}")
        except Exception as e:
            logger.warning(f"[Clarification] Skipping LOB guess due to error: {e}")

        # Show what we know first (after any guesses applied)
        known_info = await self._show_known_info(vm_request, missing_fields)
        
        if progress_callback:
            await self.emit_progress("identifying", "Identifying missing fields...", 40)
        
        if not missing_fields:
            # Everything complete - confirm before proceeding
            confirmation = await self._confirm_before_action(vm_request, context)
            return confirmation
        
        # Enforce group-by-group questioning: Business -> Resource -> Specialist
        business_fields = ["lineOfBusiness", "id", "appEnvironment", "appEnvironmentSubtype", "costCenter"]
        resource_fields = ["useType", "os"]
        specialist_fields = ["zone", "machineType"]

        asked = self.clarification_context["asked_fields"]
        # filter out already asked
        remaining = [f for f in missing_fields if f not in asked]

        def first_nonempty_group(fields):
            groups = [business_fields, resource_fields, specialist_fields]
            for g in groups:
                grp = [f for f in fields if f in g]
                if grp:
                    return grp
            return []

        group_missing = first_nonempty_group(remaining)

        # Generate natural questions only for the current group
        questions = await self._generate_natural_questions(
            group_missing if group_missing else remaining,
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
            "current_state": vm_request.model_dump(),
            "missing_count": len(missing_fields),
            "mode": "conversational"
        }

    async def _guess_business_metadata(self, raw_request: str) -> Dict[str, Any]:
        """
        Use the LLM to guess business metadata from the raw request.
        Returns dict with keys: lineOfBusiness (RETAIL|ISTS|EDML|None), confidence, evidence.
        """
        if not raw_request:
            return {}

        prompt = f"""
        From this user request, infer the most likely line of business.
        Choices: RETAIL, ISTS, EDML. If unsure, return null.

        Request:
        {raw_request}

        Respond as JSON:
        {{
          "lineOfBusiness": "RETAIL|ISTS|EDML|null",
          "confidence": 0.0-1.0,
          "evidence": "short rationale"
        }}
        """

        try:
            result = await self.reason(prompt)
            if not isinstance(result, dict):
                return {}

            lob = result.get("lineOfBusiness")
            if lob not in {"RETAIL", "ISTS", "EDML"}:
                lob = None

            try:
                confidence = float(result.get("confidence", 0) or 0)
            except Exception:
                confidence = 0.0

            return {
                "lineOfBusiness": lob,
                "confidence": confidence,
                "evidence": result.get("evidence", "")
            }
        except Exception as e:
            logger.error(f"[Clarification] LOB guess error: {e}")
            return {}
    
    async def _show_known_info(self, vm_request: VMRequest, missing_fields: List[str]) -> str:
        """
        Show what information we have in a natural way
        """
        show_prompt = f"""
        Create a natural summary of what we know about this VM request:
        
        Current values:
        {json.dumps({k: str(v) for k, v in vm_request.model_dump().items() if v is not None})}
        
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
        
        result = await self.reason(show_prompt)
        
        # Store in memory for learning
        self.memory.short_term.append({
            "type": "shown_info",
            "vm_request": vm_request.model_dump(),
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
        
        # Define ordering guidance: Business -> Resource -> Specialist
        business_fields = ["lineOfBusiness", "id", "appEnvironment", "appEnvironmentSubtype", "costCenter"]
        resource_fields = ["useType", "os"]
        specialist_fields = ["zone", "machineType"]

        question_prompt = f"""
        Generate natural, conversational questions for missing information:
        
        Missing fields: {json.dumps(new_fields)}
        Current context: {json.dumps({k: str(v) for k, v in vm_request.model_dump().items() if v is not None})}
        User's original request: {context.get('raw_request', '')}
        Conversation history: {json.dumps(context.get('conversation_history', [])[-5:])}
        
        IMPORTANT ORDERING:
        - Ask Business questions first (any order among them): {json.dumps(business_fields)}
        - Then ask Resource questions (any order among them): {json.dumps(resource_fields)}
        - Then ask Resource Specialist questions (any order among them): {json.dumps(specialist_fields)}
        Only include questions for fields present in Missing fields.
        At most one question per field.

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
        - id: requestor email address (e.g., user@company.com)
        
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
        
        # Try LLM with timeout - increased for production use
        import asyncio
        try:
            # Use configurable timeout from environment, default to 60 seconds
            clarification_timeout = float(os.getenv('CLARIFICATION_TIMEOUT', '60.0'))
            result = await asyncio.wait_for(
                self.reason(question_prompt),
                timeout=clarification_timeout
            )
            questions = result.get("questions", [])
        except asyncio.TimeoutError:
            logger.warning(f"LLM timeout in clarification after {clarification_timeout}s - using fallback questions")
            questions = []
        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            questions = []

        # Optional deterministic fallback disabled by default. To enable, set env CLARIFICATION_DETERMINISTIC_FALLBACKS=true
        if not questions and new_fields and os.getenv('CLARIFICATION_DETERMINISTIC_FALLBACKS', 'false').lower() == 'true':
            fallback_map = {}
            for f in new_fields:
                if f in fallback_map:
                    questions.append(fallback_map[f])
        
        # Convert questions to simple format for API compatibility
        simplified_questions = []
        for q in questions:
            # Ensure all values are strings for Dict[str, str] compatibility
            simplified = {
                "field": str(q.get("field", "")),
                "question": str(q.get("question", "")),
                "description": ""
            }
            
            # Handle suggestions if present
            if "suggestions" in q and q["suggestions"]:
                if isinstance(q["suggestions"], list):
                    simplified["description"] = "Options: " + ", ".join(str(s) for s in q["suggestions"])
                else:
                    simplified["description"] = str(q["suggestions"])
            elif "why_needed" in q:
                simplified["description"] = str(q.get("why_needed", ""))
            
            simplified_questions.append(simplified)
            
            # Mark field as asked
            field_name = q.get("field")
            if field_name:
                self.clarification_context["asked_fields"].add(field_name)
        
        # Enforce group ordering on the final list (Business -> Resource -> Specialist)
        simplified_questions = self._reorder_questions(
            simplified_questions,
            business_fields,
            resource_fields,
            specialist_fields,
        )

        # Learn from question generation
        self.memory.learned_patterns.append({
            "type": "question_generation",
            "fields": new_fields,
            "questions": questions,
            "context": context.get('raw_request', ''),
            "timestamp": datetime.now().isoformat()
        })
        
        # Store updated asked_fields in context for persistence
        context['asked_fields'] = list(self.clarification_context["asked_fields"])
        
        return simplified_questions

    def _reorder_questions(
        self,
        questions: List[Dict[str, str]],
        business_fields: List[str],
        resource_fields: List[str],
        specialist_fields: List[str],
    ) -> List[Dict[str, str]]:
        """Reorder questions to Business -> Resource -> Specialist while preserving in-group order."""
        group_index: Dict[str, int] = {}
        for f in business_fields:
            group_index[f] = 0
        for f in resource_fields:
            group_index[f] = 1
        for f in specialist_fields:
            group_index[f] = 2

        def key_fn(q: Dict[str, str]) -> int:
            return group_index.get(q.get("field", ""), 3)

        # Python sort is stable; preserves relative order within the same group
        return sorted(questions, key=key_fn)
    
    async def _check_for_corrections(self, vm_request: VMRequest, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Proactively check if any values might need correction
        """
        if not any(v is not None for v in vm_request.model_dump().values()):
            return []
        
        correction_prompt = f"""
        Check if any values might need correction or validation:
        
        Current values: {json.dumps({k: str(v) for k, v in vm_request.model_dump().items() if v is not None})}
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
        
        result = await self.reason(correction_prompt)
        
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
            OS, UseType
        )
        
        explicit_app_env: Optional[str] = None
        for field, value in answers.items():
            if not value:
                continue
            
            # Apply error correction (LLM-assisted) for all fields
            correction_result = await self.error_correction.detect_and_correct(
                value,
                {"field": field, "vm_request": vm_request.model_dump()}
            )
            
            corrected_val = getattr(correction_result, "corrected_text", value)
            if corrected_val != value:
                logger.info(f"[Clarification] Corrected {field}: {value} -> {corrected_val}")
                value = corrected_val
            
            # Use LLM to understand and normalize the value
            normalized = await self._normalize_value(field, value, vm_request)
            
            if normalized:
                try:
                    # Set the value with proper type conversion
                    if field == "appEnvironment":
                        setattr(vm_request, field, AppEnvironment(normalized))
                        explicit_app_env = normalized
                    elif field == "appEnvironmentSubtype":
                        setattr(vm_request, field, AppEnvironmentSubtype(normalized))
                    elif field == "lineOfBusiness":
                        setattr(vm_request, field, LineOfBusiness(normalized))
                    elif field == "os":
                        setattr(vm_request, field, OS(normalized))
                    elif field == "useType":
                        setattr(vm_request, field, UseType(normalized))
                    elif field == "machineType":
                        # Accept any supported GCP machine type string
                        setattr(vm_request, field, normalized)
                    else:
                        setattr(vm_request, field, normalized)
                    
                    # Track confirmed values
                    self.clarification_context["confirmed_values"][field] = normalized
                    
                    logger.info(f"[Clarification] Set {field} = {normalized}")
                    
                except (ValueError, ValidationError) as e:
                    logger.error(f"[Clarification] Invalid value for {field}: {normalized}")
                    # Learn from this error
                    await self.error_correction.learn_from_feedback(
                        value,
                        normalized,
                        False,
                        str(e)
                    )
                    # Re-raise for fields that require strict enum values
                    if field in {"appEnvironment", "appEnvironmentSubtype", "lineOfBusiness", "os", "useType", "machineType"}:
                        raise ValueError(f"Invalid value for {field}: {normalized}")
            else:
                # No normalized value returned; if enum-like field, raise ValueError
                if field in {"appEnvironment", "appEnvironmentSubtype", "lineOfBusiness", "os", "useType", "machineType"}:
                    raise ValueError(f"Invalid value for {field}: {value}")
        # If user explicitly set appEnvironment, respect it (do not override via subtype inference)
        if explicit_app_env:
            try:
                vm_request.appEnvironment = AppEnvironment(explicit_app_env)
            except Exception:
                pass

        return vm_request
    
    async def _normalize_value(self, field: str, value: str, vm_request: VMRequest) -> Optional[str]:
        """
        Normalize user input to expected format using LLM
        Handles variations, abbreviations, and natural language
        """
        # Deterministic early handling for email (requestor id) to avoid LLM round trips
        if field == 'id':
            if value is None:
                return None
            v = str(value).strip()
            import re
            # Lightweight email check to avoid external validators in offline/tests
            if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
                return v
            return None
        valid_values_prompt = ""
        if field == 'machineType':
            all_machine_types = get_all_machine_types()
            if all_machine_types:
                valid_values_prompt = f"- machineType: {json.dumps(all_machine_types)}"
            else:
                valid_values_prompt = "- machineType: e2-small, n1-standard-1, n2-standard-2, c2-standard-4, etc."
        else:
            valid_values_prompt = """
            - appEnvironment: NONPROD, PROD
            - appEnvironmentSubtype: dev, qa, test, perf
            - lineOfBusiness: RETAIL, ISTS, EDML
            - os: LINUX_RHEL8, LINUX_RHEL9, WINDOWS_19, WINDOWS_22
            - useType: app, database
            - zone: us-east4-a, us-central1-b, etc.
            """

        normalize_prompt = f"""
        Normalize this user input for field '{field}':

        User input: {value}
        Field type: {field}
        Current VM request context: {json.dumps({k: str(v) for k, v in vm_request.model_dump().items() if v is not None})}

        Valid values by field:
        {valid_values_prompt}

        Understand variations like:
        - "production" -> "PROD"
        - "rhel 8" -> "LINUX_RHEL8"
        - "windows server 2019" -> "WINDOWS_19"
        - "retail division" -> "RETAIL"
        - "application server" -> "app"
        - "standard n1 4gb" -> "n1-standard-4"

        Respond in JSON:
        {{
            "normalized_value": "the normalized value or null if invalid",
            "confidence": 0.0-1.0,
            "reasoning": "explanation"
        }}
        """

        result = await self.reason(normalize_prompt)

        normalized = result.get("normalized_value")
        confidence = result.get("confidence", 0)

        if not normalized or confidence < 0.5:
            # Deterministic fallback normalization for offline/tests
            val = str(value) if value is not None else ""
            v_lower = val.lower()
            v_upper = val.upper()

            if field == 'appEnvironment':
                if v_lower in {"prod", "production"}:
                    return "PROD"
                if v_lower in {"nonprod", "non-prod", "dev", "qa", "test", "perf", "staging"}:
                    return "NONPROD"
                return None
            if field == 'appEnvironmentSubtype':
                if v_lower in {"dev", "development", "develop"}:
                    return "dev"
                if v_lower in {"qa", "quality", "quality-assurance"}:
                    return "qa"
                if v_lower in {"test", "testing", "integration", "staging"}:
                    return "test"
                if v_lower in {"perf", "performance", "load"}:
                    return "perf"
                return None
            if field == 'lineOfBusiness':
                if "retail" in v_lower:
                    return "RETAIL"
                if "ists" in v_lower:
                    return "ISTS"
                if "edml" in v_lower:
                    return "EDML"
                return None
            if field == 'os':
                l = v_lower.replace('_', '-').replace(' ', '-')
                if 'windows' in l or 'win' in l:
                    if '22' in l or '2022' in l:
                        return "WINDOWS_22"
                    if '19' in l or '2019' in l:
                        return "WINDOWS_19"
                    return "WINDOWS_22"
                if 'rhel' in l or 'red-hat' in l or 'redhat' in l or 'linux' in l:
                    if '9' in l:
                        return "LINUX_RHEL9"
                    if '8' in l:
                        return "LINUX_RHEL8"
                    return "LINUX_RHEL9"
                return None
            if field == 'useType':
                if 'database' in v_lower or v_lower == 'db':
                    return "database"
                if 'app' in v_lower or 'application' in v_lower or 'web' in v_lower:
                    return "app"
                return None
            if field == 'machineType':
                # Normalize to enum-friendly lowercase with dashes
                return val.lower().replace('_', '-').replace(' ', '-')
            if field == 'id':
                # Validate using Pydantic EmailStr instead of regex
                try:
                    from pydantic import EmailStr
                    if value is None:
                        return None
                    email = EmailStr(str(value).strip())
                    return str(email)
                except Exception:
                    return None
            if field in {'zone', 'project', 'costCenter'}:
                return value

        return normalized
    
    async def _confirm_before_action(self, vm_request: VMRequest, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Confirm all details before proceeding
        """
        confirmation_prompt = f"""
        Create a natural confirmation message for this VM request:
        
        Final configuration:
        {json.dumps({k: str(v) for k, v in vm_request.model_dump().items() if v is not None}, indent=2)}
        
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
        
        result = await self.reason(confirmation_prompt)
        
        return {
            "complete": True,
            "vm_request": vm_request.model_dump(),
            "confirmation": result.get("confirmation_message"),
            "key_points": result.get("key_points", []),
            "allows_edit": result.get("allows_edit", True),
            "mode": "conversational"
        }
    
    async def reflect_on_clarification(self,
                                      questions_asked: List[str],
                                      user_responses: List[str],
                                      final_data: Dict) -> Dict[str, Any]:
        """
        Specialized reflection for clarification effectiveness.
        Analyzes question quality and learns better phrasing.
        """
        reflection_prompt = f"""
        Analyze this clarification interaction:
        
        Questions asked: {json.dumps(questions_asked)}
        User responses: {json.dumps(user_responses)}
        Final extracted data: {json.dumps(final_data, default=str)}
        
        Evaluate:
        1. Were the questions clear and effective?
        2. Did users understand what was being asked?
        3. Were there unnecessary clarifications?
        4. What question phrasings worked best?
        5. What patterns in user responses emerged?
        
        Return JSON:
        {{
            "question_effectiveness": {{
                "clear_questions": [],
                "confusing_questions": [],
                "effectiveness_score": 1-10
            }},
            "better_phrasings": {{
                "original": "suggested improvement"
            }},
            "unnecessary_clarifications": [],
            "response_patterns": [],
            "lessons": []
        }}
        """
        
        analysis = await self.reason(reflection_prompt)
        
        # Learn better question phrasings
        if analysis.get("better_phrasings"):
            for original, improved in analysis["better_phrasings"].items():
                pattern = Pattern(
                    type=PatternType.OPTIMIZATION,
                    description=f"Question phrasing improvement: {original} -> {improved}",
                    occurrences=1,
                    confidence=0.7,
                    metadata={"original": original, "improved": improved}
                )
                
                if self.learning_engine:
                    await self.share_learning(pattern, pattern.confidence)
        
        # Identify unnecessary clarifications to avoid in future
        if analysis.get("unnecessary_clarifications"):
            for unnecessary in analysis["unnecessary_clarifications"]:
                self.memory.learned_patterns.append({
                    "type": "avoid_clarification",
                    "field": unnecessary,
                    "reason": "Often not needed",
                    "timestamp": datetime.now().isoformat()
                })
        
        return analysis
    
    async def learn_field_patterns(self,
                                  field_name: str,
                                  user_inputs: List[str],
                                  corrections: List[str]) -> Dict[str, Any]:
        """
        Learn common patterns for specific fields.
        Builds field-specific confidence models.
        """
        learning_prompt = f"""
        Learn patterns for field: {field_name}
        
        User inputs: {json.dumps(user_inputs)}
        Corrections made: {json.dumps(corrections)}
        
        Identify:
        1. Common variations in how users specify this field
        2. Typical values or ranges
        3. Common mistakes or typos
        4. Validation patterns
        5. Default preferences
        
        Return JSON:
        {{
            "field_variations": [],
            "common_values": [],
            "error_patterns": [],
            "validation_rules": [],
            "default_preference": "value or null",
            "confidence_model": {{
                "high_confidence_indicators": [],
                "low_confidence_indicators": []
            }}
        }}
        """
        
        analysis = await self.reason(learning_prompt)
        
        # Build field-specific confidence model
        field_pattern = {
            "field": field_name,
            "variations": analysis.get("field_variations", []),
            "common_values": analysis.get("common_values", []),
            "validation": analysis.get("validation_rules", []),
            "learned_at": datetime.now().isoformat()
        }
        
        # Store in long-term memory for this field
        self.memory.long_term[f"field_pattern_{field_name}"] = field_pattern
        
        # Share high-value patterns
        if len(analysis.get("common_values", [])) >= 3:
            pattern = Pattern(
                type=PatternType.PREFERENCE,
                description=f"Common values for {field_name}: {', '.join(analysis['common_values'][:3])}",
                occurrences=len(user_inputs),
                confidence=0.8,
                metadata=field_pattern
            )
            
            if self.learning_engine:
                await self.share_learning(pattern, pattern.confidence)
        
        return analysis
    
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
        
        result = await self.reason(correction_prompt)
        
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
