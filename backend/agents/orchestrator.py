from pydantic import BaseModel
from typing import Literal, Optional, Dict, Any
import logging
import asyncio
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

class UserIntent(BaseModel):
    """Analyzed user intent"""
    intent: Literal["create_compute", "create_database", "modify_resource", "delete_resource", "unclear"]
    provider: Optional[Literal["gcp", "azure", "aws", "onprem"]] = None
    resource_type: Optional[str] = None
    raw_requirements: str

def analyze_user_request_pattern(user_input: str) -> UserIntent:
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
    
    # Enhanced pattern matching with more keywords and partial matches
    intent = 'unclear'
    resource_type = None
    confidence = 0.0
    
    # Count matching keywords for confidence scoring
    delete_keywords = ['delete', 'remove', 'terminate', 'destroy', 'kill', 'stop']
    modify_keywords = ['modify', 'update', 'change', 'resize', 'scale', 'edit', 'adjust']
    compute_keywords = ['vm', 'virtual machine', 'instance', 'server', 'compute', 'ec2', 'gce', 'machine']
    database_keywords = ['database', 'db', 'sql', 'postgres', 'mysql', 'mongodb', 'rds', 'datastore']
    
    delete_matches = sum(1 for term in delete_keywords if term in user_input_lower)
    modify_matches = sum(1 for term in modify_keywords if term in user_input_lower)
    compute_matches = sum(1 for term in compute_keywords if term in user_input_lower)
    database_matches = sum(1 for term in database_keywords if term in user_input_lower)
    
    # Determine intent based on matches
    if delete_matches > 0:
        intent = 'delete_resource'
        confidence = min(1.0, delete_matches * 0.5)
    elif modify_matches > 0:
        intent = 'modify_resource'
        confidence = min(1.0, modify_matches * 0.5)
    elif compute_matches > 0:
        intent = 'create_compute'
        resource_type = 'vm'
        confidence = min(1.0, compute_matches * 0.3)
    elif database_matches > 0:
        intent = 'create_database'
        resource_type = 'database'
        confidence = min(1.0, database_matches * 0.3)
    
    # Additional context clues
    if any(term in user_input_lower for term in ['create', 'deploy', 'provision', 'launch', 'spin up', 'set up', 'want', 'need']):
        confidence = min(1.0, confidence + 0.2)
    
    return UserIntent(
        intent=intent,
        provider=provider,
        resource_type=resource_type,
        raw_requirements=user_input
    )

# LLM-powered intent analysis function
if MARVIN_AVAILABLE:
    @marvin.fn
    def analyze_user_request_llm(user_input: str) -> UserIntent:
        """
        Analyze user request using AI to determine intent and cloud provider.
        
        This function should:
        1. Identify if the user wants to create, modify, or delete a resource
        2. Determine the type of resource (compute/VM, database, etc.)
        3. Identify the cloud provider if mentioned (GCP, AWS, Azure)
        4. Handle natural language variations and context
        
        Examples:
        - "I want a VM in GCP" -> intent: create_compute, provider: gcp
        - "Spin up a Linux server on Google Cloud" -> intent: create_compute, provider: gcp
        - "Need a database for my app" -> intent: create_database, provider: None
        - "Delete the VM we created yesterday" -> intent: delete_resource
        - "Can you help me set up a virtual machine?" -> intent: create_compute
        """
        pass  # Marvin will handle the implementation
else:
    analyze_user_request_llm = None

class OrchestratorAgent:
    """Routes requests to appropriate specialist agents with LLM support"""
    
    def __init__(self, mcp_client=None):
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
        self.conversation_history = []
        
    async def process(self, user_input: str, session_id: str = None) -> Dict[str, Any]:
        """Process user request and route to appropriate agent"""
        
        self.logger.info(f"Processing request: {user_input}")
        
        # Store in conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # Determine which analysis function to use
        mode = llm_manager.get_mode()
        intent = None
        
        try:
            if mode == "online" and analyze_user_request_llm:
                # Try LLM analysis with timeout
                result = await llm_manager.call_with_timeout(
                    analyze_user_request_llm, 
                    user_input
                )
                if result:
                    intent = result
                    self.logger.info(f"LLM detected intent: {intent}")
                else:
                    # Fallback to pattern matching if LLM fails
                    intent = analyze_user_request_pattern(user_input)
                    self.logger.info(f"Fallback to pattern matching: {intent}")
            else:
                # Use pattern matching
                intent = analyze_user_request_pattern(user_input)
                self.logger.info(f"Pattern detected intent: {intent}")
                
        except Exception as e:
            self.logger.error(f"Error analyzing request: {e}")
            # Fallback to pattern matching
            try:
                intent = analyze_user_request_pattern(user_input)
            except Exception as e2:
                self.logger.error(f"Pattern matching also failed: {e2}")
                return {
                    "next_agent": "clarification",
                    "error": "Could not understand request",
                    "context": {"raw_request": user_input},
                    "mode": mode
                }
        
        # Route based on intent
        if intent.intent == "create_compute":
            return {
                "next_agent": "compute",
                "context": {
                    "provider": intent.provider,
                    "raw_request": user_input,
                    "session_id": session_id,
                    "conversation_history": self.conversation_history
                },
                "mode": mode
            }
        elif intent.intent == "create_database":
            return {
                "next_agent": "database",
                "context": {
                    "provider": intent.provider,
                    "raw_request": user_input,
                    "session_id": session_id,
                    "conversation_history": self.conversation_history
                },
                "mode": mode
            }
        else:
            return {
                "next_agent": "clarification",
                "context": {
                    "unclear_request": user_input,
                    "detected_intent": intent.intent,
                    "session_id": session_id,
                    "conversation_history": self.conversation_history
                },
                "mode": mode
            }
