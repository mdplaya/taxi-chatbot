from typing import List, Dict, Any, Optional
from models.taxi_models import VMRequest
import logging
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.llm_manager import llm_manager

try:
    import marvin
    MARVIN_AVAILABLE = True
except ImportError:
    MARVIN_AVAILABLE = False

logger = logging.getLogger(__name__)

def generate_template_question(field_name: str, context: str = "") -> str:
    """
    Generate a natural, conversational question for a missing field.
    
    Examples:
    - field_name: "zone", context: "GCP VM" -> "Which GCP zone would you like to deploy to (e.g., us-east4-a)?"
    - field_name: "os", context: "Linux server" -> "What operating system do you need? (RHEL8, RHEL9, Windows 2019, or Windows 2022)"
    - field_name: "costCenter", context: "retail app" -> "What's the 5-digit cost center code for this resource?"
    """
    # Direct implementation with question templates
    questions = {
        "zone": "Which GCP zone would you like to deploy to (e.g., us-east4-a)?",
        "os": "What operating system do you need? (LINUX_RHEL8, LINUX_RHEL9, WINDOWS_19, or WINDOWS_22)",
        "costCenter": "What's the 5-digit cost center code for this resource?",
        "appEnvironment": "Is this for a production or non-production environment? (PROD or NONPROD)",
        "appEnvironmentSubtype": "What environment subtype? (dev, qa, test, or perf)",
        "lineOfBusiness": "Which line of business is this for? (RETAIL, ISTS, or EDML)",
        "project": "What's the GCP project name?",
        "useType": "What will this VM be used for? (app or database)",
        "machineType": "What machine type do you need? (e.g., e2-small, n1-standard-1, n2-standard-2, c2-standard-4)",
        "id": "What's your email address?"
    }
    
    return questions.get(field_name, f"Please provide the {field_name}:")

# LLM-powered natural question generation
if MARVIN_AVAILABLE:
    @marvin.fn
    def generate_natural_questions_llm(missing_fields: List[str], context: str, conversation_history: list = None) -> List[Dict[str, str]]:
        """
        Generate natural, conversational questions for missing fields using AI.
        Consider the conversation context to create more relevant questions.
        
        Each question should:
        1. Be conversational and friendly
        2. Include helpful examples or hints
        3. Consider what the user has already told us
        4. Be clear about the expected format
        
        Return a list of dictionaries with 'field' and 'question' keys.
        
        Examples:
        missing_fields=["zone", "os"], context="I need a VM for testing our retail app"
        -> [
            {"field": "zone", "question": "Where would you like to deploy this test VM? We have zones like us-east4-a or us-central1-b available."},
            {"field": "os", "question": "What operating system should we use for your retail app testing? We support RHEL 8/9 and Windows Server 2019/2022."}
        ]
        """
        pass  # Marvin will handle the implementation
else:
    generate_natural_questions_llm = None

