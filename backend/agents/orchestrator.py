"""
Orchestrator Agent - Routes requests using pure LLM reasoning
NO pattern matching, NO hardcoded rules
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import logging
import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, Action
from utils.reasoning import ReasoningEngine, ReasoningContext
from utils.error_correction import ErrorCorrectionSystem
from utils.learning import Pattern, PatternType

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
            model=os.getenv("AGENT_REASONING_MODEL", "gpt-5-mini")
        )
        
        self.mcp = mcp_client
        self.reasoning_engine = ReasoningEngine(self.model)
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
    
    async def process(self, context: Any, session_id: str = None, progress_callback=None) -> Dict[str, Any]:
        """
        Process user request using pure LLM reasoning
        NO pattern matching allowed
        """
        # Handle both string and dict inputs for compatibility
        if isinstance(context, str):
            user_input = context
            conversation_history = []
        elif isinstance(context, dict):
            user_input = context.get("message", context.get("raw_request", ""))
            session_id = context.get("session_id", session_id)
            conversation_history = context.get("conversation_history", [])
        else:
            user_input = str(context)
            conversation_history = []
        
        logger.info(f"[Orchestrator] Processing: {user_input}")
        
        # Set progress callback if provided
        if progress_callback:
            self.progress_callback = progress_callback
        
        # Emit initial progress
        if self.progress_callback:
            await self.emit_progress("analyzing", "Analyzing user request...", 10)
        
        # Store in memory
        self.memory.short_term.append({
            "type": "user_input",
            "content": user_input,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
        # Optimize: Skip error correction for simple, clear requests
        processed_input = user_input
        skip_correction = False
        
        # Check if request is simple and clear - expanded conditions
        if isinstance(user_input, str):
            user_lower = user_input.lower()
            # Expanded VM keywords to catch more variations
            vm_keywords = ['vm', 'vms', 'virtual machine', 'virtual-machine', 
                          'instance', 'instances', 'server', 'servers', 
                          'compute', 'machine', 'box', 'node', 'linux', 
                          'windows', 'rhel', 'gcp', 'gce']
            database_keywords = ['database', 'db', 'sql', 'mysql', 'postgres', 
                               'rds', 'cloudsql', 'datastore']
            
            # Skip if: short request with clear keywords OR very specific technical request
            is_short_clear = len(user_input) < 100 and any(keyword in user_lower for keyword in vm_keywords)
            # Expanded action keywords for better detection
            action_keywords = ['create', 'deploy', 'provision', 'launch', 'spin up', 'need', 'want', 'set up']
            is_specific_technical = any(keyword in user_lower for keyword in action_keywords) and \
                                  any(keyword in user_lower for keyword in vm_keywords + database_keywords)
            
            if is_short_clear or is_specific_technical:
                skip_correction = True
                logger.info(f"[Orchestrator] Skipping error correction for simple/clear request: {user_input[:50]}...")
        
        if not skip_correction:
            # Apply error correction only for complex/unclear requests
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
        else:
            logger.info(f"[Orchestrator] Using original input without correction")
        
        # Emit progress for intent detection
        if self.progress_callback:
            await self.emit_progress("detecting_intent", "Determining request intent...", 30)
        
        # Create reasoning context with optimized settings
        is_simple = skip_correction  # Simple requests that skipped correction
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
            memory=self._get_session_memory(session_id),
            simple_request=is_simple  # Pass simple flag to reduce iterations
        )
        
        # Check cache first
        cache_key = f"{processed_input}_{session_id}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.info(f"[Orchestrator] Using cached routing decision for: {processed_input[:50]}")
            return cached_result
        
        # Enhanced fast path with better keyword detection
        user_lower = processed_input.lower()
        
        # Comprehensive VM request detection
        vm_keywords = ['vm', 'vms', 'virtual machine', 'virtual-machine',
                      'instance', 'instances', 'server', 'servers',
                      'compute', 'machine', 'box', 'node']
        action_keywords = ['create', 'deploy', 'provision', 'launch', 'spin up', 'need', 'want', 'set up']
        
        is_vm_request = any(keyword in user_lower for keyword in vm_keywords)
        is_compute_action = any(action in user_lower for action in action_keywords) and \
                          any(kw in user_lower for kw in ['server', 'instance', 'machine', 'compute'])
        
        # Use fast path for VM requests
        if is_simple and (is_vm_request or is_compute_action):
            logger.info(f"[Orchestrator] Using fast path for VM request: {processed_input[:50]}")
            
            # Enhanced provider detection
            provider_patterns = {
                'gcp': ['gcp', 'google', 'gce', 'google cloud'],
                'aws': ['aws', 'amazon', 'ec2', 'amazon web services'],
                'azure': ['azure', 'microsoft', 'windows azure'],
                'onprem': ['on-prem', 'on prem', 'onprem', 'datacenter', 'vmware']
            }
            
            # Enhanced OS detection - use correct enum values
            os_patterns = {
                'WINDOWS_22': ['windows 2022', 'win2022', 'win22', 'windows 22'],
                'WINDOWS_19': ['windows 2019', 'win2019', 'win19', 'windows 19'],
                'LINUX_RHEL9': ['rhel9', 'rhel 9', 'red hat 9', 'redhat 9'],
                'LINUX_RHEL8': ['rhel8', 'rhel 8', 'red hat 8', 'redhat 8']
            }
            
            # Extract all possible requirements
            extracted = {}
            
            # Extract business metadata fields first
            import re
            
            # Extract email (requestor.id)
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_match = re.search(email_pattern, processed_input)
            if email_match:
                extracted["id"] = email_match.group(0)
            
            # Extract cost center (5-digit number)
            cost_center_pattern = r'\b\d{5}\b'
            cost_center_match = re.search(cost_center_pattern, processed_input)
            if cost_center_match:
                extracted["costCenter"] = cost_center_match.group(0)
            
            # Extract line of business
            lob_patterns = {
                'RETAIL': ['retail', 'storefront', 'store', 'shop', 'commerce', 'sales'],
                'ISTS': ['ists', 'it services', 'technology services', 'it support', 'tech support'],
                'EDML': ['edml', 'data management', 'data lake', 'analytics', 'data platform']
            }
            for lob, patterns in lob_patterns.items():
                if any(pattern in user_lower for pattern in patterns):
                    extracted["lineOfBusiness"] = lob
                    break
            
            # Detect provider
            for provider, patterns in provider_patterns.items():
                if any(pattern in user_lower for pattern in patterns):
                    extracted["provider"] = provider
                    break
            # Don't set a default provider - let clarification agent handle it
            
            # Enhanced OS detection with defaults
            os_detected = False
            for os_type, patterns in os_patterns.items():
                if any(pattern in user_lower for pattern in patterns):
                    extracted["os"] = os_type
                    os_detected = True
                    break
            
            # Apply OS defaults if not detected (check for generic terms)
            if not os_detected:
                if 'windows' in user_lower:
                    # Check for specific versions first
                    if '2019' in user_lower or 'win19' in user_lower:
                        extracted["os"] = "WINDOWS_19"
                    elif '2022' in user_lower or 'win22' in user_lower:
                        extracted["os"] = "WINDOWS_22"
                    else:
                        extracted["os"] = "WINDOWS_22"  # Default Windows
                elif 'linux' in user_lower or 'rhel' in user_lower or 'red hat' in user_lower:
                    # Check for specific versions
                    if '8' in user_lower:
                        extracted["os"] = "LINUX_RHEL8"
                    elif '9' in user_lower:
                        extracted["os"] = "LINUX_RHEL9"
                    else:
                        extracted["os"] = "LINUX_RHEL9"  # Default Linux
            # Comprehensive environment detection with subtype
            env_keywords = {
                'PROD': ['production', 'prod', 'live', 'operational', 'operations', 
                         'critical', 'customer-facing', 'public'],
                'NONPROD': {
                    'dev': ['development', 'dev', 'develop', 'sandbox', 'demo', 'poc', 
                            'proof of concept', 'prototype', 'experimental', 'training', 
                            'learning', 'education'],
                    'test': ['testing', 'test', 'unit test', 'integration', 'staging', 
                             'stage', 'pre-prod', 'preprod', 'uat', 'user acceptance'],
                    'qa': ['qa', 'quality', 'quality assurance', 'validation', 'verification'],
                    'perf': ['performance', 'perf', 'load test', 'stress test', 
                             'benchmark', 'capacity']
                }
            }
            
            # Check for PROD first
            for keyword in env_keywords['PROD']:
                if keyword in user_lower:
                    extracted["environment"] = "PROD"
                    break
            else:
                # Check for NONPROD with subtype
                for subtype, keywords in env_keywords['NONPROD'].items():
                    for keyword in keywords:
                        if keyword in user_lower:
                            extracted["environment"] = "NONPROD"
                            extracted["appEnvironmentSubtype"] = subtype
                            break
                    if extracted.get("environment"):
                        break
            
            # Detect zone/region
            import re
            zone_pattern = r'\b(us-\w+(-\w+)?|europe-\w+(-\w+)?|asia-\w+(-\w+)?)\b'
            zone_match = re.search(zone_pattern, user_lower)
            if zone_match:
                extracted["zone"] = zone_match.group(0)
            
            # Detect machine type
            machine_patterns = ['e2-', 'n1-', 'n2-', 't2.', 'm5.', 'standard']
            for pattern in machine_patterns:
                if pattern in user_lower:
                    # Try to extract the full machine type
                    machine_match = re.search(f'{pattern}\\w+', user_lower)
                    if machine_match:
                        extracted["machine_type"] = machine_match.group(0)
                    break
            
            # Enhanced use type detection
            if any(x in user_lower for x in ['database', 'db', 'mysql', 'postgres', 'mongodb', 'redis', 'storage']):
                extracted["use_type"] = "database"
            elif any(x in user_lower for x in ['web', 'website', 'frontend', 'ui']):
                extracted["use_type"] = "app"  # Map to 'app' for TAXI compatibility
            elif any(x in user_lower for x in ['api', 'backend', 'service', 'microservice', 'application']):
                extracted["use_type"] = "app"
            else:
                # Default use type if unclear
                extracted["use_type"] = "app"
            
            # Project detection (if mentioned)
            if 'project' in user_lower:
                # Try to extract project name (word after 'project')
                project_match = re.search(r'project\s+(\S+)', user_lower)
                if project_match:
                    extracted["project"] = project_match.group(1)
            
            # Separate business metadata from technical fields
            business_metadata = {}
            technical_fields = {}
            
            for key, value in extracted.items():
                if key in ['id', 'costCenter', 'lineOfBusiness', 'environment', 'appEnvironmentSubtype']:
                    business_metadata[key] = value
                else:
                    technical_fields[key] = value
            
            routing_decision = {
                "next_agent": "compute",
                "context": {
                    "intent": "create_compute",
                    "resource_type": "vm",
                    "provider": technical_fields.get("provider"),  # No default - will be None if not specified
                    "raw_request": processed_input,
                    "session_id": session_id,
                    "extracted_requirements": extracted,
                    "business_metadata": business_metadata,  # Pass business metadata separately
                    "technical_fields": technical_fields,  # Pass technical fields separately
                    "missing_info": [],
                    "conversation_history": [],
                    "confidence": 0.95
                },
                "reasoning": f"VM request detected with keywords - routing to compute agent. Extracted business metadata: {list(business_metadata.keys())}, technical: {list(technical_fields.keys())}",
                "mode": "fast_path"
            }
            reasoning_chain = []
            logger.info(f"[Orchestrator] Fast path extracted: {extracted}")
            
            # Log environment inference if applied
            if extracted.get("environment"):
                env_msg = f"Inferred environment: {extracted['environment']}"
                if extracted.get("appEnvironmentSubtype"):
                    env_msg += f" (subtype: {extracted['appEnvironmentSubtype']})"
                logger.info(f"[Orchestrator] {env_msg}")
            
            # Log OS defaults if applied
            if extracted.get("os"):
                if 'linux' in user_lower and extracted["os"] == "LINUX_RHEL9":
                    logger.info("[Orchestrator] Applied default OS: LINUX_RHEL9 for generic Linux")
                elif 'windows' in user_lower and extracted["os"] == "WINDOWS_22":
                    logger.info("[Orchestrator] Applied default OS: WINDOWS_22 for generic Windows")
                elif 'server' in user_lower and extracted["os"] == "LINUX_RHEL9":
                    logger.info("[Orchestrator] Applied default OS: LINUX_RHEL9 for generic server")
        else:
            # Use reasoning engine for complex requests
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
        
        # Cache the result
        self._cache_result(cache_key, routing_decision)
        
        # Emit routing progress
        if self.progress_callback:
            next_agent = routing_decision.get("next_agent", "unknown")
            await self.emit_progress("routing", f"Routing to {next_agent} agent...", 50)
        
        return routing_decision
    
    async def _direct_reasoning(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """
        Direct LLM reasoning for routing decision
        Simplified prompt focusing on resource type detection only
        """
        # Enhanced simple request detection
        vm_keywords = ['vm', 'vms', 'virtual machine', 'virtual-machine',
                      'instance', 'instances', 'server', 'servers',
                      'compute', 'machine', 'box', 'node']
        is_simple = len(user_input) < 100 and any(kw in user_input.lower() for kw in vm_keywords)
        
        if is_simple:
            # Simplified prompt for simple requests with VM-specific examples
            routing_prompt = f"""
            Route this request to the correct agent and extract business metadata:
            User: {user_input}
            
            Available agents: {list(self.available_agents.keys())}
            
            Examples:
            - "I want a VM" -> {{"resource_type": "vm", "next_agent": "compute", "confidence": 0.95}}
            - "Create a GCP instance for retail" -> {{"resource_type": "vm", "next_agent": "compute", "lineOfBusiness": "RETAIL", "confidence": 0.95}}
            - "Deploy a server with cost center 12345" -> {{"resource_type": "vm", "next_agent": "compute", "costCenter": "12345", "confidence": 0.9}}
            
            Extract business metadata if present:
            - Email addresses -> "id"
            - 5-digit numbers -> "costCenter"  
            - retail/ISTS/EDML mentions -> "lineOfBusiness"
            - prod/nonprod mentions -> "appEnvironment"
            
            Return JSON:
            {{
                "resource_type": "vm|database|network|storage|other",
                "next_agent": "agent_name",
                "confidence": 0.0-1.0,
                "business_metadata": {{
                    "id": "email if found",
                    "costCenter": "5-digit if found",
                    "lineOfBusiness": "RETAIL|ISTS|EDML if found",
                    "appEnvironment": "PROD|NONPROD if found"
                }}
            }}
            
            IMPORTANT: For any VM, server, instance, or compute request, route to "compute" agent.
            """
        else:
            # Full prompt for complex requests with better VM detection
            routing_prompt = f"""
            As an intelligent orchestrator, analyze this request and decide routing:
            
            User input: {user_input}
            Conversation history: {json.dumps(self._get_conversation_history(session_id)[-2:])}
            
            Available agents:
            {json.dumps(self.available_agents)}
            
            Routing rules:
            1. VM/instance/server/compute requests -> "compute" agent
            2. Database requests -> "database" agent
            3. Unclear requests -> "clarification" agent
            
            Common VM request patterns:
            - "I want/need a VM/server/instance"
            - "Create/deploy/provision a VM/server/instance"
            - "Set up a Windows/Linux machine"
            - References to GCP/AWS/Azure compute resources
            
            Extract business metadata if present:
            - Email addresses (e.g., user@company.com) -> "id"
            - 5-digit numbers (e.g., 12345) -> "costCenter"
            - Line of business: retail/ISTS/EDML -> "lineOfBusiness"
            - Environment: production/prod/nonprod/dev/test -> "appEnvironment"
            - Environment subtype: dev/qa/test/perf -> "appEnvironmentSubtype"
            
            Respond in JSON:
            {{
                "intent": "brief description",
                "resource_type": "vm|database|network|storage|other",
                "provider": "gcp|aws|azure|unclear",
                "confidence": 0.0-1.0,
                "next_agent": "agent_name",
                "reasoning": "brief explanation",
                "business_metadata": {{
                    "id": "email if found",
                    "costCenter": "5-digit if found",
                    "lineOfBusiness": "RETAIL|ISTS|EDML if found",
                    "appEnvironment": "PROD|NONPROD if found",
                    "appEnvironmentSubtype": "dev|qa|test|perf if found"
                }}
            }}
            
            IMPORTANT: Default to "compute" agent for ANY request mentioning VMs, servers, instances, or compute resources.
            """
        
        result = self._llm_reason(routing_prompt)
        
        # Validate and correct routing decision for obvious VM requests
        vm_keywords = ['vm', 'vms', 'virtual machine', 'instance', 'server', 'compute', 'machine']
        if any(kw in user_input.lower() for kw in vm_keywords):
            if result.get("next_agent") == "clarification":
                logger.warning(f"[Orchestrator] Correcting routing: VM keywords detected but routed to clarification")
                result["next_agent"] = "compute"
                result["confidence"] = max(result.get("confidence", 0.5), 0.8)
                result["reasoning"] = "Corrected: VM keywords detected - routing to compute agent"
        
        # Build routing response
        next_agent = result.get("next_agent", "compute")  # Default to compute instead of clarification
        
        # Extract business metadata from result
        business_metadata = result.get("business_metadata", {})
        extracted_requirements = result.get("extracted_requirements", {})
        
        # Merge business metadata into extracted requirements
        if business_metadata:
            for key, value in business_metadata.items():
                if value and value not in ["email if found", "5-digit if found", "RETAIL|ISTS|EDML if found", "PROD|NONPROD if found", "dev|qa|test|perf if found"]:
                    extracted_requirements[key] = value
        
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
                "extracted_requirements": extracted_requirements,
                "business_metadata": business_metadata,  # Pass business metadata separately
                "missing_info": result.get("missing_info", []),
                "conversation_history": self._get_conversation_history(session_id),
                "confidence": result.get("confidence", 0.5)
            },
            "reasoning": result.get("reasoning", ""),
            "mode": "agentic"
        }
    
    async def reflect_on_routing(self, 
                                routing_decision: str,
                                outcome: str,
                                session_context: Dict) -> Dict[str, Any]:
        """
        Specialized reflection for routing decisions.
        Analyzes if correct agent was chosen and learns routing patterns.
        """
        reflection_prompt = f"""
        Analyze this routing decision:
        
        Decision: Routed to {routing_decision}
        Outcome: {outcome}
        Context: {json.dumps(session_context, default=str)}
        
        Previous routing patterns:
        {json.dumps(self.memory.learned_patterns[-5:], default=str)}
        
        Evaluate:
        1. Was the correct agent chosen?
        2. Could a different agent have handled this better?
        3. What routing patterns are emerging?
        4. How can routing confidence thresholds be adjusted?
        
        Return JSON:
        {{
            "correct_routing": true/false,
            "better_agent": "agent_name or null",
            "routing_patterns": [],
            "confidence_adjustment": {{"agent_name": adjustment}},
            "lessons": [],
            "user_type_pattern": "description or null"
        }}
        """
        
        analysis = self._llm_reason(reflection_prompt)
        
        # Learn routing patterns for specific user types
        if analysis.get("user_type_pattern"):
            pattern = Pattern(
                type=PatternType.PREFERENCE,
                description=f"User type routing: {analysis['user_type_pattern']}",
                occurrences=1,
                confidence=0.7,
                metadata={"routing_decision": routing_decision, "outcome": outcome}
            )
            
            if self.learning_engine:
                await self.share_learning(pattern, pattern.confidence)
        
        # Adjust routing confidence thresholds
        if analysis.get("confidence_adjustment"):
            for agent, adjustment in analysis["confidence_adjustment"].items():
                current = self.memory.long_term.get(f"routing_confidence_{agent}", 0.6)
                new_confidence = min(1.0, max(0.3, current + adjustment))
                self.memory.long_term[f"routing_confidence_{agent}"] = new_confidence
        
        return analysis
    
    async def evaluate_conversation_flow(self,
                                        conversation_history: List[Dict]) -> Dict[str, Any]:
        """
        Evaluate overall conversation quality and identify improvements.
        """
        evaluation_prompt = f"""
        Evaluate this conversation flow:
        
        History: {json.dumps(conversation_history, default=str)}
        
        Assess:
        1. Conversation coherence (1-10)
        2. Efficiency (were there unnecessary steps?)
        3. Missed routing opportunities
        4. User satisfaction indicators
        5. Suggested conversation improvements
        
        Return JSON:
        {{
            "coherence_score": 1-10,
            "efficiency_score": 1-10,
            "unnecessary_steps": [],
            "missed_opportunities": [],
            "satisfaction_indicators": {{
                "positive": [],
                "negative": []
            }},
            "improvements": []
        }}
        """
        
        evaluation = self._llm_reason(evaluation_prompt)
        
        # Learn from conversation patterns
        if evaluation.get("coherence_score", 0) >= 8:
            # This was a good conversation flow - learn from it
            flow_pattern = {
                "type": "successful_flow",
                "steps": len(conversation_history),
                "coherence": evaluation["coherence_score"],
                "efficiency": evaluation.get("efficiency_score", 0)
            }
            self.memory.learned_patterns.append(flow_pattern)
        
        # Identify improvement opportunities
        if evaluation.get("missed_opportunities"):
            for opportunity in evaluation["missed_opportunities"]:
                self.memory.long_term[f"improvement_{datetime.now().timestamp()}"] = opportunity
        
        return evaluation
    
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
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached routing decision if available and not expired
        """
        if cache_key in self.request_cache:
            cached = self.request_cache[cache_key]
            if (datetime.now() - cached['timestamp']).seconds < self.cache_ttl:
                return cached['result']
            else:
                # Expired, remove from cache
                del self.request_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """
        Cache routing decision with timestamp
        """
        self.request_cache[cache_key] = {
            'result': result,
            'timestamp': datetime.now()
        }
        
        # Clean old cache entries
        current_time = datetime.now()
        expired_keys = [
            k for k, v in self.request_cache.items()
            if (current_time - v['timestamp']).seconds > self.cache_ttl
        ]
        for key in expired_keys:
            del self.request_cache[key]
    
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