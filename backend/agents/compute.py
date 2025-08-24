from typing import Dict, Any, Optional
from models.taxi_models import VMRequest, AppEnvironment, OS, UseType, MachineType, LineOfBusiness, AppEnvironmentSubtype
import logging
import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.llm_manager import llm_manager

try:
    import marvin
    MARVIN_AVAILABLE = True
except ImportError:
    MARVIN_AVAILABLE = False

logger = logging.getLogger(__name__)

def extract_vm_requirements_pattern(user_input: str) -> Dict[str, Any]:
    """
    Enhanced pattern matching for VM requirement extraction.
    Handles fuzzy matching, partial matches, and common variations.
    
    Return a dictionary with any identifiable fields:
    - environment: NONPROD or PROD
    - os: LINUX_RHEL8, LINUX_RHEL9, WINDOWS_19, WINDOWS_22
    - use_type: app or database
    - machine_type: Various GCP machine types
    - zone: GCP zone like us-east4-a
    - line_of_business: RETAIL, ISTS, or EDML
    
    Example:
    "I need a RHEL 8 VM for our retail app in development" ->
    {
        "os": "LINUX_RHEL8",
        "use_type": "app",
        "environment": "NONPROD",
        "line_of_business": "RETAIL"
    }
    """
    import re
    
    user_input_lower = user_input.lower()
    # Also create a normalized version without spaces/dashes for fuzzy matching
    user_input_normalized = re.sub(r'[\s\-_]', '', user_input_lower)
    requirements = {}
    confidence_scores = {}
    
    # Environment detection
    if any(term in user_input_lower for term in ['prod', 'production']):
        requirements['environment'] = 'PROD'
        confidence_scores['environment'] = 0.9
    elif any(term in user_input_lower for term in ['dev', 'development', 'test', 'testing', 'nonprod', 'non-prod', 'staging', 'qa', 'perf']):
        requirements['environment'] = 'NONPROD'
        confidence_scores['environment'] = 0.9
    
    # Environment subtype detection for NONPROD - check more specific patterns first
    if requirements.get('environment') == 'NONPROD':
        if 'perf' in user_input_lower:  # Check 'perf' before 'test' to avoid confusion with 'performance testing'
            requirements['environment_subtype'] = 'perf'
        elif any(term in user_input_lower for term in ['dev', 'development']):
            requirements['environment_subtype'] = 'dev'
        elif 'qa' in user_input_lower:
            requirements['environment_subtype'] = 'qa'
        elif any(term in user_input_lower for term in ['test', 'testing']):
            requirements['environment_subtype'] = 'test'
    
    # Enhanced OS detection with fuzzy matching for RHEL variations
    # Handle "RHEL 8", "RHEL8", "rhel-8", "RHEL 8.x", etc.
    rhel8_patterns = [
        r'rhel\s*8', r'rhel-8', r'rhel_8', r'rhel8',
        r'red\s*hat\s*8', r'redhat\s*8', r'red\s*hat\s*enterprise\s*linux\s*8'
    ]
    rhel9_patterns = [
        r'rhel\s*9', r'rhel-9', r'rhel_9', r'rhel9',
        r'red\s*hat\s*9', r'redhat\s*9', r'red\s*hat\s*enterprise\s*linux\s*9'
    ]
    
    if any(re.search(pattern, user_input_lower) for pattern in rhel8_patterns):
        requirements['os'] = 'LINUX_RHEL8'
        confidence_scores['os'] = 0.95
    elif any(re.search(pattern, user_input_lower) for pattern in rhel9_patterns):
        requirements['os'] = 'LINUX_RHEL9'
        confidence_scores['os'] = 0.95
    elif 'windows' in user_input_lower:
        if any(term in user_input for term in ['22', '2022', 'server 2022']):
            requirements['os'] = 'WINDOWS_22'
            confidence_scores['os'] = 0.95
        elif any(term in user_input for term in ['19', '2019', 'server 2019']):
            requirements['os'] = 'WINDOWS_19'
            confidence_scores['os'] = 0.95
        else:
            requirements['os'] = 'WINDOWS_22'  # Default to latest
            confidence_scores['os'] = 0.7
    elif any(term in user_input_lower for term in ['linux', 'ubuntu', 'centos', 'debian']):
        requirements['os'] = 'LINUX_RHEL8'  # Default Linux to RHEL8
        confidence_scores['os'] = 0.6
    
    # Use type detection
    if any(term in user_input_lower for term in ['database', 'db', 'sql', 'mysql', 'postgres', 'mongodb', 'oracle', 'data store']):
        requirements['use_type'] = 'database'
        confidence_scores['use_type'] = 0.9
    elif any(term in user_input_lower for term in ['app', 'application', 'web', 'api', 'service', 'microservice', 'server']):
        requirements['use_type'] = 'app'
        confidence_scores['use_type'] = 0.9
    
    # Enhanced Machine type detection with all new types and partial matching
    machine_type_mappings = {
        # E2 Series (Cost Optimized)
        'e2-micro': ['e2-micro', 'e2micro', 'micro'],
        'e2-small': ['e2-small', 'e2small', 'small'],
        'e2-medium': ['e2-medium', 'e2medium', 'medium'],
        'e2-standard-2': ['e2-standard-2', 'e2standard2'],
        'e2-standard-4': ['e2-standard-4', 'e2standard4'],
        'e2-standard-8': ['e2-standard-8', 'e2standard8'],
        
        # N1 Series (Previous Gen) - Specific types first, then partial match
        'n1-standard-8': ['n1-standard-8', 'n1standard8'],
        'n1-standard-4': ['n1-standard-4', 'n1standard4'],
        'n1-standard-2': ['n1-standard-2', 'n1standard2'],
        'n1-standard-1': ['n1-standard-1', 'n1standard1'],  # Removed 'n1' from here - will handle separately
        
        # N2 Series (Balanced)
        'n2-standard-2': ['n2-standard-2', 'n2standard2'],
        'n2-standard-4': ['n2-standard-4', 'n2standard4'],
        'n2-standard-8': ['n2-standard-8', 'n2standard8'],
        'n2-highmem-2': ['n2-highmem-2', 'n2highmem2', 'n2-high-memory-2'],
        'n2-highmem-4': ['n2-highmem-4', 'n2highmem4', 'n2-high-memory-4'],
        
        # C2 Series (Compute Optimized)
        'c2-standard-4': ['c2-standard-4', 'c2standard4'],
        'c2-standard-8': ['c2-standard-8', 'c2standard8'],
    }
    
    # Check for machine type matches - check longer patterns first
    machine_type_found = False
    # Sort patterns by length (descending) to match longer patterns first
    sorted_items = sorted(machine_type_mappings.items(), 
                         key=lambda x: max(len(p) for p in x[1]) if x[1] else 0, 
                         reverse=True)
    
    for machine_type, patterns in sorted_items:
        for pattern in patterns:
            # Check both normal and normalized versions
            if pattern in user_input_lower or pattern.replace('-', '') in user_input_normalized:
                requirements['machine_type'] = machine_type
                confidence_scores['machine_type'] = 0.9
                machine_type_found = True
                break
        if machine_type_found:
            break
    
    # Handle "n1" alone as a special case - only if no specific n1 type was found
    if not machine_type_found:
        # Check for standalone "n1" (with word boundaries)
        if re.search(r'\bn1\b', user_input_lower) and 'n1-' not in user_input_lower:
            requirements['machine_type'] = 'n1-standard-1'
            confidence_scores['machine_type'] = 0.7  # Lower confidence for partial match
            machine_type_found = True
    
    # Handle descriptive machine type requests
    if not machine_type_found:
        # Also handle hyphenated variations
        if any(term in user_input_lower for term in ['cost-optimized', 'cost optimized', 'cheap', 'budget', 'economical']):
            requirements['machine_type'] = 'e2-small'
            confidence_scores['machine_type'] = 0.6
        elif any(term in user_input_lower for term in ['compute-optimized', 'compute optimized', 'high compute', 'cpu intensive']):
            requirements['machine_type'] = 'c2-standard-4'
            confidence_scores['machine_type'] = 0.6
        elif any(term in user_input_lower for term in ['high memory', 'memory intensive', 'ram intensive']):
            requirements['machine_type'] = 'n2-highmem-4'
            confidence_scores['machine_type'] = 0.6
        elif any(term in user_input_lower for term in ['balanced', 'general purpose']):
            requirements['machine_type'] = 'n2-standard-2'
            confidence_scores['machine_type'] = 0.6
    
    # Zone detection (regex for GCP zones)
    zone_pattern = r'(us|europe|asia|australia|southamerica|northamerica)-(central|east|west|south|north|northeast|southeast)\d+-[a-z]'
    zone_match = re.search(zone_pattern, user_input_lower)
    if zone_match:
        requirements['zone'] = zone_match.group()
        confidence_scores['zone'] = 0.95
    
    # Line of business detection
    if 'retail' in user_input_lower:
        requirements['line_of_business'] = 'RETAIL'
        confidence_scores['line_of_business'] = 0.9
    elif 'ists' in user_input_lower:
        requirements['line_of_business'] = 'ISTS'
        confidence_scores['line_of_business'] = 0.9
    elif 'edml' in user_input_lower:
        requirements['line_of_business'] = 'EDML'
        confidence_scores['line_of_business'] = 0.9
    
    # Add overall confidence score
    if confidence_scores:
        requirements['_confidence'] = sum(confidence_scores.values()) / len(confidence_scores)
    
    return requirements