class ClarificationAgent:
    """Handles gathering missing information from users with LLM support"""
    
    def __init__(self, mcp_client=None):
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
        self.asked_fields = set()  # Track which fields we've asked about
        
        # Field descriptions for better questions
        self.field_descriptions = {
            "appEnvironment": "environment type (NONPROD or PROD)",
            "appEnvironmentSubtype": "environment subtype (dev, qa, test, or perf)",
            "lineOfBusiness": "line of business (RETAIL, ISTS, or EDML)",
            "costCenter": "5-digit cost center code",
            "project": "GCP project name",
            "zone": "GCP zone (e.g., us-east4-a)",
            "os": "operating system (LINUX_RHEL8, LINUX_RHEL9, WINDOWS_19, or WINDOWS_22)",
            "useType": "usage type (app or database)",
            "machineType": "machine type (e2-small, n1-standard-1, n2-standard-2, c2-standard-4, etc.)",
            "id": "your email address"
        }
    
    async def get_clarifications(self, vm_request: VMRequest, context: str = "", conversation_history: list = None) -> Dict[str, Any]:
        """Generate clarification questions for missing fields with LLM support"""
        
        missing_fields = vm_request.get_missing_fields()
        
        # Filter out fields we've already asked about
        new_missing_fields = [f for f in missing_fields if f not in self.asked_fields]
        
        if not new_missing_fields:
            if missing_fields:  # Still have missing fields but already asked
                return {
                    "complete": False,
                    "error": "Some required fields are still missing. Please provide all required information.",
                    "missing_fields": missing_fields
                }
            return {
                "complete": True,
                "vm_request": vm_request.dict(),
                "mode": llm_manager.get_mode()
            }
        
        self.logger.info(f"Missing fields: {new_missing_fields}")
        
        # Mark fields as asked
        self.asked_fields.update(new_missing_fields)
        
        # Determine which question generation method to use
        mode = llm_manager.get_mode()
        questions = []
        
        if mode == "online" and generate_natural_questions_llm:
            try:
                # Try LLM-powered natural question generation
                result = await llm_manager.call_with_timeout(
                    generate_natural_questions_llm,
                    new_missing_fields,
                    context,
                    conversation_history
                )
                if result:
                    questions = result
                    self.logger.info(f"LLM generated {len(questions)} natural questions")
            except Exception as e:
                self.logger.warning(f"LLM question generation failed: {e}")
        
        # Fallback to template questions if needed
        if not questions:
            for field in new_missing_fields:
                try:
                    # Generate template question
                    question = generate_template_question(field, context)
                    questions.append({
                        "field": field,
                        "question": question,
                        "description": self.field_descriptions.get(field, field)
                    })
                except Exception as e:
                    # Ultimate fallback
                    self.logger.warning(f"Error generating question for {field}: {e}")
                    questions.append({
                        "field": field,
                        "question": f"Please provide the {self.field_descriptions.get(field, field)}:",
                        "description": self.field_descriptions.get(field, field)
                    })
        
        return {
            "complete": False,
            "questions": questions,
            "current_state": vm_request.dict(),
            "missing_count": len(new_missing_fields),
            "mode": mode
        }
    
    async def process_answers(self, vm_request: VMRequest, answers: Dict[str, str]) -> VMRequest:
        """Update VM request with provided answers"""
        
        # Import enum classes for type conversion
        from models.taxi_models import (
            AppEnvironment, AppEnvironmentSubtype, LineOfBusiness, 
            OS, UseType, MachineType
        )
        
        for field, value in answers.items():
            if hasattr(vm_request, field) and value:
                try:
                    # Normalize case based on field type
                    # AppEnvironment: Convert to uppercase
                    if field == "appEnvironment":
                        value = value.upper()  # prod -> PROD
                    # LineOfBusiness: Convert to uppercase
                    elif field == "lineOfBusiness":
                        value = value.upper()  # retail -> RETAIL
                    # OS: Convert to uppercase with underscores
                    elif field == "os":
                        value = value.upper().replace("-", "_")  # linux-rhel8 -> LINUX_RHEL8
                    # MachineType: Keep lowercase with hyphens (new format)
                    elif field == "machineType":
                        value = value.lower()  # e2-small, n1-standard-1, etc.
                    # AppEnvironmentSubtype & UseType: Keep lowercase
                    elif field in ["appEnvironmentSubtype", "useType"]:
                        value = value.lower()  # QA -> qa, APP -> app
                    
                    # Handle enum conversions based on field name
                    if field == "appEnvironment":
                        setattr(vm_request, field, AppEnvironment(value))
                    elif field == "appEnvironmentSubtype":
                        setattr(vm_request, field, AppEnvironmentSubtype(value))
                    elif field == "lineOfBusiness":
                        setattr(vm_request, field, LineOfBusiness(value))
                    elif field == "os":
                        setattr(vm_request, field, OS(value))
                    elif field == "useType":
                        setattr(vm_request, field, UseType(value))
                    elif field == "machineType":
                        setattr(vm_request, field, MachineType(value))
                    else:
                        # String fields (costCenter, project, zone, id)
                        setattr(vm_request, field, value)
                    
                    self.logger.info(f"Updated {field} = {value}")
                except ValueError as e:
                    self.logger.error(f"Invalid value for {field}: {value} - {e}")
                    raise ValueError(f"Invalid value '{value}' for field '{field}'. Please check the allowed values.")
        
        return vm_request
