import marvin
from marvin import fn
from typing import List, Dict, Any, Optional
from models.taxi_models import VMRequest
import logging

logger = logging.getLogger(__name__)

@fn
def generate_natural_question(field_name: str, context: str) -> str:
    """
    Generate a natural, conversational question for a missing field.
    
    Examples:
    - field_name: "zone", context: "GCP VM" -> "Which GCP zone would you like to deploy to (e.g., us-east4-a)?"
    - field_name: "os", context: "Linux server" -> "What operating system do you need? (RHEL8, RHEL9, Windows 2019, or Windows 2022)"
    - field_name: "costCenter", context: "retail app" -> "What's the 5-digit cost center code for this resource?"
    """
    pass

class ClarificationAgent:
    """Handles gathering missing information from users"""
    
    def __init__(self, mcp_client=None):
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
        
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
            "machineType": "machine type (n1-STANDARD-1, n2-STANDARD-1, etc.)",
            "id": "your email address"
        }
    
    async def get_clarifications(self, vm_request: VMRequest, context: str = "") -> Dict[str, Any]:
        """Generate clarification questions for missing fields"""
        
        missing_fields = vm_request.get_missing_fields()
        
        if not missing_fields:
            return {
                "complete": True,
                "vm_request": vm_request.dict()
            }
        
        self.logger.info(f"Missing fields: {missing_fields}")
        
        # Generate questions for each missing field
        questions = []
        for field in missing_fields:
            try:
                # Use Marvin to generate natural question
                question = generate_natural_question(field, context)
                questions.append({
                    "field": field,
                    "question": question,
                    "description": self.field_descriptions.get(field, field)
                })
            except Exception as e:
                # Fallback to template question
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
            "missing_count": len(missing_fields)
        }
    
    async def process_answers(self, vm_request: VMRequest, answers: Dict[str, str]) -> VMRequest:
        """Update VM request with provided answers"""
        
        for field, value in answers.items():
            if hasattr(vm_request, field):
                setattr(vm_request, field, value)
                self.logger.info(f"Updated {field} = {value}")
        
        return vm_request