# LLM-powered requirement extraction
if MARVIN_AVAILABLE:
    @marvin.fn
    def extract_vm_requirements_llm(user_input: str, conversation_history: list = None) -> Dict[str, Any]:
        """
        Use AI to extract VM requirements from natural language, considering conversation context.
        
        This function should extract:
        - environment: NONPROD or PROD
        - environment_subtype: dev, qa, test, or perf (if NONPROD)
        - os: Operating system (LINUX_RHEL8, LINUX_RHEL9, WINDOWS_19, WINDOWS_22)
        - use_type: app or database
        - machine_type: GCP machine type (e2-micro, n1-standard-1, etc.)
        - zone: GCP zone (us-east4-a, etc.)
        - line_of_business: RETAIL, ISTS, or EDML
        - cost_center: 5-digit cost center if mentioned
        - project: GCP project name if mentioned
        - id: Email address if mentioned
        
        Consider the conversation history for context.
        
        Examples:
        "I need a RHEL 8 VM" -> {"os": "LINUX_RHEL8"}
        "Create a VM with RHEL8" -> {"os": "LINUX_RHEL8"}
        "I want an n1 machine" -> {"machine_type": "n1-standard-1"}
        "Deploy an n1-standard-1 instance" -> {"machine_type": "n1-standard-1"}
        "Set up n1 VM" -> {"machine_type": "n1-standard-1"}
        "Need a cost-optimized VM for testing" -> {"machine_type": "e2-small", "environment": "NONPROD", "environment_subtype": "test"}
        """
        pass  # Marvin will handle the implementation
