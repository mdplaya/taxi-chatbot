"""
Orchestrator Agent - Routes requests to appropriate specialist agents
Simplified version with direct LLM routing
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import logging
import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, Action
from utils.reasoning import get_reasoning_engine
from utils.error_correction import ErrorCorrectionSystem
from utils.learning import Pattern, PatternType

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Routes requests to appropriate specialist agents
    Uses simplified LLM reasoning for routing decisions
    """
    
    def __init__(self, mcp_client=None):
        super().__init__(
            name="Orchestrator",
            goal="Understand user intent and route to appropriate specialist agents",
            model=os.getenv("AGENT_REASONING_MODEL", "gpt-5-mini")
        )
        
        self.mcp = mcp_client
        self.reasoning_engine = get_reasoning_engine(self.model)
        self.error_correction = ErrorCorrectionSystem(self.model)
        self.request_cache = {}  # Simple cache for requests
        self.cache_ttl = 300  # 5 minutes TTL
        
        # Agent capabilities for routing
        self.available_agents = {
            "compute": "Handles VM/instance creation and configuration",
            "database": "Manages database provisioning and setup",
            "clarification": "Gathers missing information through natural conversation",
            "gce_specialist": "GCP-specific compute provisioning",
            "azure_specialist": "Azure-specific provisioning",
            "aws_specialist": "AWS-specific provisioning"
        }
        
        # Fast paths for common patterns
        self.fast_paths = {
            "vm_keywords": ["vm", "virtual machine", "instance", "compute", "server"],
            "database_keywords": ["database", "db", "sql", "postgres", "mysql", "mongodb"],
            "cloud_providers": {
                "gcp": ["gcp", "google cloud", "google", "gce"],
                "azure": ["azure", "microsoft azure", "microsoft cloud"],
                "aws": ["aws", "amazon", "ec2", "amazon web services"],
                "onprem": ["on-prem", "on-premises", "on premise", "onpremises", "local", "private cloud"]
            }
        }
    
    def _setup_default_config(self):
        """Setup default configuration for orchestrator"""
        self.config.update({
            'enable_correction': os.getenv('ORCHESTRATOR_ENABLE_CORRECTION', 'false').lower() == 'true',
            'max_correction_attempts': int(os.getenv('ORCHESTRATOR_MAX_CORRECTION_ATTEMPTS', '1')),
            'cache_enabled': os.getenv('ORCHESTRATOR_CACHE_ENABLED', 'false').lower() == 'true',
            'simple_timeout': float(os.getenv('REASONING_TIMEOUT_SIMPLE', '30.0')),
            'complex_timeout': float(os.getenv('REASONING_TIMEOUT_COMPLEX', '120.0')),
            'simple_iterations': int(os.getenv('REASONING_MAX_ITERATIONS_SIMPLE', '2')),
            'complex_iterations': int(os.getenv('REASONING_MAX_ITERATIONS', '5'))
        })
    
    async def prepare_context(self, input_data: Any) -> Dict[str, Any]:
        """Prepare context for routing decision"""
        if isinstance(input_data, dict):
            # Handle 'message' key from API and normalize to 'user_input'
            if "message" in input_data and "user_input" not in input_data:
                input_data["user_input"] = input_data["message"]
            return input_data
        return {"user_input": str(input_data)}
    
    async def process(self, context: Any, session_id: str = None, progress_callback=None) -> Dict[str, Any]:
        """
        Process user request and route to appropriate agent
        Uses simplified LLM reasoning
        """
        self.progress_callback = progress_callback
        logger.info(f"[Orchestrator] Processing request for session: {session_id}")
        logger.info(f"[Orchestrator] Model: {self.model}, Temperature: 1.0")
        
        # Prepare context
        processed_context = await self.prepare_context(context)
        user_input = processed_context.get("user_input", "")
        logger.info(f"[Orchestrator] User input: {user_input}")
        
        # Initialize session if needed
        if session_id:
            await self.update_session(session_id, processed_context)
        
        # Emit progress for understanding
        if self.progress_callback:
            await self.emit_progress("understanding", "Understanding your request...", 10)
        
        # Simple keyword detection for environment
        environment = self._extract_environment(user_input)
        if environment:
            logger.info(f"[Orchestrator] Detected environment from keywords: {environment}")
        
        # Check for error correction
        skip_correction = self._should_skip_correction(user_input)
        processed_input = user_input
        
        if self.config.get('enable_correction', False) and not skip_correction:
            logger.info(f"[Orchestrator] Attempting error correction...")
            if self.progress_callback:
                await self.emit_progress("correcting", "Checking for common errors...", 20)
            
            correction_result = await self.error_correction.correct(
                user_input,
                context={
                    "session_id": session_id,
                    "conversation_history": self._get_conversation_history(session_id)
                }
            )
            
            if correction_result.has_correction:
                processed_input = correction_result.corrected_text
                logger.info(f"[Orchestrator] Applied correction: {correction_result.reasoning}")
                
                # Store the correction for learning
                if session_id and self.learning_engine:
                    pattern = Pattern(
                        type=PatternType.ERROR_CORRECTION,
                        pattern={"original": user_input, "corrected": processed_input},
                        confidence=correction_result.confidence,
                        frequency=1
                    )
                    await self.learning_engine.learn(pattern, session_id)
            
            if correction_result.requires_confirmation:
                logger.info(f"[Orchestrator] Correction requires confirmation: {correction_result.reasoning}")
        else:
            logger.info(f"[Orchestrator] Using original input without correction")
        
        # Emit progress for intent detection
        if self.progress_callback:
            await self.emit_progress("detecting_intent", "Determining request intent...", 30)
        
        # Check cache first
        cache_key = f"{processed_input}_{session_id}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.info(f"[Orchestrator] Using cached routing decision for: {processed_input[:50]}")
            return cached_result
        
        # Try fast path detection first
        fast_path_result = self._check_fast_path(processed_input, session_id)
        if fast_path_result:
            logger.info(f"[Orchestrator] Fast path detected: {fast_path_result['action']['type']}")
            # Cache and return
            self._cache_result(cache_key, fast_path_result)
            return fast_path_result
        
        # Use direct LLM reasoning
        routing_decision = await self._direct_reasoning(processed_input, session_id)
        
        # Cache the result
        self._cache_result(cache_key, routing_decision)
        
        # Emit routing progress
        if self.progress_callback:
            agent_name = routing_decision.get("action", {}).get("next_agent", "unknown")
            await self.emit_progress("routing", f"Routing to {agent_name} agent...", 40)
        
        return routing_decision
    
    async def _direct_reasoning(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """
        Direct LLM reasoning for routing decision
        Simplified prompt focusing on resource type detection
        """
        logger.info(f"[Orchestrator] Using direct LLM reasoning for routing")
        
        prompt = f"""
        Analyze this request and determine routing:
        "{user_input}"
        
        Available agents:
        - compute: For VM/instance creation (any cloud)
        - database: For database provisioning
        - clarification: When critical information is missing
        
        Detect:
        1. Resource type (compute/database/other)
        2. Cloud provider if mentioned (GCP/Azure/AWS/OnPrem)
        3. Key requirements mentioned
        
        Response format:
        {{
            "resource_type": "compute|database|other",
            "cloud_provider": "gcp|azure|aws|onprem|none",
            "requirements": ["list of extracted requirements"],
            "confidence": 0.0-1.0,
            "next_agent": "agent_name",
            "reasoning": "brief explanation",
            "business_metadata": {{
                "id": "email if found",
                "lineOfBusiness": "if mentioned",
                "costCenter": "if mentioned"
            }}
        }}
        """
        
        try:
            result = await self.reasoning_engine.reason(prompt)
            
            # Handle result
            if not result:
                logger.error("[Orchestrator] LLM reasoning returned empty result")
                return self._build_routing_response(
                    "clarification",
                    {"original_request": user_input, "raw_request": user_input},
                    "Could not understand request",
                    0.3
                )
            
            # Validate and correct agent selection
            if result.get("resource_type") == "compute" and result.get("next_agent") != "compute":
                result["next_agent"] = "compute"
                result["confidence"] = max(result.get("confidence", 0.5), 0.8)
                result["reasoning"] = "Corrected: VM keywords detected - routing to compute agent"
            
            # Build routing response with environment if detected
            context = {
                "original_request": user_input,
                "raw_request": user_input,  # Compute agent expects 'raw_request'
                "resource_type": result.get("resource_type"),
                "cloud_provider": result.get("cloud_provider"),
                "requirements": result.get("requirements", []),
                "business_metadata": result.get("business_metadata", {})
            }
            
            # Add environment if detected
            environment = self._extract_environment(user_input)
            if environment:
                normalized_env = self._normalize_environment(environment)
                context["extracted_requirements"] = {
                    "environment": normalized_env,
                    "environment_confidence": 0.9,
                    "environment_source": "orchestrator"
                }
                logger.info(f"[Orchestrator] Environment detected in LLM path: {normalized_env}")
            
            return self._build_routing_response(
                result.get("next_agent", "clarification"),
                context,
                result.get("reasoning", ""),
                result.get("confidence", 0.5)
            )
            
        except Exception as e:
            logger.error(f"[Orchestrator] Direct reasoning failed: {e}")
            return self._build_routing_response(
                "clarification",
                {"original_request": user_input, "raw_request": user_input, "error": str(e)},
                "Error processing request",
                0.1
            )
    
    def _build_routing_response(self, agent_name: str, context: Dict, reasoning: str, confidence: float) -> Dict[str, Any]:
        """Build standardized routing response"""
        # Extract environment and add to context if not already present
        if "extracted_requirements" not in context:
            context["extracted_requirements"] = {}
        
        # For appEnvironment/appEnvironmentSubtype: NON-deterministic.
        # Detect candidate labels only; never set final values here.
        user_input = context.get("original_request", "")
        candidates = self._detect_environment_candidates(user_input)
        if candidates:
            context["extracted_requirements"]["environment_ambiguous"] = True
            context["extracted_requirements"]["environment_candidates"] = candidates

        # Deterministic extraction for LoB, costCenter, id (email)
        context.setdefault("business_metadata", {})
        src = user_input
        lob = self._extract_line_of_business(src)
        if lob:
            context["business_metadata"]["lineOfBusiness"] = lob
            context["extracted_requirements"]["lineOfBusiness"] = lob
        cc = self._extract_cost_center(src)
        if cc:
            context["business_metadata"]["costCenter"] = cc
            context["extracted_requirements"]["costCenter"] = cc
        email = self._extract_id(src)
        if email:
            context["business_metadata"]["id"] = email
            context["extracted_requirements"]["id"] = email

        return {
            "action": {
                "type": f"route_to_{agent_name}",
                "agent": agent_name,
                "parameters": context,
                "confidence": confidence
            },
            "reasoning": reasoning,
            "mode": "agentic"
        }
    
    def _check_fast_path(self, user_input: str, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Check for fast path routing based on keywords
        Returns routing decision if fast path detected
        """
        lower_input = user_input.lower()
        
        # Check for VM/compute keywords
        if any(keyword in lower_input for keyword in self.fast_paths["vm_keywords"]):
            # Detect cloud provider
            cloud_provider = "none"
            for provider, keywords in self.fast_paths["cloud_providers"].items():
                if any(kw in lower_input for kw in keywords):
                    cloud_provider = provider
                    break
            
            logger.info(f"[Orchestrator] Fast path: VM request detected, provider: {cloud_provider}")
            
            return self._build_routing_response(
                "compute",
                {
                    "original_request": user_input,
                    "raw_request": user_input,  # Compute agent expects 'raw_request'
                    "resource_type": "compute",
                    "cloud_provider": cloud_provider
                },
                "VM/compute keywords detected - fast routing to compute agent",
                0.9
            )
        
        # Check for database keywords
        if any(keyword in lower_input for keyword in self.fast_paths["database_keywords"]):
            logger.info(f"[Orchestrator] Fast path: Database request detected")
            
            return self._build_routing_response(
                "database",
                {
                    "original_request": user_input,
                    "raw_request": user_input,  # For consistency across agents
                    "resource_type": "database"
                },
                "Database keywords detected - fast routing to database agent",
                0.9
            )
        
        return None
    
    def _extract_environment(self, user_input: str) -> Optional[str]:
        """Extract environment from user input using keywords"""
        lower_input = user_input.lower()
        
        env_keywords = {
            "production": ["production", "prod"],
            "development": ["development", "dev"],
            "test": ["test", "testing"],
            "staging": ["staging", "stage"],
            "qa": ["qa", "quality"]
        }
        
        for env, keywords in env_keywords.items():
            if any(kw in lower_input for kw in keywords):
                return env
        
        return None
    
    def _normalize_environment(self, env: Optional[str]) -> Optional[str]:
        """Normalize environment value to PROD/NONPROD"""
        if not env:
            return None
        
        env_mapping = {
            "production": "PROD",
            "development": "NONPROD",
            "test": "NONPROD",
            "staging": "NONPROD",
            "qa": "NONPROD"
        }
        
        return env_mapping.get(env, env.upper())

    def _detect_environment_candidates(self, text: str) -> list:
        """Detect environment-related labels only; do not set values.
        Returns normalized tokens like: prod, dev, qa, test, staging, perf, sit, uat, preprod, production.
        """
        s = (text or "").lower()
        labels = []
        mapping = {
            "production": ["production", "prod"],
            "dev": ["development", "dev"],
            "qa": ["quality", "qa"],
            "test": ["test", "testing", "preprod"],
            "sit": ["sit"],
            "uat": ["uat"],
            "staging": ["staging", "stage"],
            "perf": ["perf", "performance", "load"],
        }
        # Emit normalized tokens for each match; include 'prod' shorthand for production
        for norm, keys in mapping.items():
            if any(k in s for k in keys):
                if norm == "production":
                    # Include both 'production' and 'prod' as candidates for clarity
                    labels.extend(["production", "prod"])
                else:
                    labels.append(norm)
        # De-duplicate while preserving order
        seen = set()
        unique = []
        for x in labels:
            if x not in seen:
                seen.add(x)
                unique.append(x)
        return unique

    def _extract_line_of_business(self, text: str) -> Optional[str]:
        s = (text or "").lower()
        if "retail" in s:
            return "RETAIL"
        if "ists" in s:
            return "ISTS"
        if "edml" in s:
            return "EDML"
        return None

    def _extract_cost_center(self, text: str) -> Optional[str]:
        import re
        m = re.search(r"(^|\D)(\d{5})(\D|$)", text or "")
        return m.group(2) if m else None

    def _extract_id(self, text: str) -> Optional[str]:
        import re
        from pydantic import EmailStr
        m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")
        if not m:
            return None
        candidate = m.group(0)
        try:
            EmailStr(candidate)
            return candidate
        except Exception:
            # Fallback: keep deterministic extraction even if strict validation fails
            return candidate
    
    def _should_skip_correction(self, user_input: str) -> bool:
        """Check if we should skip error correction for simple requests"""
        # Skip for very short inputs
        if len(user_input.strip()) < 10:
            return True
        
        # Skip if it's a simple command
        simple_patterns = [
            "create vm", "new vm", "i need a vm",
            "create database", "new database",
            "help", "status", "list"
        ]
        
        lower_input = user_input.lower().strip()
        return any(lower_input.startswith(pattern) for pattern in simple_patterns)
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached routing result if available"""
        if not self.config.get('cache_enabled', False):
            return None
        
        if cache_key in self.request_cache:
            cached_entry = self.request_cache[cache_key]
            if datetime.now().timestamp() - cached_entry['timestamp'] < self.cache_ttl:
                return cached_entry['result']
            else:
                del self.request_cache[cache_key]
        
        return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache routing result"""
        if self.config.get('cache_enabled', False):
            self.request_cache[cache_key] = {
                'result': result,
                'timestamp': datetime.now().timestamp()
            }
    
    def _get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get recent conversation history for session"""
        if not session_id:
            return []
        
        history = []
        session_key_prefix = f"session_{session_id}_"
        
        for key in self.memory.long_term.keys():
            if key.startswith(session_key_prefix):
                history.append(self.memory.long_term[key])
        
        # Sort by timestamp and return last 5
        history.sort(key=lambda x: x.get('timestamp', 0))
        return history[-5:]
    
    def _get_session_memory(self, session_id: str) -> Dict[str, Any]:
        """Get or create session memory"""
        if not session_id:
            return {}
        
        session_key = f"session_{session_id}_memory"
        if session_key not in self.memory.long_term:
            self.memory.long_term[session_key] = {
                'session_id': session_id,
                'created_at': datetime.now().isoformat(),
                'interactions': []
            }
        
        return self.memory.long_term[session_key]
    
    async def update_session(self, session_id: str, context: Dict[str, Any]):
        """Update session with new interaction"""
        if not session_id:
            return
        
        memory = self._get_session_memory(session_id)
        memory['interactions'].append({
            'timestamp': datetime.now().isoformat(),
            'input': context.get('user_input', ''),
            'context': context
        })
        
        # Keep only last 10 interactions
        memory['interactions'] = memory['interactions'][-10:]
    
    async def execute_action(self, action: Action, session_id: str = None) -> Dict[str, Any]:
        """Execute routing action - delegate to appropriate agent"""
        agent_name = action.parameters.get("agent")
        context = action.parameters.get("context", {})
        
        logger.info(f"[Orchestrator] Executing routing to {agent_name} agent")
        
        # Return routing information for the main application to handle
        return {
            "status": "routed",
            "agent": agent_name,
            "context": context,
            "session_id": session_id
        }
    
    async def validate_action(self, action: Action) -> Tuple[bool, str]:
        """Validate routing action"""
        agent_name = action.parameters.get("agent")
        
        if not agent_name:
            return False, "No agent specified for routing"
        
        if agent_name not in self.available_agents:
            return False, f"Unknown agent: {agent_name}"
        
        return True, "Valid routing action"
    
    async def learn_from_outcome(self, action: Action, outcome: Any, session_id: str = None):
        """Learn from routing outcome"""
        if not self.learning_engine:
            return
        
        # Create learning pattern
        pattern = Pattern(
            type=PatternType.ROUTING_SUCCESS if outcome.get("success") else PatternType.ROUTING_FAILURE,
            pattern={
                "input": action.parameters.get("context", {}).get("original_request", ""),
                "routed_to": action.parameters.get("agent"),
                "outcome": outcome
            },
            confidence=action.confidence,
            frequency=1
        )
        
        await self.learning_engine.learn(pattern, session_id)
    
    async def emit_progress(self, stage: str, message: str, percentage: int):
        """Emit progress update"""
        if self.progress_callback:
            try:
                await self.progress_callback({
                    "stage": stage,
                    "message": message,
                    "percentage": percentage,
                    "agent": self.name
                })
            except Exception as e:
                logger.error(f"Failed to emit progress: {e}")
