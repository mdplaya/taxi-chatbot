import marvin
from marvin import fn
from typing import Dict, Any, Optional
from models.taxi_models import VMRequest, AppEnvironment, OS, UseType, MachineType
import logging

logger = logging.getLogger(__name__)

@fn
def extract_vm_requirements(user_input: str) -> Dict[str, Any]:
    """
    Extract VM requirements from natural language.
    
    Return a dictionary with any identifiable fields:
    - environment: NONPROD or PROD
    - os: LINUX_RHEL8, LINUX_RHEL9, WINDOWS_19, WINDOWS_22
    - use_type: app or database
    - machine_type: n1-STANDARD-1, n2-STANDARD-1, etc.
    - zone: GCP zone like us-east4-a
    - line_of_business: RETAIL, ISTS, or EDML
    
    Example:
    "I need a Linux VM for our retail app in development" ->
    {
        "os": "LINUX_RHEL8",
        "use_type": "app",
        "environment": "NONPROD",
        "line_of_business": "RETAIL"
    }
    """
    pass

class ComputeAgent:
    """Handles compute resource requests across all cloud providers"""
    
    def __init__(self, mcp_client=None):
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process compute request and extract requirements"""
        
        provider = context.get("provider")
        raw_request = context.get("raw_request", "")
        
        self.logger.info(f"Processing compute request for provider: {provider}")
        
        # Extract requirements using Marvin
        try:
            requirements = extract_vm_requirements(raw_request)
            self.logger.info(f"Extracted requirements: {requirements}")
        except Exception as e:
            self.logger.error(f"Error extracting requirements: {e}")
            requirements = {}
        
        # Create VMRequest with extracted data
        vm_request = VMRequest()
        
        # Map extracted requirements to VMRequest fields
        if "environment" in requirements:
            if requirements["environment"] == "NONPROD":
                vm_request.appEnvironment = AppEnvironment.NONPROD
            elif requirements["environment"] == "PROD":
                vm_request.appEnvironment = AppEnvironment.PROD
        
        if "os" in requirements:
            try:
                vm_request.os = OS(requirements["os"])
            except ValueError:
                pass
        
        if "use_type" in requirements:
            try:
                vm_request.useType = UseType(requirements["use_type"])
            except ValueError:
                pass
        
        if "machine_type" in requirements:
            try:
                vm_request.machineType = MachineType(requirements["machine_type"])
            except ValueError:
                pass
        
        if "zone" in requirements:
            vm_request.zone = requirements["zone"]
        
        if "line_of_business" in requirements:
            vm_request.lineOfBusiness = requirements.get("line_of_business")
        
        # Determine next agent based on provider
        if provider == "gcp":
            next_agent = "gce_specialist"
        elif provider == "azure":
            next_agent = "azure_specialist"
        elif provider == "aws":
            next_agent = "ec2_specialist"
        else:
            # Need to determine provider
            next_agent = "clarification"
        
        return {
            "next_agent": next_agent,
            "vm_request": vm_request,
            "provider": provider,
            "needs_clarification": len(vm_request.get_missing_fields()) > 0,
            "missing_fields": vm_request.get_missing_fields()
        }
