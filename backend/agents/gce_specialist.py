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

logger = logging.getLogger(__name__)


class GCESpecialistAgent(BaseAgent):
    """
    Specialist agent for Google Cloud Platform Compute Engine instances
    Uses LLM reasoning for validation and provisioning decisions
    """
    
    def __init__(self, mcp_client=None):
        super().__init__(
            name="GCESpecialistAgent",
            goal="Validate and provision GCE instances using intelligent reasoning",
            model="gpt-5-mini"
        )
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Define available tools for GCE provisioning"""
        return [
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
            return result["payload"]
        else:
            # Fallback to direct mapping
            return {
                "cloud": "gcp",
                "resourceType": "compute",
                "action": "create",
                **vm_dict
            }
    
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
            return {
                "success": True,
                "job_id": f"TAXI-MOCK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "instance_id": f"i-gce-{taxi_payload.get('machineType', 'unknown')}-001",
                "status": "PROVISIONING",
                "message": f"Creating {taxi_payload.get('machineType')} in {taxi_payload.get('zone')}",
                "estimated_completion": "2-3 minutes"
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
    
    async def create_instance(self, vm_request: VMRequest) -> Dict[str, Any]:
        """
        Create GCE instance with full reasoning pipeline
        """
        self.logger.info("Creating GCE instance with intelligent reasoning")
        
        # Use the ReAct pattern for the provisioning process
        input_data = {
            "vm_request": vm_request.dict(exclude_none=True) if hasattr(vm_request, 'dict') else vm_request,
            "action": "provision"
        }
        
        # Clear reasoning chain
        self.reasoning_chain = []
        self.total_steps = 5
        self.current_step = 0
        
        # Step 1: Observe the request
        self.current_step += 1
        await self.emit_progress("observing", "Analyzing VM request", 20)
        observation = self.observe(input_data)
        
        # Step 2: Validate configuration
        self.current_step += 1
        await self.emit_progress("validating", "Validating configuration", 40)
        validation = self._validate_config_llm(input_data["vm_request"])
        
        if not validation.get("valid", False):
            # Configuration has issues
            severe_issues = [i for i in validation.get("issues", []) if i.get("severity") == "error"]
            if severe_issues:
                return {
                    "success": False,
                    "error": "Configuration validation failed",
                    "issues": severe_issues,
                    "needs_clarification": True,
                    "reasoning_chain": [t.dict() for t in self.reasoning_chain]
                }
        
        # Step 3: Suggest improvements
        self.current_step += 1
        await self.emit_progress("optimizing", "Optimizing configuration", 50)
        improvements = self._suggest_improvements(input_data["vm_request"])
        
        # Step 4: Build TAXI payload
        self.current_step += 1
        await self.emit_progress("preparing", "Preparing TAXI payload", 70)
        taxi_payload = self._build_taxi_payload(vm_request)
        
        # Step 5: Provision instance
        self.current_step += 1
        await self.emit_progress("provisioning", "Provisioning instance", 90)
        result = self._provision_instance(taxi_payload)
        
        # Reflect on the outcome
        reflection = self.reflect(None, result)
        
        # Store in memory
        self.memory.short_term.append({
            "request": input_data["vm_request"],
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        await self.emit_progress("complete", "Instance provisioning complete", 100)
        
        return {
            **result,
            "validation": validation,
            "improvements_suggested": improvements.get("improvements", []),
            "payload_sent": taxi_payload,
            "reasoning_chain": [t.dict() for t in self.reasoning_chain]
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