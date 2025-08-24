"""
Compute Agent - Extracts VM requirements using pure LLM reasoning
NO pattern matching - all decisions through LLM
"""

from typing import Dict, Any, List, Optional
from models.taxi_models import VMRequest, AppEnvironment, OS, UseType, MachineType, LineOfBusiness, AppEnvironmentSubtype
import logging
import json
from datetime import datetime
from agents.base_agent import BaseAgent, Action

logger = logging.getLogger(__name__)


class ComputeAgent(BaseAgent):
    """
    Handles compute resource requests across all cloud providers
    Uses pure LLM reasoning to extract requirements - NO pattern matching
    """
    
    def __init__(self, mcp_client=None):
        super().__init__(
            name="ComputeAgent",
            goal="Extract VM requirements from natural language using intelligent reasoning",
            model="gpt-5-mini"
        )
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Define available tools for compute extraction"""
        return [
            {
                "name": "extract_requirements",
                "description": "Extract VM requirements from user input",
                "parameters": ["user_input", "conversation_history"]
            },
            {
                "name": "detect_cloud_provider",
                "description": "Detect which cloud provider the user wants",
                "parameters": ["user_input"]
            },
            {
                "name": "normalize_values",
                "description": "Normalize extracted values to valid enum options",
                "parameters": ["raw_values"]
            },
            {
                "name": "validate_requirements",
                "description": "Validate extracted requirements for completeness",
                "parameters": ["requirements"]
            }
        ]
    
    def execute_action(self, action: Action) -> Any:
        """Execute the chosen action"""
        if action.name == "extract_requirements":
            return self._extract_requirements_llm(
                action.parameters.get("user_input", ""),
                action.parameters.get("conversation_history", [])
            )
        elif action.name == "detect_cloud_provider":
            return self._detect_cloud_provider(
                action.parameters.get("user_input", "")
            )
        elif action.name == "normalize_values":
            return self._normalize_values(
                action.parameters.get("raw_values", {})
            )
        elif action.name == "validate_requirements":
            return self._validate_requirements(
                action.parameters.get("requirements", {})
            )
        else:
            logger.warning(f"Unknown action: {action.name}")
            return None
    
    def _extract_requirements_llm(self, user_input: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """
        Use pure LLM reasoning to extract VM requirements
        NO pattern matching - intelligent extraction only
        """
        extraction_prompt = f"""
        Extract VM requirements from this natural language request.
        
        User Input: {user_input}
        
        Conversation History: {json.dumps(conversation_history[-3:]) if conversation_history else "None"}
        
        Previous corrections/learning: {json.dumps(self.memory.corrections[-3:]) if self.memory.corrections else "None"}
        
        Extract these fields if mentioned (be intelligent about variations):
        - environment: NONPROD or PROD (consider: dev/development/test/qa/staging -> NONPROD, prod/production -> PROD)
        - environment_subtype: For NONPROD only - dev, qa, test, or perf
        - os: Operating system
          * LINUX_RHEL8 (RHEL 8, rhel8, rhel-8, Red Hat 8, etc.)
          * LINUX_RHEL9 (RHEL 9, rhel9, rhel-9, Red Hat 9, etc.)
          * WINDOWS_19 (Windows 2019, Windows Server 2019, etc.)
          * WINDOWS_22 (Windows 2022, Windows Server 2022, etc.)
        - use_type: app or database
        - machine_type: GCP machine types like:
          * e2-micro, e2-small, e2-medium, e2-standard-2/4/8 (cost-optimized)
          * n1-standard-1/2/4/8 (previous gen, "n1" alone -> n1-standard-1)
          * n2-standard-2/4/8, n2-highmem-2/4 (balanced/memory)
          * c2-standard-4/8 (compute-optimized)
        - zone: GCP zones like us-east4-a, europe-west1-b, etc.
        - line_of_business: RETAIL, ISTS, or EDML
        - cost_center: 5-digit number if mentioned
        - project: GCP project name if mentioned
        - id: Email address if mentioned
        
        Important:
        - Be smart about variations and typos
        - Consider context from conversation history
        - Apply any learned corrections
        - Handle descriptive requests (e.g., "cheap VM" -> e2-small, "high memory" -> n2-highmem)
        
        Return JSON with extracted fields and confidence scores:
        {{
            "requirements": {{
                "environment": "value or null",
                "environment_subtype": "value or null",
                "os": "value or null",
                "use_type": "value or null",
                "machine_type": "value or null",
                "zone": "value or null",
                "line_of_business": "value or null",
                "cost_center": "value or null",
                "project": "value or null",
                "id": "value or null"
            }},
            "confidence_scores": {{
                "field_name": 0.0-1.0
            }},
            "reasoning": "Explanation of extraction logic"
        }}
        """
        
        result = self._llm_reason(extraction_prompt)
        return result.get("requirements", {})
    
    def _detect_cloud_provider(self, user_input: str) -> str:
        """
        Detect cloud provider using LLM reasoning
        NO hardcoded patterns
        """
        provider_prompt = f"""
        Detect the cloud provider from this request:
        {user_input}
        
        Look for mentions of:
        - GCP/Google Cloud/Google/GCE
        - AWS/Amazon/EC2
        - Azure/Microsoft
        - OnPrem/On-premises/On-prem/Local
        
        Also consider context clues:
        - GCP zones (us-east4-a, etc.)
        - AWS regions (us-east-1, etc.)
        - Azure regions (eastus, westeurope, etc.)
        - Machine types specific to providers
        
        Return JSON:
        {{
            "provider": "gcp/aws/azure/onprem/unknown",
            "confidence": 0.0-1.0,
            "reasoning": "Why this provider was detected"
        }}
        """
        
        result = self._llm_reason(provider_prompt)
        return result.get("provider", "unknown")
    
    def _normalize_values(self, raw_values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize extracted values to valid enum values using LLM
        Handles variations and corrections
        """
        normalization_prompt = f"""
        Normalize these extracted values to valid enum options:
        {json.dumps(raw_values)}
        
        Valid enum values:
        - environment: NONPROD, PROD
        - environment_subtype: dev, qa, test, perf
        - os: LINUX_RHEL8, LINUX_RHEL9, WINDOWS_19, WINDOWS_22
        - use_type: app, database
        - line_of_business: RETAIL, ISTS, EDML
        - machine_type: e2-micro, e2-small, e2-medium, e2-standard-2, e2-standard-4, e2-standard-8,
                       n1-standard-1, n1-standard-2, n1-standard-4, n1-standard-8,
                       n2-standard-2, n2-standard-4, n2-standard-8, n2-highmem-2, n2-highmem-4,
                       c2-standard-4, c2-standard-8
        
        Apply intelligent normalization:
        - Map variations to correct enums
        - Handle case differences
        - Fix common typos
        - Use learned corrections: {json.dumps(self.memory.corrections[-5:])}
        
        Return JSON with normalized values:
        {{
            "normalized": {{}},
            "changes_made": [],
            "confidence": 0.0-1.0
        }}
        """
        
        result = self._llm_reason(normalization_prompt)
        return result.get("normalized", raw_values)
    
    def _validate_requirements(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate requirements for completeness and correctness
        Suggest any corrections needed
        """
        validation_prompt = f"""
        Validate these VM requirements:
        {json.dumps(requirements)}
        
        Check for:
        1. Required fields that are missing
        2. Invalid combinations (e.g., environment_subtype without NONPROD)
        3. Values that don't match valid options
        4. Logical inconsistencies
        
        Return JSON:
        {{
            "valid": true/false,
            "missing_fields": [],
            "invalid_fields": {{}},
            "suggestions": [],
            "confidence": 0.0-1.0
        }}
        """
        
        result = self._llm_reason(validation_prompt)
        return result
    
    async def process(self, context: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
        """
        Process compute request using pure LLM reasoning
        NO pattern matching allowed
        """
        # Set progress callback if provided
        if progress_callback:
            self.progress_callback = progress_callback
        
        raw_request = context.get("raw_request", "")
        conversation_history = context.get("conversation_history", [])
        
        self.logger.info(f"Processing compute request with LLM reasoning")
        
        # Use the ReAct pattern from base class
        input_data = {
            "raw_request": raw_request,
            "conversation_history": conversation_history,
            "context": context
        }
        
        # Clear reasoning chain for new process
        self.reasoning_chain = []
        self.total_steps = 5
        self.current_step = 0
        
        # Step 1: Observe input
        self.current_step += 1
        await self.emit_progress("observing", "Understanding user request", 20)
        observation = self.observe(input_data)
        
        # Step 2: Think about extraction
        self.current_step += 1
        await self.emit_progress("analyzing", "Analyzing requirements with AI", 40)
        reasoning = self.think(observation)
        
        # Step 3: Extract requirements
        self.current_step += 1
        await self.emit_progress("extracting", "Extracting VM requirements", 60)
        
        # Direct extraction using LLM
        requirements = self._extract_requirements_llm(raw_request, conversation_history)
        
        # Step 4: Detect cloud provider
        self.current_step += 1
        await self.emit_progress("detecting", "Detecting cloud provider", 70)
        provider = self._detect_cloud_provider(raw_request)
        
        # Step 5: Normalize and validate
        self.current_step += 1
        await self.emit_progress("validating", "Validating requirements", 80)
        
        # Normalize values
        normalized = self._normalize_values(requirements)
        
        # Create VMRequest with normalized data
        vm_request = VMRequest()
        
        # Map normalized requirements to VMRequest fields
        if normalized.get("environment"):
            try:
                vm_request.appEnvironment = AppEnvironment(normalized["environment"])
            except ValueError:
                self.logger.warning(f"Invalid environment: {normalized['environment']}")
        
        if normalized.get("environment_subtype") and vm_request.appEnvironment == AppEnvironment.NONPROD:
            try:
                vm_request.appEnvironmentSubtype = AppEnvironmentSubtype(normalized["environment_subtype"])
            except ValueError:
                self.logger.warning(f"Invalid subtype: {normalized['environment_subtype']}")
        
        if normalized.get("os"):
            try:
                vm_request.os = OS(normalized["os"])
            except ValueError:
                self.logger.warning(f"Invalid OS: {normalized['os']}")
        
        if normalized.get("use_type"):
            try:
                vm_request.useType = UseType(normalized["use_type"])
            except ValueError:
                self.logger.warning(f"Invalid use type: {normalized['use_type']}")
        
        if normalized.get("machine_type"):
            try:
                # Try to find matching enum value
                for mt in MachineType:
                    if mt.value == normalized["machine_type"]:
                        vm_request.machineType = mt
                        break
            except Exception as e:
                self.logger.warning(f"Invalid machine type: {normalized['machine_type']} - {e}")
        
        if normalized.get("zone"):
            vm_request.zone = normalized["zone"]
        
        if normalized.get("line_of_business"):
            try:
                vm_request.lineOfBusiness = LineOfBusiness(normalized["line_of_business"])
            except ValueError:
                self.logger.warning(f"Invalid LOB: {normalized['line_of_business']}")
        
        if normalized.get("cost_center"):
            vm_request.costCenter = normalized["cost_center"]
        
        if normalized.get("project"):
            vm_request.project = normalized["project"]
        
        if normalized.get("id"):
            vm_request.id = normalized["id"]
        
        # Validate the requirements
        validation = self._validate_requirements(normalized)
        
        # Determine next agent based on provider
        if provider == "gcp":
            next_agent = "gce_specialist"
        elif provider == "azure":
            next_agent = "azure_specialist"
        elif provider == "aws":
            next_agent = "ec2_specialist"
        else:
            # Need clarification on provider
            next_agent = "clarification"
        
        # Reflect on the extraction
        outcome = {
            "success": True,
            "extracted_count": len([v for v in normalized.values() if v]),
            "provider_detected": provider != "unknown"
        }
        
        await self.emit_progress("reflecting", "Learning from extraction", 90)
        reflection = self.reflect(None, outcome)
        
        # Store in short-term memory for context
        self.memory.short_term.append({
            "request": raw_request,
            "extracted": normalized,
            "provider": provider,
            "timestamp": datetime.now().isoformat()
        })
        
        await self.emit_progress("complete", "Requirement extraction complete", 100)
        
        return {
            "next_agent": next_agent,
            "vm_request": vm_request,
            "provider": provider,
            "needs_clarification": len(vm_request.get_missing_fields()) > 0,
            "missing_fields": vm_request.get_missing_fields(),
            "extraction_confidence": validation.get("confidence", 0.5),
            "reasoning_chain": [t.dict() for t in self.reasoning_chain],
            "mode": "llm_reasoning"  # Always LLM reasoning now
        }