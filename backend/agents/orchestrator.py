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
            logger.info(f"[Orchestrator] Fast path detected: {fast_path_result['intent']}")
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
        
        # Check for clarification needs first
        from api.main import _check_clarification_needed
        needs_clarification = await _check_clarification_needed(user_input, session_id)
        
        if needs_clarification:
            logger.info("[Orchestrator] Missing business fields detected, routing to clarification")
            return self._build_routing_response(
                "clarification",
                {"original_request": user_input},
                "Missing required business information",
                0.95
            )
        
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
                    {"original_request": user_input},
                    "Could not understand request",
                    0.3
                )
            
            # Validate and correct agent selection
            if result.get("resource_type") == "compute" and result.get("next_agent") != "compute":
                result["next_agent"] = "compute"
                result["confidence"] = max(result.get("confidence", 0.5), 0.8)
                result["reasoning"] = "Corrected: VM keywords detected - routing to compute agent"
            
            # Build routing response
            return self._build_routing_response(
                result.get("next_agent", "clarification"),
                {
                    "original_request": user_input,
                    "resource_type": result.get("resource_type"),
                    "cloud_provider": result.get("cloud_provider"),
                    "requirements": result.get("requirements", []),
                    "business_metadata": result.get("business_metadata", {})
                },
                result.get("reasoning", ""),
                result.get("confidence", 0.5)
            )
            
        except Exception as e:
            logger.error(f"[Orchestrator] Direct reasoning failed: {e}")
            return self._build_routing_response(
                "clarification",
                {"original_request": user_input, "error": str(e)},
                "Error processing request",
                0.1
            )
    
    def _build_routing_response(self, agent_name: str, context: Dict, reasoning: str, confidence: float) -> Dict[str, Any]:
        """Build standardized routing response"""
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
        
        for key in self.memory.short_term.keys():
            if key.startswith(session_key_prefix):
                history.append(self.memory.short_term[key])
        
        # Sort by timestamp and return last 5
        history.sort(key=lambda x: x.get('timestamp', 0))
        return history[-5:]
    
    def _get_session_memory(self, session_id: str) -> Dict[str, Any]:
        """Get or create session memory"""
        if not session_id:
            return {}
        
        session_key = f"session_{session_id}_memory"
        if session_key not in self.memory.short_term:
            self.memory.short_term[session_key] = {
                'session_id': session_id,
                'created_at': datetime.now().isoformat(),
                'interactions': []
            }
        
        return self.memory.short_term[session_key]
    
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