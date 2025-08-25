"""
GCE Specialist Agent - Handles GCP-specific provisioning with LLM reasoning
NO hardcoded validation rules - all through intelligent reasoning
"""

from typing import Dict, Any, List, Optional
from models.taxi_models import VMRequest, MachineType
import logging
import json
from datetime import datetime
from agents.base_agent import BaseAgent, Action
from utils.learning import Pattern, PatternType
import os

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
        
        analysis = self._llm_reason(reflection_prompt)
        
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
    
    def _extract_vm_requirements(self, raw_request: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract VM requirements from raw request with intelligent corrections
        Focus on TAXI required fields only
        """
        extraction_prompt = f"""
        Extract GCE VM requirements from this request:
        {raw_request}
        
        Context: {json.dumps(context, default=str)[:500]}
        
        Apply intelligent corrections:
        - "red hat 8" or "rhel 8" → LINUX_RHEL8
        - "red hat 9" or "rhel 9" → LINUX_RHEL9  
        - "windows 2019" or "win19" → WINDOWS_19
        - "windows 2022" or "win22" → WINDOWS_22
        - "us-east" → Identify as region, needs zone clarification
        - "cheap vm" → Suggest e2-micro or e2-small
        - "n1" alone → n1-standard-1
        - "e2" alone → Ask which e2 type
        - Fix common typos and variations
        
        Extract ONLY these TAXI required fields:
        - appEnvironment: NONPROD or PROD
        - appEnvironmentSubtype: dev/qa/test/perf (if NONPROD)
        - lineOfBusiness: RETAIL/ISTS/EDML
        - costCenter: 5-digit code
        - project: GCP project ID
        - zone: Full zone (e.g., us-east4-a)
        - os: LINUX_RHEL8/LINUX_RHEL9/WINDOWS_19/WINDOWS_22
        - useType: app/database
        - machineType: Valid GCP machine type
        - id: User email
        
        DO NOT extract or ask about:
        - Firewall rules
        - SSH keys
        - Service accounts
        - Network configurations
        - Disk configurations beyond basic
        
        Return JSON:
        {{
            "extracted_fields": {{
                "appEnvironment": "value or null",
                "appEnvironmentSubtype": "value or null",
                "lineOfBusiness": "value or null",
                "costCenter": "value or null",
                "project": "value or null",
                "zone": "value or null",
                "os": "value or null",
                "useType": "value or null",
                "machineType": "value or null",
                "id": "value or null"
            }},
            "corrections_applied": ["list of corrections"],
            "missing_fields": ["list of required fields not found"],
            "clarifications_needed": ["specific questions for missing info"],
            "confidence": 0.0-1.0
        }}
        """
        
        result = self._llm_reason(extraction_prompt)
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
        
        analysis = self._llm_reason(learning_prompt)
        
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
    
    def execute_action(self, action: Action) -> Any:
        """Execute the chosen action"""
        if action.name == "validate_configuration":
            return self._validate_config_llm(action.parameters.get("vm_request"))
        elif action.name == "suggest_improvements":
            return self._suggest_improvements(action.parameters.get("vm_request"))
        elif action.name == "build_taxi_payload":
            return self._build_taxi_payload(action.parameters.get("vm_request"))
        elif action.name == "provision_instance":
            return self._provision_instance(action.parameters.get("taxi_payload"))
        elif action.name == "check_quota":
            return self._check_quota(action.parameters.get("vm_request"))
        else:
            logger.warning(f"Unknown action: {action.name}")
            return None
    
    def _validate_config_llm(self, vm_request: Dict[str, Any]) -> Dict[str, Any]:
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
        
        result = self._llm_reason(validation_prompt)
        return result
    
    def _suggest_improvements(self, vm_request: Dict[str, Any]) -> Dict[str, Any]:
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
        
        result = self._llm_reason(improvement_prompt)
        return result
    
    def _build_taxi_payload(self, vm_request: VMRequest) -> Dict[str, Any]:
        """
        Build TAXI API payload with intelligent field mapping
        Uses LLM to handle any special cases or transformations
        """
        if isinstance(vm_request, dict):
            # If it's already a dict, use it directly
            vm_dict = vm_request
        else:
            # Convert VMRequest to dict
            vm_dict = vm_request.dict(exclude_none=True)
        
        payload_prompt = f"""
        Build a TAXI API payload from this VM request:
        {json.dumps(vm_dict, default=str)}
        
        The TAXI API expects these fields:
        - cloud: "gcp"
        - resourceType: "compute"
        - action: "create"
        - appEnvironment: NONPROD or PROD
        - appEnvironmentSubtype: dev/qa/test/perf (if NONPROD)
        - os: LINUX_RHEL8/LINUX_RHEL9/WINDOWS_19/WINDOWS_22
        - useType: app or database
        - machineType: GCP machine type
        - zone: GCP zone
        - lineOfBusiness: RETAIL/ISTS/EDML
        - costCenter: 5-digit string
        - project: GCP project name
        - id: User email
        
        Apply any necessary transformations or defaults.
        Use learned patterns: {json.dumps(self.memory.learned_patterns[-3:])}
        
        Return JSON with the complete TAXI payload:
        {{
            "payload": {{}},
            "transformations_applied": [],
            "defaults_added": [],
            "confidence": 0.0-1.0
        }}
        """
        
        result = self._llm_reason(payload_prompt)
        
        # Extract the payload or build a default one
        if result and "payload" in result:
            taxi_payload = result["payload"]
            # Ensure required fields are present
            taxi_payload["cloud"] = "gcp"
            taxi_payload["resourceType"] = "compute"
            taxi_payload["action"] = "create"
            return taxi_payload
        else:
            # Fallback to direct mapping with safe defaults
            self.logger.warning("[GCE] Using fallback payload building")
            # Filter out None values and ensure all required fields
            filtered_dict = {k: v for k, v in vm_dict.items() if v is not None}
            taxi_payload = {
                "cloud": "gcp",
                "resourceType": "compute",
                "action": "create",
                "appEnvironment": filtered_dict.get("appEnvironment", "NONPROD"),
                "os": filtered_dict.get("os", "LINUX_RHEL8"),
                "useType": filtered_dict.get("useType", "app"),
                "machineType": filtered_dict.get("machineType", "e2-small"),
                "zone": filtered_dict.get("zone", "us-central1-a"),
                "lineOfBusiness": filtered_dict.get("lineOfBusiness", "RETAIL"),
                "costCenter": str(filtered_dict.get("costCenter", "00000")),
                "project": filtered_dict.get("project", "default-project"),
                "id": filtered_dict.get("id", "vm-instance")
            }
            # Add subtype if NONPROD
            if taxi_payload["appEnvironment"] == "NONPROD":
                taxi_payload["appEnvironmentSubtype"] = filtered_dict.get("appEnvironmentSubtype", "dev")
            return taxi_payload
    
    def _provision_instance(self, taxi_payload: Dict[str, Any]) -> Dict[str, Any]:
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
                
                error_analysis = self._llm_reason(error_prompt)
                
                return {
                    "success": False,
                    "error": str(e),
                    "analysis": error_analysis
                }
        else:
            # Mock response for testing
            self.logger.info(f"[GCE] Mock provisioning with payload: {json.dumps(taxi_payload, default=str)[:200]}")
            # Ensure we have valid values for the response
            machine_type = taxi_payload.get('machineType', 'e2-small')
            zone = taxi_payload.get('zone', 'us-central1-a')
            
            # Validate machine type format
            if machine_type:
                machine_type_clean = machine_type.replace('-', '').replace('_', '')
            else:
                machine_type_clean = 'e2small'
            
            return {
                "success": True,
                "job_id": f"TAXI-MOCK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "instance_id": f"i-gce-{machine_type_clean}-001",
                "status": "PROVISIONING",
                "message": f"Creating {machine_type} in {zone}",
                "estimated_completion": "2-3 minutes",
                "payload_sent": taxi_payload  # Include payload for debugging
            }
    
    def _check_quota(self, vm_request: Dict[str, Any]) -> Dict[str, Any]:
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
        
        result = self._llm_reason(quota_prompt)
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
                    vm_request.id = vm_request_data["id"]
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
            
            extraction_result = self._extract_vm_requirements(raw_request, context)
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
                vm_request.id = extracted_fields["id"]
        
        # Step 2: Validate configuration (if not skipped)
        validation = {"valid": True, "issues": []}
        if not config.get("skip_validation"):
            self.current_step += 1
            await self.emit_progress("validating", "Validating configuration", 40)
            validation = self._validate_config_llm(vm_request.dict(exclude_none=True))
            
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
            improvements = self._suggest_improvements(vm_request.dict(exclude_none=True))
        
        # Step 4: Build TAXI payload
        self.current_step += 1
        await self.emit_progress("preparing", "Preparing TAXI payload", 70)
        taxi_payload = self._build_taxi_payload(vm_request)
        
        # Step 5: Provision instance
        self.current_step += 1
        await self.emit_progress("provisioning", "Provisioning instance", 90)
        result = self._provision_instance(taxi_payload)
        
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
        vm_dict = vm_request.dict(exclude_none=True) if hasattr(vm_request, 'dict') else vm_request
        validation = self._validate_config_llm(vm_dict)
        
        # Check quota availability
        quota_check = self._check_quota(vm_dict)
        
        return {
            "valid": validation.get("valid", False) and quota_check.get("likely_available", True),
            "validation_issues": validation.get("issues", []),
            "quota_assessment": quota_check,
            "recommendations": validation.get("recommendations", []),
            "confidence": (validation.get("confidence", 0.5) + quota_check.get("confidence", 0.5)) / 2
        }