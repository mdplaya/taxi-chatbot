from typing import Dict, Any
from models.taxi_models import VMRequest
import logging
import json

logger = logging.getLogger(__name__)

class GCESpecialistAgent:
    """Specialist agent for Google Cloud Platform Compute Engine instances"""
    
    def __init__(self, mcp_client=None):
        self.mcp = mcp_client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def create_instance(self, vm_request: VMRequest) -> Dict[str, Any]:
        """Create GCE instance via TAXI API"""
        
        self.logger.info("Creating GCE instance")
        
        # Validate all required fields are present
        missing = vm_request.get_missing_fields()
        if missing:
            return {
                "success": False,
                "error": f"Missing required fields: {missing}",
                "needs_clarification": True,
                "missing_fields": missing
            }
        
        # Build TAXI payload
        taxi_payload = vm_request.to_taxi_payload()
        
        self.logger.info(f"TAXI Payload: {json.dumps(taxi_payload, indent=2)}")
        
        # Call MCP server to execute TAXI API
        if self.mcp:
            try:
                result = await self.mcp.call_tool(
                    "mock_taxi_call",
                    taxi_payload
                )
            except Exception as e:
                self.logger.error(f"Error calling TAXI API: {e}")
                result = {
                    "success": False,
                    "error": str(e)
                }
        else:
            # Mock response for testing without MCP
            result = {
                "success": True,
                "job_id": "TAXI-MOCK-12345",
                "instance_id": "i-mockinstance-001",
                "status": "PROVISIONING",
                "message": f"Creating {taxi_payload['machineType']} in {taxi_payload['zone']}"
            }
        
        return {
            "success": result.get("success", False),
            "instance_id": result.get("instance_id"),
            "job_id": result.get("job_id"),
            "status": result.get("status"),
            "message": result.get("message"),
            "payload_sent": taxi_payload,
            "error": result.get("error")
        }
    
    async def validate_config(self, vm_request: VMRequest) -> Dict[str, Any]:
        """Validate GCE configuration before provisioning"""
        
        validations = []
        
        # Validate zone format
        if vm_request.zone and not vm_request.zone.startswith("us-"):
            validations.append({
                "field": "zone",
                "issue": "Zone should be a US region",
                "suggestion": "Use us-east4-a or us-central1-a"
            })
        
        # Validate cost center
        if vm_request.costCenter and not vm_request.costCenter.isdigit():
            validations.append({
                "field": "costCenter",
                "issue": "Cost center must be 5 digits",
                "suggestion": "Provide a valid 5-digit cost center code"
            })
        
        # Validate environment/subtype combination
        if vm_request.appEnvironment == "PROD" and vm_request.appEnvironmentSubtype:
            validations.append({
                "field": "appEnvironmentSubtype",
                "issue": "PROD environment should not have a subtype",
                "suggestion": "Remove appEnvironmentSubtype for PROD"
            })
        
        return {
            "valid": len(validations) == 0,
            "validations": validations
        }