else:
    extract_vm_requirements_llm = None

class ComputeAgent:
    """Handles compute resource requests across all cloud providers with LLM support"""
    
    def __init__(self, mcp_client=None):
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
        self.progress_callback = None
    
    async def emit_progress(self, step: str, message: str, percentage: int = None):
        """Emit progress update if callback is set"""
        if self.progress_callback:
            try:
                await self.progress_callback("Compute", step, message, percentage)
            except Exception as e:
                self.logger.error(f"Error emitting progress: {e}")
    
    async def process(self, context: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
        """Process compute request and extract requirements"""
        
        # Set progress callback if provided
        if progress_callback:
            self.progress_callback = progress_callback
            await self.emit_progress("extracting", "Extracting VM requirements...", 10)
        
        provider = context.get("provider")
        raw_request = context.get("raw_request", "")
        conversation_history = context.get("conversation_history", [])
        
        self.logger.info(f"Processing compute request for provider: {provider}")
        
        if progress_callback:
            await self.emit_progress("detecting_provider", "Detecting cloud provider...", 30)
        
        # Determine which extraction method to use
        mode = llm_manager.get_mode()
        requirements = {}
        
        try:
            if mode == "online" and extract_vm_requirements_llm:
                if progress_callback:
                    await self.emit_progress("analyzing", "Analyzing requirements with AI...", 50)
                
                # Try LLM extraction with timeout
                result = await llm_manager.call_with_timeout(
                    extract_vm_requirements_llm,
                    raw_request,
                    conversation_history
                )
                if result:
                    requirements = result
                    self.logger.info(f"LLM extracted requirements: {requirements}")
                else:
                    # Fallback to pattern matching
                    requirements = extract_vm_requirements_pattern(raw_request)
                    self.logger.info(f"Fallback pattern extracted: {requirements}")
            else:
                # Use pattern matching
                requirements = extract_vm_requirements_pattern(raw_request)
                self.logger.info(f"Pattern extracted requirements: {requirements}")
                
        except Exception as e:
            self.logger.error(f"Error extracting requirements: {e}")
            # Fallback to pattern matching
            try:
                requirements = extract_vm_requirements_pattern(raw_request)
            except Exception as e2:
                self.logger.error(f"Pattern extraction also failed: {e2}")
                requirements = {}
        
        # Remove internal confidence score before mapping
        confidence = requirements.pop('_confidence', 0.0)
        
        # Create VMRequest with extracted data
        vm_request = VMRequest()
        
        # Map extracted requirements to VMRequest fields
        if "environment" in requirements:
            if requirements["environment"] == "NONPROD":
                vm_request.appEnvironment = AppEnvironment.NONPROD
            elif requirements["environment"] == "PROD":
                vm_request.appEnvironment = AppEnvironment.PROD
        
        if "environment_subtype" in requirements and vm_request.appEnvironment == AppEnvironment.NONPROD:
            try:
                vm_request.appEnvironmentSubtype = AppEnvironmentSubtype(requirements["environment_subtype"])
            except ValueError:
                pass
        
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
                # Try to find the enum value that matches
                for mt in MachineType:
                    if mt.value == requirements["machine_type"]:
                        vm_request.machineType = mt
                        break
        
        if "zone" in requirements:
            vm_request.zone = requirements["zone"]
        
        if "line_of_business" in requirements:
            try:
                vm_request.lineOfBusiness = LineOfBusiness(requirements["line_of_business"])
            except ValueError:
                pass
        
        if "cost_center" in requirements:
            vm_request.costCenter = requirements["cost_center"]
        
        if "project" in requirements:
            vm_request.project = requirements["project"]
        
        if "id" in requirements:
            vm_request.id = requirements["id"]
        
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
            "missing_fields": vm_request.get_missing_fields(),
            "extraction_confidence": confidence,
            "mode": mode
        }