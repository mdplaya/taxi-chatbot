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
from utils.learning import Pattern, PatternType
import os
import httpx

logger = logging.getLogger(__name__)


class ComputeAgent(BaseAgent):
    """
    Routes compute requests to appropriate specialist agents
    Pure LLM routing - NO field extraction, NO pattern matching
    """
    
    def __init__(self, mcp_client=None):
        super().__init__(
            name="ComputeAgent",
            goal="Route compute requests to appropriate cloud specialist agents",
            model="gpt-5-mini"
        )
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
        # Use environment variable or default to mcp-server hostname
        import os
        self.mcp_url = os.getenv("MCP_SERVER_URL", "http://mcp-server:8001")
        self._available_specialists = None  # Cache
        
        # Available compute specialists
        self.compute_specialists = {
            "gce_specialist": "Google Cloud VMs/instances",
            "gke_specialist": "Google Kubernetes Engine",
            "ec2_specialist": "AWS EC2 instances",
            "eks_specialist": "AWS Kubernetes",
            "azure_vm_specialist": "Azure Virtual Machines",
            "aks_specialist": "Azure Kubernetes Service"
        }
    
    async def _get_available_specialists(self) -> List[Dict[str, Any]]:
        """Get list of available specialists from MCP server"""
        if self._available_specialists is not None:
            return self._available_specialists
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.mcp_url}/specialists")
                if response.status_code == 200:
                    data = response.json()
                    self._available_specialists = data.get("specialists", [])
                    return self._available_specialists
        except Exception as e:
            self.logger.warning(f"Failed to get specialists from MCP: {e}")
        
        # Fallback if MCP is unavailable
        return [
            {"name": "gce_specialist", "cloud": "gcp", "available": True}
        ]
        
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Define available tools for compute routing"""
        return [
            {
                "name": "detect_compute_type",
                "description": "Detect compute type and cloud provider",
                "parameters": ["user_input", "context"]
            },
            {
                "name": "route_to_specialist",
                "description": "Route to appropriate compute specialist",
                "parameters": ["specialist_name", "context"]
            },
            {
                "name": "apply_corrections",
                "description": "Apply intelligent corrections for typos and variations",
                "parameters": ["user_input"]
            }
        ]
    
    async def reflect_on_extraction(self,
                                   raw_input: str,
                                   extracted_data: Dict,
                                   corrections: Dict) -> Dict[str, Any]:
        """
        Specialized reflection for requirement extraction.
        Analyzes extraction accuracy and learns new patterns.
        """
        reflection_prompt = f"""
        Analyze this extraction:
        
        Raw input: {raw_input}
        Extracted data: {json.dumps(extracted_data, default=str)}
        Corrections made: {json.dumps(corrections, default=str)}
        
        Evaluate:
        1. What was extracted correctly?
        2. What was missed or extracted incorrectly?
        3. What new extraction patterns should be learned?
        4. How can extraction confidence be improved?
        5. Any ambiguous terms that need clarification?
        
        Return JSON:
        {{
            "extraction_accuracy": {{
                "correct_fields": [],
                "incorrect_fields": [],
                "missed_fields": [],
                "accuracy_score": 0.0-1.0
            }},
            "new_patterns": [
                {{
                    "pattern": "description",
                    "example": "input example",
                    "extracts_to": {{"field": "value"}}
                }}
            ],
            "confidence_adjustments": {{
                "field_name": adjustment_value
            }},
            "ambiguous_terms": [],
            "lessons": []
        }}
        """
        
        analysis = self._llm_reason(reflection_prompt)
        
        # Learn new extraction patterns
        if analysis.get("new_patterns"):
            for new_pattern in analysis["new_patterns"]:
                pattern = Pattern(
                    type=PatternType.SEQUENCE,
                    description=f"Extraction pattern: {new_pattern['pattern']}",
                    occurrences=1,
                    confidence=0.7,
                    metadata={
                        "example": new_pattern.get("example"),
                        "extracts_to": new_pattern.get("extracts_to")
                    }
                )
                
                if self.learning_engine:
                    await self.share_learning(pattern, pattern.confidence)
        
        # Adjust field extraction confidence
        if analysis.get("confidence_adjustments"):
            for field, adjustment in analysis["confidence_adjustments"].items():
                current = self.memory.long_term.get(f"extraction_confidence_{field}", 0.6)
                new_confidence = min(1.0, max(0.3, current + adjustment))
                self.memory.long_term[f"extraction_confidence_{field}"] = new_confidence
        
        return analysis
    
    async def learn_cloud_patterns(self,
                                  user_input: str,
                                  detected_cloud: str,
                                  was_correct: bool) -> Dict[str, Any]:
        """
        Learn cloud provider detection patterns.
        Builds provider-specific terminology knowledge.
        """
        learning_prompt = f"""
        Learn from this cloud detection:
        
        User input: {user_input}
        Detected: {detected_cloud}
        Was correct: {was_correct}
        
        Identify:
        1. Provider-specific terminology used
        2. Key indicators for each cloud provider
        3. Ambiguous terms that could mean multiple providers
        4. Common user phrases for each provider
        5. Detection confidence factors
        
        Return JSON:
        {{
            "provider_indicators": {{
                "gcp": [],
                "aws": [],
                "azure": []
            }},
            "ambiguous_terms": [
                {{
                    "term": "term",
                    "could_mean": ["provider1", "provider2"],
                    "disambiguation": "how to clarify"
                }}
            ],
            "common_phrases": {{
                "provider": ["phrase1", "phrase2"]
            }},
            "confidence_factors": {{
                "high_confidence": [],
                "low_confidence": []
            }}
        }}
        """
        
        analysis = self._llm_reason(learning_prompt)
        
        # Build cloud detection confidence model
        if was_correct:
            # Reinforce successful detection patterns
            pattern = Pattern(
                type=PatternType.SUCCESS,
                description=f"Cloud detection: '{user_input}' -> {detected_cloud}",
                occurrences=1,
                confidence=0.9,
                metadata=analysis
            )
        else:
            # Learn from incorrect detection
            pattern = Pattern(
                type=PatternType.ERROR,
                description=f"Incorrect cloud detection: avoid '{user_input}' -> {detected_cloud}",
                occurrences=1,
                confidence=0.8,
                metadata=analysis
            )
        
        if self.learning_engine:
            await self.share_learning(pattern, pattern.confidence)
        
        # Store provider-specific indicators
        for provider, indicators in analysis.get("provider_indicators", {}).items():
            if indicators:
                self.memory.long_term[f"cloud_indicators_{provider}"] = indicators
        
        # Track ambiguous cases for future clarification
        if analysis.get("ambiguous_terms"):
            self.memory.long_term["ambiguous_cloud_terms"] = analysis["ambiguous_terms"]
        
        return analysis
    
    def execute_action(self, action: Action) -> Any:
        """Execute the chosen action"""
        if action.name == "detect_compute_type":
            return self._detect_compute_type(
                action.parameters.get("user_input", ""),
                action.parameters.get("context", {})
            )
        elif action.name == "route_to_specialist":
            return {
                "specialist": action.parameters.get("specialist_name"),
                "context": action.parameters.get("context")
            }
        elif action.name == "apply_corrections":
            return self._apply_corrections(
                action.parameters.get("user_input", "")
            )
        else:
            logger.warning(f"Unknown action: {action.name}")
            return None
    
    async def _detect_compute_type(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect compute type and provider using LLM with MCP discovery
        """
        # Get available specialists
        specialists = await self._get_available_specialists()
        
        # Build specialist info for prompt
        specialist_info = []
        for spec in specialists:
            status = "AVAILABLE" if spec.get("available") else "NOT IMPLEMENTED"
            specialist_info.append(
                f"- {spec['name']} (handles {spec.get('cloud', 'unknown').upper()} {spec.get('resource_type', 'compute')}) - {status}"
            )
        
        routing_prompt = f"""
        Route this compute request to the appropriate specialist.
        
        User request: {user_input}
        Context from orchestrator: {json.dumps(context.get('extracted_requirements', {}), default=str)}
        
        Available specialists:
        {chr(10).join(specialist_info)}
        
        Apply intelligent routing:
        - If user mentions AWS/EC2/Amazon → route to ec2_specialist
        - If user mentions Azure/Microsoft → route to azure_vm_specialist  
        - If user mentions GCP/Google/GCE → route to gce_specialist
        - If unclear but looks like VM request and only one specialist is available → route there
        - If unclear and multiple available → ask for clarification
        
        Return JSON:
        {{
            "specialist": "specialist_name",
            "reasoning": "why this specialist",
            "detected_provider": "gcp/aws/azure/unclear", 
            "is_available": true/false,
            "confidence": 0.0-1.0
        }}
        """
        
        result = self._llm_reason(routing_prompt)
        
        # Verify specialist availability
        if result.get("specialist"):
            spec_name = result["specialist"]
            available_spec = next((s for s in specialists if s["name"] == spec_name), None)
            if available_spec:
                result["is_available"] = available_spec.get("available", False)
            else:
                result["is_available"] = False
                
        return result
    
    def _apply_corrections(self, user_input: str) -> str:
        """
        Apply intelligent corrections for common typos and variations
        Returns corrected input
        """
        corrections_prompt = f"""
        Apply intelligent corrections to this compute request:
        {user_input}
        
        Common corrections:
        - "red hat 8" or "rhel 8" → "RHEL8"
        - "windows 2022" or "win22" → "Windows Server 2022"
        - "k8s" → "Kubernetes"
        - "vm" → "virtual machine"
        - Fix obvious typos
        
        Return JSON:
        {{
            "corrected_input": "corrected text",
            "corrections_applied": ["list of corrections"],
            "confidence": 0.0-1.0
        }}
        """
        
        result = self._llm_reason(corrections_prompt)
        return result.get("corrected_input", user_input)
    
    async def process(self, context: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
        """
        Route compute request to appropriate specialist
        Pure LLM routing - NO extraction, NO pattern matching
        """
        # Set progress callback if provided
        if progress_callback:
            self.progress_callback = progress_callback
        
        raw_request = context.get("raw_request", "")
        
        self.logger.info(f"[ComputeAgent] Routing compute request: {raw_request[:100]}...")
        
        # Clear reasoning chain for new process
        self.reasoning_chain = []
        self.total_steps = 3
        self.current_step = 0
        
        # Step 1: Detect compute type and cloud provider
        self.current_step += 1
        await self.emit_progress("detecting", "Detecting compute type and provider", 33)
        
        routing_decision = await self._detect_compute_type(raw_request, context)
        
        # Check if specialist is available
        if routing_decision.get("specialist") and not routing_decision.get("is_available", True):
            specialist_name = routing_decision.get("specialist")
            return {
                "next_agent": "unavailable",
                "specialist_name": specialist_name,
                "context": context,
                "routing_metadata": routing_decision,
                "mode": "llm_routing"
            }
        
        # Step 2: Apply corrections if needed
        self.current_step += 1
        await self.emit_progress("routing", f"Routing to {routing_decision.get('specialist', 'specialist')}", 66)
        
        # Step 3: Complete routing
        self.current_step += 1
        specialist = routing_decision.get("specialist")
        
        if not specialist or specialist == "unclear":
            specialist = "clarification"
            self.logger.info("[ComputeAgent] Routing to clarification for unclear request")
        
        await self.emit_progress("complete", f"Routing complete - sending to {specialist}", 100)
        
        # Store routing decision in memory
        self.memory.short_term.append({
            "request": raw_request,
            "routed_to": specialist,
            "reasoning": routing_decision.get("reasoning"),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "next_agent": specialist,
            "context": context,  # Pass full context to specialist
            "routing_metadata": routing_decision,
            "mode": "llm_routing"  # Pure LLM routing
        }