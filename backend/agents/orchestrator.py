from pydantic import BaseModel
from typing import Literal, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class UserIntent(BaseModel):
    """Analyzed user intent"""
    intent: Literal["create_compute", "create_database", "modify_resource", "delete_resource", "unclear"]
    provider: Optional[Literal["gcp", "azure", "aws", "onprem"]] = None
    resource_type: Optional[str] = None
    raw_requirements: str

def analyze_user_request(user_input: str) -> UserIntent:
    """
    Analyze user request and determine intent and cloud provider.
    
    Examples:
    - "I want a VM in GCP" -> intent: create_compute, provider: gcp
    - "Create a Linux server" -> intent: create_compute, provider: None
    - "Deploy a database" -> intent: create_database, provider: None
    - "Set up a virtual machine in Google Cloud" -> intent: create_compute, provider: gcp
    """
    user_input_lower = user_input.lower()
    
    # Detect cloud provider
    provider = None
    if any(term in user_input_lower for term in ['gcp', 'google cloud', 'gce', 'google compute']):
        provider = 'gcp'
    elif any(term in user_input_lower for term in ['azure', 'microsoft']):
        provider = 'azure'
    elif any(term in user_input_lower for term in ['aws', 'amazon', 'ec2']):
        provider = 'aws'
    
    # Detect intent - check specific actions first before resource creation
    intent = 'unclear'
    resource_type = None
    
    if any(term in user_input_lower for term in ['delete', 'remove', 'terminate', 'destroy']):
        intent = 'delete_resource'
    elif any(term in user_input_lower for term in ['modify', 'update', 'change', 'resize', 'scale']):
        intent = 'modify_resource'
    elif any(term in user_input_lower for term in ['vm', 'virtual machine', 'instance', 'server', 'compute']):
        intent = 'create_compute'
        resource_type = 'vm'
    elif any(term in user_input_lower for term in ['database', 'db', 'sql', 'postgres', 'mysql', 'mongodb']):
        intent = 'create_database'
        resource_type = 'database'
    
    return UserIntent(
        intent=intent,
        provider=provider,
        resource_type=resource_type,
        raw_requirements=user_input
    )

class OrchestratorAgent:
    """Routes requests to appropriate specialist agents"""
    
    def __init__(self, mcp_client=None):
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def process(self, user_input: str, session_id: str = None) -> Dict[str, Any]:
        """Process user request and route to appropriate agent"""
        
        self.logger.info(f"Processing request: {user_input}")
        
        # Analyze intent using Marvin
        try:
            intent = analyze_user_request(user_input)
            self.logger.info(f"Detected intent: {intent}")
        except Exception as e:
            self.logger.error(f"Error analyzing request: {e}")
            return {
                "next_agent": "clarification",
                "error": "Could not understand request",
                "context": {"raw_request": user_input}
            }
        
        # Route based on intent
        if intent.intent == "create_compute":
            return {
                "next_agent": "compute",
                "context": {
                    "provider": intent.provider,
                    "raw_request": user_input,
                    "session_id": session_id
                }
            }
        elif intent.intent == "create_database":
            return {
                "next_agent": "database",
                "context": {
                    "provider": intent.provider,
                    "raw_request": user_input,
                    "session_id": session_id
                }
            }
        else:
            return {
                "next_agent": "clarification",
                "context": {
                    "unclear_request": user_input,
                    "detected_intent": intent.intent,
                    "session_id": session_id
                }
            }
