from typing import Dict, Any, Optional
from models.taxi_models import VMRequest, AppEnvironment, OS, UseType, MachineType
import logging

logger = logging.getLogger(__name__)

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
    import re
    
    user_input_lower = user_input.lower()
    requirements = {}
    
    # Environment detection
    if any(term in user_input_lower for term in ['prod', 'production']):
        requirements['environment'] = 'PROD'
    elif any(term in user_input_lower for term in ['dev', 'development', 'test', 'testing', 'nonprod', 'non-prod', 'staging']):
        requirements['environment'] = 'NONPROD'
    
    # OS detection
    if 'windows' in user_input_lower:
        if any(term in user_input for term in ['22', '2022']):
            requirements['os'] = 'WINDOWS_22'
        elif any(term in user_input for term in ['19', '2019']):
            requirements['os'] = 'WINDOWS_19'
        else:
            requirements['os'] = 'WINDOWS_22'  # Default to latest
    elif any(term in user_input_lower for term in ['linux', 'rhel', 'red hat']):
        if '9' in user_input:
            requirements['os'] = 'LINUX_RHEL9'
        elif '8' in user_input:
            requirements['os'] = 'LINUX_RHEL8'
        else:
            requirements['os'] = 'LINUX_RHEL8'  # Default to RHEL8
    elif 'ubuntu' in user_input_lower:
        requirements['os'] = 'LINUX_RHEL8'  # Map Ubuntu to RHEL for now
    
    # Use type detection
    if any(term in user_input_lower for term in ['database', 'db', 'sql', 'mysql', 'postgres', 'mongodb']):
        requirements['use_type'] = 'database'
    elif any(term in user_input_lower for term in ['app', 'application', 'web', 'api', 'service']):
        requirements['use_type'] = 'app'
    
    # Machine type detection
    if 'n1-standard' in user_input_lower:
        # Extract number if specified (e.g., n1-standard-2)
        match = re.search(r'n1-standard-(\d+)', user_input_lower)
        if match:
            requirements['machine_type'] = f'n1-STANDARD-{match.group(1)}'
        else:
            requirements['machine_type'] = 'n1-STANDARD-1'
    elif 'n2-standard' in user_input_lower:
        match = re.search(r'n2-standard-(\d+)', user_input_lower)
        if match:
            requirements['machine_type'] = f'n2-STANDARD-{match.group(1)}'
        else:
            requirements['machine_type'] = 'n2-STANDARD-1'
    elif 'e2-medium' in user_input_lower:
        requirements['machine_type'] = 'e2-MEDIUM'
    elif 'e2-small' in user_input_lower:
        requirements['machine_type'] = 'e2-SMALL'
    
    # Zone detection (regex for GCP zones)
    zone_pattern = r'(us|europe|asia|australia|southamerica|northamerica)-(central|east|west|south|north|northeast|southeast)\d+-[a-z]'
    zone_match = re.search(zone_pattern, user_input_lower)
    if zone_match:
        requirements['zone'] = zone_match.group()
    
    # Line of business detection
    if 'retail' in user_input_lower:
        requirements['line_of_business'] = 'RETAIL'
    elif 'ists' in user_input_lower:
        requirements['line_of_business'] = 'ISTS'
    elif 'edml' in user_input_lower:
        requirements['line_of_business'] = 'EDML'
    
    return requirements

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
