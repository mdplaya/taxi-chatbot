"""
GCE Specialist Agent - Handles GCP-specific provisioning with LLM reasoning
NO hardcoded validation rules - all through intelligent reasoning
"""

from typing import Dict, Any, List, Optional
from models.taxi_models import VMRequest
from pydantic import ValidationError
import logging
import json
from datetime import datetime
from agents.base_agent import BaseAgent, Action
from utils.learning import Pattern, PatternType
import os
from utils.gcp_catalog import (
    is_valid_machine_type,
    is_valid_zone,
    parse_region,
    is_valid_region,
    machine_family,
    is_family_supported_in_region,
    REGION_SUPPORTED_FAMILIES,
)

logger = logging.getLogger(__name__)


class GCESpecialistAgent(BaseAgent):
    """
    Specialist agent for Google Cloud Platform Compute Engine instances
    Handles field extraction, validation, and provisioning
    """
    
    def __init__(self, mcp_client=None, config=None):
        super().__init__(
            name="GCESpecialistAgent",
            goal="Extract requirements and provision GCE instances",
            model="gpt-5-mini"
        )
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Configuration with bypass flags
        self.config = config or {
            "skip_validation": os.getenv('GCE_SKIP_VALIDATION', 'true').lower() == 'true',
            "skip_improvements": os.getenv('GCE_SKIP_IMPROVEMENTS', 'true').lower() == 'true',
            "skip_quota_check": os.getenv('GCE_SKIP_QUOTA_CHECK', 'true').lower() == 'true'
        }
    
    async def prepare_context(self, input_data: Any) -> Dict[str, Any]:
        """Prepare context for GCE specialist processing"""
        if isinstance(input_data, dict):
            return input_data
        return {"raw_request": str(input_data)}
    
    async def process(self, context: Any, session_id: str = None, progress_callback=None) -> Dict[str, Any]:
        """Process request - delegates to create_instance for compatibility"""
        return await self.create_instance(context)
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Define available tools for GCE provisioning"""
        return [
            {
                "name": "extract_vm_requirements",
                "description": "Extract VM requirements from user request",
                "parameters": ["raw_request", "context"]
            },
            {
                "name": "validate_configuration",
                "description": "Validate VM configuration using intelligent reasoning",
                "parameters": ["vm_request"]
            },
            {
                "name": "suggest_improvements",
                "description": "Suggest configuration improvements based on best practices",
                "parameters": ["vm_request"]
            },
            {
                "name": "build_taxi_payload",
                "description": "Build TAXI API payload from VM request",
                "parameters": ["vm_request"]
            },
            {
                "name": "provision_instance",
                "description": "Provision GCE instance via TAXI API",
                "parameters": ["taxi_payload"]
            },
            {
                "name": "check_quota",
                "description": "Check if resources are available in the zone",
                "parameters": ["vm_request"]
            }
        ]
    
    async def reflect_on_provisioning(self,
                                     requirements: Dict,
                                     taxi_payload: Dict,
                                     provision_result: str) -> Dict[str, Any]:
        """
        Specialized reflection for provisioning decisions.
        Analyzes success patterns and learns optimal configurations.
        """
        reflection_prompt = f"""
        Analyze this provisioning:
        
        Requirements: {json.dumps(requirements, default=str)}
        TAXI payload: {json.dumps(taxi_payload, default=str)}
        Result: {provision_result}
        
        Evaluate:
        1. Was the configuration optimal?
        2. What provisioning patterns led to success/failure?
        3. Any configuration improvements for next time?
        4. Best practices learned?
        5. Common configuration combinations?
        
        Return JSON:
        {{
            "configuration_quality": {{
                "optimal": true/false,
                "improvements": [],
                "quality_score": 0.0-1.0
            }},
            "success_patterns": [
                {{
                    "pattern": "description",
                    "configuration": {{}},
                    "success_rate": 0.0-1.0
                }}
            ],
            "best_practices": [],
            "common_combinations": [
                {{
                    "fields": [],
                    "frequency": "how often seen"
                }}
            ],
            "lessons": []
        }}
        """
        
        analysis = await self.reason(reflection_prompt)
        
        # Learn successful provisioning patterns
        if analysis.get("success_patterns"):
            for success_pattern in analysis["success_patterns"]:
                if success_pattern.get("success_rate", 0) >= 0.8:
                    pattern = Pattern(
                        type=PatternType.SUCCESS,
                        description=f"GCE provisioning: {success_pattern['pattern']}",
                        occurrences=1,
                        confidence=success_pattern["success_rate"],
                        metadata={
                            "configuration": success_pattern.get("configuration", {}),
                            "provision_result": provision_result
                        }
                    )
                    
                    if self.learning_engine:
                        await self.share_learning(pattern, pattern.confidence)
        
        # Store best practices
        if analysis.get("best_practices"):
            current_practices = self.memory.long_term.get("gce_best_practices", [])
            current_practices.extend(analysis["best_practices"])
            self.memory.long_term["gce_best_practices"] = current_practices[-20:]  # Keep last 20
        
        return analysis
    
    async def _extract_vm_requirements(self, raw_request: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract VM requirements from raw request with intelligent corrections
        Focus on TAXI required fields only
        """
        # Get any previously extracted requirements from context
        extracted_requirements = context.get('extracted_requirements', {})
        
        # Get business metadata from context (already extracted by Orchestrator)
        business_metadata = context.get('business_metadata', {})
        
        extraction_prompt = f"""
        Extract TECHNICAL GCE VM requirements from this request (specialist scope only):
        {raw_request}
        
        Context from previous analysis (use as hints if relevant):
        {json.dumps(extracted_requirements, default=str)}
        
        Business metadata already extracted by Orchestrator (DO NOT extract these again):
        {json.dumps(business_metadata, default=str)}
        
        Full context: {json.dumps(context, default=str)[:500]}
        
        IMPORTANT: 
        1. Focus ONLY on specialist technical fields (GCE): project, zone, machineType
        2. DO NOT extract business metadata (id, costCenter, lineOfBusiness, appEnvironment, appEnvironmentSubtype) - handled by Orchestrator
        3. DO NOT extract os or useType - handled by Compute agent. Use values from context if present.
        4. If the context already contains extracted values, use them unless the raw request explicitly contradicts them

        STRICT NON-DEFAULTING FOR ZONE AND MACHINE TYPE:
        - DO NOT assume or default a GCP zone. If only a region is given (e.g., "us-east4"), mark "zone" as missing and include a clarification question like "Which zone (a, b, c) in us-east4?".
        - DO NOT assume or default a machine type. If not explicitly specified, mark "machineType" as missing and include a clarification question like "Which GCP machine type (e.g., e2-small, n1-standard-1)?".

        EXISTING CORRECTIONS:
        - "red hat 8" or "rhel 8" → LINUX_RHEL8
        - "red hat 9" or "rhel 9" → LINUX_RHEL9  
        - "windows 2019" or "win19" → WINDOWS_19
        - "windows 2022" or "win22" → WINDOWS_22
        - "us-east" → Identify as region, needs zone clarification
        - "cheap vm" → Suggest e2-micro or e2-small
        - "n1" alone → n1-standard-1
        - "e2" alone → Ask which e2 type
        - Fix common typos and variations
        
        Extract ONLY these TECHNICAL fields (skip business/resource metadata):
        - project: GCP project ID
        - zone: Full zone (e.g., us-east4-a)
        - machineType: Valid GCP machine type
        
        DO NOT extract these business/resource fields (handled by Orchestrator/Compute):
        - appEnvironment, appEnvironmentSubtype, lineOfBusiness, costCenter, id (user email)
        - os, useType
        
        DO NOT extract or ask about:
        - Firewall rules
        - SSH keys
        - Service accounts
        - Network configurations
        - Disk configurations beyond basic
        
        Return JSON:
        {{
            "extracted_fields": {{
                "project": "value or null",
                "zone": "value or null",
                "machineType": "value or null"
            }},
            "corrections_applied": ["list of corrections"],
            "missing_fields": ["list of TECHNICAL fields not found (only project, zone, machineType)"],
            "clarifications_needed": ["specific questions for missing TECHNICAL info only (project, zone, machineType)"],
            "confidence": 0.0-1.0
        }}
        
        CRITICAL: Return EXACT enum values (case-sensitive):
        - appEnvironment: MUST be exactly "NONPROD" or "PROD" (not "nonprod", "dev", etc.) [from context]
        - os: MUST be exactly "LINUX_RHEL8", "LINUX_RHEL9", "WINDOWS_19", or "WINDOWS_22" [from context]
        - useType: MUST be exactly "app" or "database" (lowercase) [from context]
        - lineOfBusiness: MUST be exactly "RETAIL", "ISTS", or "EDML" (uppercase) [from context]
        - appEnvironmentSubtype: MUST be exactly "dev", "qa", "test", or "perf" (lowercase) [from context]
        - machineType: Use exact GCP machine type strings (e.g., "e2-small", "n1-standard-1")
        """
        
        result = await self.reason(extraction_prompt)
        
        # Merge business metadata from context into the result
        if business_metadata:
            if not result.get("extracted_fields"):
                result["extracted_fields"] = {}
            
            # Add business metadata fields (these won't be in our extraction since we focus on technical fields)
            for key, value in business_metadata.items():
                if value is not None:
                    result["extracted_fields"][key] = value
        
        # Merge context's extracted_requirements into the extracted_fields (os/useType, appEnvironment, etc.)
        if extracted_requirements:
            if not result.get("extracted_fields"):
                result["extracted_fields"] = {}
            
            # Use context values for any fields that are provided
            for key, value in extracted_requirements.items():
                if value is not None:
                    # Map canonical field names appropriately
                    if key == "environment":
                        # Backward-compat: map legacy key
                        result["extracted_fields"]["appEnvironment"] = value
                    else:
                        result["extracted_fields"][key] = value
        
        # Filter out questions for fields we already have (including business metadata)
        if result.get("clarifications_needed"):
            known_fields = set(result["extracted_fields"].keys())
            filtered_questions = []
            
            for question in result["clarifications_needed"]:
                # Check if this question is about a field we already have
                if isinstance(question, dict):
                    field = question.get("field", "")
                    # Skip if we already have this field
                    if field not in known_fields:
                        filtered_questions.append(question)
                elif isinstance(question, str):
                    # Skip questions about fields we already have
                    skip = False
                    for known_field in known_fields:
                        if known_field.lower() in question.lower():
                            skip = True
                            break
                    if not skip:
                        filtered_questions.append(question)
            
            result["clarifications_needed"] = filtered_questions
        
        return result
    
    async def learn_configuration_patterns(self,
                                          successful_configs: List[Dict],
                                          failed_configs: List[Dict]) -> Dict[str, Any]:
        """
        Learn from configuration outcomes.
        Builds configuration recommendation model.
        """
        learning_prompt = f"""
        Learn from these GCE configurations:
        
        Successful configs: {json.dumps(successful_configs, default=str)}
        Failed configs: {json.dumps(failed_configs, default=str)}
        
        Identify:
        1. Patterns in successful configurations
        2. Common failure points
        3. Optimal configuration combinations
        4. Resource sizing recommendations
        5. Zone/region preferences
        
        Return JSON:
        {{
            "success_patterns": [
                {{
                    "pattern": "description",
                    "key_factors": [],
                    "confidence": 0.0-1.0
                }}
            ],
            "failure_patterns": [
                {{
                    "pattern": "description",
                    "avoid": "what to avoid",
                    "alternative": "better option"
                }}
            ],
            "optimal_combinations": [
                {{
                    "machine_type": "type",
                    "os": "os",
                    "zone": "zone",
                    "reason": "why optimal"
                }}
            ],
            "sizing_recommendations": {{
                "use_case": {{
                    "recommended_type": "machine_type",
                    "min_resources": {{}}
                }}
            }},
            "zone_preferences": {{
                "zone": "preference_reason"
            }}
        }}
        """
        
        analysis = await self.reason(learning_prompt)
        
        # Build configuration recommendation model
        config_model = {
            "success_patterns": analysis.get("success_patterns", []),
            "failure_patterns": analysis.get("failure_patterns", []),
            "optimal_combinations": analysis.get("optimal_combinations", []),
            "learned_at": datetime.now().isoformat()
        }
        
        # Store in long-term memory
        self.memory.long_term["gce_config_model"] = config_model
        
        # Share high-confidence patterns
        for pattern_data in analysis.get("success_patterns", []):
            if pattern_data.get("confidence", 0) >= 0.8:
                pattern = Pattern(
                    type=PatternType.OPTIMIZATION,
                    description=f"GCE config: {pattern_data['pattern']}",
                    occurrences=len(successful_configs),
                    confidence=pattern_data["confidence"],
                    metadata=pattern_data
                )
                
                if self.learning_engine:
                    await self.share_learning(pattern, pattern.confidence)
        
        # Learn from failures
        for failure in analysis.get("failure_patterns", []):
            self.memory.corrections.append({
                "type": "configuration_failure",
                "pattern": failure["pattern"],
                "avoid": failure.get("avoid"),
                "alternative": failure.get("alternative"),
                "timestamp": datetime.now().isoformat()
            })
        
        return analysis
    
    async def execute_action(self, action: Action) -> Any:
        """Execute the chosen action"""
        if action.name == "validate_configuration":
            return await self._validate_config_llm(action.parameters.get("vm_request"))
        elif action.name == "suggest_improvements":
            return await self._suggest_improvements(action.parameters.get("vm_request"))
        elif action.name == "build_taxi_payload":
            return self._build_taxi_payload(action.parameters.get("vm_request"))
        elif action.name == "provision_instance":
            return await self._provision_instance(action.parameters.get("taxi_payload"))
        elif action.name == "check_quota":
            return await self._check_quota(action.parameters.get("vm_request"))
        else:
            logger.warning(f"Unknown action: {action.name}")
            return None
    
    async def _validate_config_llm(self, vm_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate GCE configuration using LLM reasoning
        NO hardcoded rules - intelligent validation only
        """
        validation_prompt = f"""
        Validate this GCE VM configuration for best practices and correctness:
        {json.dumps(vm_request, default=str)}
        
        Consider these aspects:
        1. Zone validity and availability (GCP zones like us-east4-a, europe-west1-b)
        2. Machine type appropriateness for the use case
        3. OS compatibility with the application type
        4. Environment and subtype consistency
        5. Cost optimization opportunities
        6. Security best practices
        7. Resource sizing (is the machine type appropriate?)
        8. Regional compliance (if applicable)
        
        Use your knowledge of GCP best practices and common patterns.
        Consider learned corrections: {json.dumps(self.memory.corrections[-3:]) if self.memory.corrections else "None"}
        
        Return JSON:
        {{
            "valid": true/false,
            "issues": [
                {{
                    "field": "field_name",
                    "severity": "error/warning/info",
                    "issue": "Description of the issue",
                    "suggestion": "How to fix it",
                    "reasoning": "Why this is an issue"
                }}
            ],
            "confidence": 0.0-1.0,
            "recommendations": []
        }}
        """
        
        result = await self.reason(validation_prompt)
        return result
    
    async def _suggest_improvements(self, vm_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest configuration improvements using LLM reasoning
        Based on best practices and patterns
        """
        improvement_prompt = f"""
        Suggest improvements for this GCE VM configuration:
        {json.dumps(vm_request, default=str)}
        
        Consider:
        1. Cost optimization (could a smaller machine type work?)
        2. Performance optimization (does it need more resources?)
        3. Availability improvements (better zone selection?)
        4. Security enhancements
        5. Compliance requirements
        6. Common patterns for this type of workload
        
        Previous successful configurations: {json.dumps(self.memory.long_term.get("successful_configs", [])[-3:])}
        User preferences: {json.dumps(self.memory.user_preferences)}
        
        Return JSON:
        {{
            "improvements": [
                {{
                    "field": "field_name",
                    "current_value": "current",
                    "suggested_value": "suggested",
                    "reasoning": "Why this is better",
                    "impact": "cost_reduction/performance/security/compliance",
                    "confidence": 0.0-1.0
                }}
            ],
            "overall_assessment": "Summary of configuration quality",
            "estimated_monthly_cost": "Rough estimate if possible"
        }}
        """
        
        result = await self.reason(improvement_prompt)
        return result
    
    def _build_taxi_payload(self, vm_request: VMRequest) -> Dict[str, Any]:
        """
        Build TAXI API payload deterministically without adding defaults.
        If required fields are missing, return a clarification request.
        """
        if isinstance(vm_request, dict):
            vm_dict = vm_request
        else:
            vm_dict = vm_request.model_dump(exclude_none=True)
        
        # Only map what we have; do not invent defaults
        filtered_dict = {k: v for k, v in vm_dict.items() if v is not None}

        # Check for required fields (specialist scope only)
        required_fields = [
            "project", "zone", "machineType"
        ]
        missing_fields = [f for f in required_fields if f not in filtered_dict or filtered_dict[f] is None]

        if missing_fields:
            self.logger.info(f"[GCE] Missing fields for TAXI payload, requesting clarification: {missing_fields}")
            questions = []
            field_to_question = {
                "machineType": "Which GCP machine type do you prefer (e.g., e2-small, n1-standard-1)?",
                "zone": "Which GCP zone should we use (e.g., us-east4-a)?",
                "project": "Which GCP project should this run in?"
            }
            for f in missing_fields:
                q = field_to_question.get(f)
                if q:
                    questions.append({"field": f, "question": q})

            return {
                "success": False,
                "needs_clarification": True,
                "missing_fields": missing_fields,
                "questions": questions,
                "partial_data": filtered_dict
            }

        # All required fields are present; validate against in-code catalog
        mt = filtered_dict.get("machineType")
        zone = filtered_dict.get("zone")

        # 1) Validate machine type
        if not is_valid_machine_type(mt):
            return {
                "success": False,
                "needs_clarification": True,
                "questions": [
                    {
                        "field": "machineType",
                        "question": "Which GCP machine type (e.g., e2-small, n1-standard-1)?",
                        "reason": "Unrecognized machine type"
                    }
                ],
                "partial_data": filtered_dict,
            }

        # 2) Validate zone and region
        if not is_valid_zone(zone):
            return {
                "success": False,
                "needs_clarification": True,
                "questions": [
                    {
                        "field": "zone",
                        "question": "Which GCP zone should we use (e.g., us-east4-a)?",
                        "reason": "Invalid or unsupported zone"
                    }
                ],
                "partial_data": filtered_dict,
            }

        region = parse_region(zone)
        if not is_valid_region(region):
            return {
                "success": False,
                "needs_clarification": True,
                "questions": [
                    {
                        "field": "zone",
                        "question": "Which GCP zone should we use (e.g., us-east4-a)?",
                        "reason": "Invalid or unsupported region"
                    }
                ],
                "partial_data": filtered_dict,
            }

        # 3) Validate region-family support for the chosen machine type
        family = machine_family(mt)
        if not is_family_supported_in_region(family, region):
            supported = sorted(REGION_SUPPORTED_FAMILIES.get(region, set()))
            return {
                "success": False,
                "needs_clarification": True,
                "questions": [
                    {
                        "field": "machineType",
                        "question": "Select a machine type available in the chosen region.",
                        "reason": f"Family {family} not supported in region {region}",
                        "supportedFamilies": supported,
                    }
                ],
                "partial_data": filtered_dict,
            }

        # All required fields present; build payload directly
        taxi_payload = {
            "cloud": "gcp",
            "resourceType": "compute",
            "action": "create",
            **filtered_dict
        }

        if "costCenter" in taxi_payload:
            taxi_payload["costCenter"] = str(taxi_payload["costCenter"])

        if taxi_payload.get("appEnvironment") == "NONPROD" and "appEnvironmentSubtype" in filtered_dict:
            taxi_payload["appEnvironmentSubtype"] = filtered_dict["appEnvironmentSubtype"]

        return taxi_payload
    
    async def _provision_instance(self, taxi_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provision instance via TAXI API
        Handles the actual API call with intelligent error handling
        """
        if self.mcp:
            try:
                result = self.mcp.call_tool("mock_taxi_call", taxi_payload)
                
                # Learn from successful provisioning
                if result.get("success"):
                    self.memory.long_term.setdefault("successful_configs", []).append({
                        "config": taxi_payload,
                        "timestamp": datetime.now().isoformat()
                    })
                
                return result
            except Exception as e:
                logger.error(f"Error calling TAXI API: {e}")
                
                # Use LLM to interpret the error and suggest fixes
                error_prompt = f"""
                The TAXI API call failed with this error:
                {str(e)}
                
                For this payload:
                {json.dumps(taxi_payload)}
                
                Analyze the error and suggest:
                1. What went wrong
                2. How to fix it
                3. Whether to retry
                
                Return JSON:
                {{
                    "error_type": "category of error",
                    "root_cause": "what caused it",
                    "fix_suggestion": "how to fix",
                    "retry_with_changes": {{}},
                    "should_retry": true/false
                }}
                """
                
                error_analysis = await self.reason(error_prompt)
                
                return {
                    "success": False,
                    "error": str(e),
                    "analysis": error_analysis
                }
        else:
            # Mock response for testing
            self.logger.info(f"[GCE] Mock provisioning with payload: {json.dumps(taxi_payload, default=str)[:200]}")
            # Ensure we have valid values for the response (do not assume defaults)
            machine_type = taxi_payload.get('machineType', 'unknown')
            zone = taxi_payload.get('zone', 'unknown')
            
            # Validate machine type format
            if machine_type:
                machine_type_clean = machine_type.replace('-', '').replace('_', '')
            else:
                machine_type_clean = 'unknown'
            
            return {
                "success": True,
                "job_id": f"TAXI-MOCK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "instance_id": f"i-gce-{machine_type_clean}-001",
                "status": "PROVISIONING",
                "message": f"Creating {machine_type} in {zone}",
                "estimated_completion": "2-3 minutes",
                "payload_sent": taxi_payload  # Include payload for debugging
            }
    
    async def _check_quota(self, vm_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check resource availability and quota using intelligent reasoning
        """
        quota_prompt = f"""
        Check if these resources are likely available in GCP:
        {json.dumps(vm_request, default=str)}
        
        Consider:
        1. Common quota limits for the machine type
        2. Zone availability patterns
        3. Regional capacity trends
        4. Time of day effects
        5. Previous provisioning failures: {json.dumps(self.memory.long_term.get("quota_failures", [])[-3:])}
        
        Return JSON:
        {{
            "likely_available": true/false,
            "confidence": 0.0-1.0,
            "potential_issues": [],
            "alternative_zones": [],
            "alternative_machine_types": [],
            "reasoning": "Why this assessment"
        }}
        """
        
        result = await self.reason(quota_prompt)
        return result
    
    async def create_instance(self, context: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create GCE instance - now handles extraction and provisioning
        Can bypass validation/improvements for speed
        """
        # Use provided config or instance defaults
        config = config or self.config
        
        self.logger.info(f"[GCE] Creating instance with config: skip_validation={config.get('skip_validation')}, "
                        f"skip_improvements={config.get('skip_improvements')}")
        
        # Check if VM request is already provided (from clarification flow)
        if "vm_request" in context and context["vm_request"]:
            # VM request already provided from clarification flow
            self.logger.info("[GCE] Using pre-provided VM request from clarification flow")
            
            from models.taxi_models import VMRequest, AppEnvironment, OS, UseType, LineOfBusiness
            
            # Convert dict to VMRequest if needed
            vm_request_data = context["vm_request"]
            if isinstance(vm_request_data, dict):
                vm_request = VMRequest()
                # Map fields from dict to VMRequest
                if vm_request_data.get("appEnvironment"):
                    vm_request.appEnvironment = AppEnvironment(vm_request_data["appEnvironment"])
                if vm_request_data.get("appEnvironmentSubtype"):
                    vm_request.appEnvironmentSubtype = vm_request_data["appEnvironmentSubtype"]
                if vm_request_data.get("lineOfBusiness"):
                    vm_request.lineOfBusiness = LineOfBusiness(vm_request_data["lineOfBusiness"])
                if vm_request_data.get("costCenter"):
                    vm_request.costCenter = vm_request_data["costCenter"]
                if vm_request_data.get("project"):
                    vm_request.project = vm_request_data["project"]
                if vm_request_data.get("zone"):
                    vm_request.zone = vm_request_data["zone"]
                if vm_request_data.get("os"):
                    vm_request.os = OS(vm_request_data["os"])
                if vm_request_data.get("useType"):
                    vm_request.useType = UseType(vm_request_data["useType"])
                if vm_request_data.get("machineType"):
                    vm_request.machineType = vm_request_data["machineType"]
                if vm_request_data.get("id"):
                    try:
                        vm_request.id = vm_request_data["id"]
                    except (ValueError, ValidationError):
                        self.logger.warning(f"[GCE] Ignoring invalid requestor id: {vm_request_data['id']}")
            else:
                vm_request = vm_request_data
            
            # Clear reasoning chain for provisioning
            self.reasoning_chain = []
            self.total_steps = 3
            self.current_step = 0
            
            # Skip extraction since we already have the data
            extraction_result = {"corrections_applied": []}
            
        else:
            # Need to extract from raw request
            raw_request = context.get("raw_request", "")
            
            # Clear reasoning chain
            self.reasoning_chain = []
            self.total_steps = 4 if config.get('skip_validation') else 6
            self.current_step = 0
            
            # Step 1: Extract VM requirements with corrections
            self.current_step += 1
            await self.emit_progress("extracting", "Extracting VM requirements", 20)
            
            extraction_result = await self._extract_vm_requirements(raw_request, context)
            extracted_fields = extraction_result.get("extracted_fields", {})
            
            # Check if clarification needed
            if extraction_result.get("clarifications_needed"):
                return {
                    "success": False,
                    "needs_clarification": True,
                    "questions": extraction_result["clarifications_needed"],
                    "partial_data": extracted_fields,
                    "corrections_applied": extraction_result.get("corrections_applied", [])
                }
            
            # Build VMRequest from extracted fields
            from models.taxi_models import VMRequest, AppEnvironment, OS, UseType, LineOfBusiness
            vm_request = VMRequest()
            
            # Map extracted fields to VMRequest
            if extracted_fields.get("appEnvironment"):
                vm_request.appEnvironment = AppEnvironment(extracted_fields["appEnvironment"])
            if extracted_fields.get("appEnvironmentSubtype"):
                vm_request.appEnvironmentSubtype = extracted_fields["appEnvironmentSubtype"]
            if extracted_fields.get("lineOfBusiness"):
                vm_request.lineOfBusiness = LineOfBusiness(extracted_fields["lineOfBusiness"])
            if extracted_fields.get("costCenter"):
                vm_request.costCenter = extracted_fields["costCenter"]
            if extracted_fields.get("project"):
                vm_request.project = extracted_fields["project"]
            if extracted_fields.get("zone"):
                vm_request.zone = extracted_fields["zone"]
            if extracted_fields.get("os"):
                vm_request.os = OS(extracted_fields["os"])
            if extracted_fields.get("useType"):
                vm_request.useType = UseType(extracted_fields["useType"])
            if extracted_fields.get("machineType"):
                vm_request.machineType = extracted_fields["machineType"]
            if extracted_fields.get("id"):
                try:
                    vm_request.id = extracted_fields["id"]
                except (ValueError, ValidationError):
                    self.logger.warning(f"[GCE] Ignoring invalid extracted requestor id: {extracted_fields['id']}")
        
        # Step 2: Validate configuration (if not skipped)
        validation = {"valid": True, "issues": []}
        if not config.get("skip_validation"):
            self.current_step += 1
            await self.emit_progress("validating", "Validating configuration", 40)
            validation = await self._validate_config_llm(vm_request.model_dump(exclude_none=True))
            
            if not validation.get("valid", False):
                severe_issues = [i for i in validation.get("issues", []) if i.get("severity") == "error"]
                if severe_issues:
                    return {
                        "success": False,
                        "error": "Configuration validation failed",
                        "issues": severe_issues,
                        "needs_clarification": True
                    }
        
        # Step 3: Suggest improvements (if not skipped)
        improvements = {"improvements": []}
        if not config.get("skip_improvements"):
            self.current_step += 1
            await self.emit_progress("optimizing", "Optimizing configuration", 50)
            improvements = await self._suggest_improvements(vm_request.model_dump(exclude_none=True))
        
        # Step 4: Build TAXI payload
        self.current_step += 1
        await self.emit_progress("preparing", "Preparing TAXI payload", 70)
        taxi_payload = self._build_taxi_payload(vm_request)
        # If payload builder indicates clarification is still needed, return early
        if isinstance(taxi_payload, dict) and taxi_payload.get("needs_clarification"):
            return taxi_payload

        # Step 5: Provision instance
        self.current_step += 1
        await self.emit_progress("provisioning", "Provisioning instance", 90)
        result = await self._provision_instance(taxi_payload)
        
        await self.emit_progress("complete", "Instance provisioning complete", 100)
        
        return {
            **result,
            "validation": validation if not config.get('skip_validation') else {"skipped": True},
            "improvements_suggested": improvements.get("improvements", []),
            "payload_sent": taxi_payload,
            "corrections_applied": extraction_result.get("corrections_applied", [])
        }
    
    async def validate_config(self, vm_request: VMRequest) -> Dict[str, Any]:
        """
        Validate GCE configuration with pure LLM reasoning
        """
        vm_dict = (
            vm_request.model_dump(exclude_none=True)
            if hasattr(vm_request, 'model_dump') else (
                vm_request.dict(exclude_none=True) if hasattr(vm_request, 'dict') else vm_request
            )
        )
        validation = await self._validate_config_llm(vm_dict)
        
        # Check quota availability
        quota_check = await self._check_quota(vm_dict)
        
        return {
            "valid": validation.get("valid", False) and quota_check.get("likely_available", True),
            "validation_issues": validation.get("issues", []),
            "quota_assessment": quota_check,
            "recommendations": validation.get("recommendations", []),
            "confidence": (validation.get("confidence", 0.5) + quota_check.get("confidence", 0.5)) / 2
        }
