# Implementation TODO: Fix Environment Inference with MCP Discovery

## Pre-Implementation Checklist
- [ ] Ensure you're on the `fix/environment-inference` branch
- [ ] Docker environment is running (`docker-compose up`)
- [ ] Read `FIX_ENVIRONMENT_INFERENCE_MCP_DISCOVERY.md` completely
- [ ] Backup current working state

## Phase 1: Add MCP Specialist Discovery Endpoint

### Task 1.1: Update MCP Server
**File**: `backend/mcp_server/server.py`

- [ ] Open the file
- [ ] Locate line 166 (after the `/tools` endpoint)
- [ ] Add the following new endpoint:

```python
@app.get("/specialists")
async def list_specialists():
    """List all specialists and their availability"""
    return {
        "specialists": [
            {
                "name": "gce_specialist",
                "cloud": "gcp",
                "resource_type": "compute",
                "available": True,
                "description": "Google Cloud Compute Engine VMs"
            },
            {
                "name": "ec2_specialist", 
                "cloud": "aws",
                "resource_type": "compute",
                "available": False,
                "description": "AWS EC2 instances"
            },
            {
                "name": "azure_vm_specialist",
                "cloud": "azure", 
                "resource_type": "compute",
                "available": False,
                "description": "Azure Virtual Machines"
            }
        ]
    }
```

- [ ] Save the file
- [ ] Restart MCP server container: `docker restart taxi-chatbot-mcp-server-1`
- [ ] Test the endpoint: `curl http://localhost:8001/specialists`
- [ ] Verify response shows all three specialists

## Phase 2: Update Compute Agent with MCP Discovery

### Task 2.1: Add Required Imports
**File**: `backend/agents/compute.py`

- [ ] Open the file
- [ ] At line 10 (in the imports section), add:
```python
import httpx
from typing import Optional, List
```

### Task 2.2: Add Specialist Discovery Methods
**File**: `backend/agents/compute.py`

- [ ] Locate the `__init__` method (around line 30)
- [ ] Replace the `__init__` method with:

```python
def __init__(self):
    super().__init__()
    self.mcp_url = "http://localhost:8001"
    self._available_specialists = None  # Cache
```

- [ ] After the `__init__` method, add:

```python
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
```

### Task 2.3: Update Routing Logic
**File**: `backend/agents/compute.py`

- [ ] Find the `_detect_compute_type` method (around line 235)
- [ ] Replace the ENTIRE method with:

```python
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
```

### Task 2.4: Remove Hardcoded GCP Default
**File**: `backend/agents/compute.py`

- [ ] Find lines 338-344 (in the `process` method)
- [ ] DELETE these lines completely:
```python
# Default to GCE if unclear but looks like VM request
if not specialist or specialist == "unclear":
    if any(kw in raw_request.lower() for kw in ['vm', 'server', 'instance', 'linux', 'windows']):
        specialist = "gce_specialist"
        self.logger.info("[ComputeAgent] Defaulting to gce_specialist for VM-like request")
    else:
        specialist = "clarification"
        self.logger.info("[ComputeAgent] Routing to clarification for unclear request")
```

- [ ] Replace with:
```python
if not specialist or specialist == "unclear":
    specialist = "clarification"
    self.logger.info("[ComputeAgent] Routing to clarification for unclear request")
```

### Task 2.5: Update process method to handle availability
**File**: `backend/agents/compute.py`

- [ ] In the `process` method, after line 327 (after `routing_decision = self._detect_compute_type(...)`), add:

```python
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
```

## Phase 3: Fix GCE Specialist Context Usage

### Task 3.1: Update Extraction Method
**File**: `backend/agents/gce_specialist.py`

- [ ] Find the `_extract_vm_requirements` method (line 150)
- [ ] Replace the first part of the method (up to the extraction_prompt) with:

```python
def _extract_vm_requirements(self, raw_request: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract VM requirements from raw request with intelligent corrections
    Focus on TAXI required fields only
    """
    # Get any previously extracted requirements from context
    extracted_requirements = context.get('extracted_requirements', {})
    
    extraction_prompt = f"""
    Extract GCE VM requirements from this request:
    {raw_request}
    
    Context from previous analysis (use as hints if relevant):
    {json.dumps(extracted_requirements, default=str)}
    
    Full context: {json.dumps(context, default=str)[:500]}
    
    IMPORTANT: If the context already contains extracted values (like appEnvironment, os, etc.), 
    use them unless the raw request explicitly contradicts them.
```

- [ ] Keep the rest of the prompt but ensure it includes the context usage instruction

### Task 3.2: Fix OS Defaults in GCE Specialist
**File**: `backend/agents/gce_specialist.py`

- [ ] In the extraction prompt (around line 186), find:
```python
- "server" alone without OS specified → LINUX_RHEL9
```

- [ ] REMOVE that line completely
- [ ] Add this line instead:
```python
- DO NOT default "server" alone to any OS
```

## Phase 4: Fix Orchestrator OS Default

### Task 4.1: Remove Incorrect Server Default
**File**: `backend/agents/orchestrator.py`

- [ ] Find lines 255-256:
```python
elif 'server' in user_lower:
    extracted["os"] = "LINUX_RHEL9"  # Default for generic "server"
```

- [ ] DELETE these two lines completely

## Phase 5: Update API to Handle Unavailable Specialists

### Task 5.1: Add Handling for Unavailable Specialists
**File**: `backend/api/main.py`

- [ ] Find the section handling compute_result (around line 185)
- [ ] After the check for `specialist_name == "gce_specialist"` (around line 187), add:

```python
elif compute_result.get("next_agent") == "unavailable":
    specialist_name = compute_result.get("specialist_name", "unknown")
    cloud_map = {
        "ec2_specialist": "AWS EC2",
        "azure_vm_specialist": "Azure VM",
        "gce_specialist": "GCP GCE"
    }
    friendly_name = cloud_map.get(specialist_name, specialist_name)
    return ChatResponse(
        response=f"The {friendly_name} specialist is not yet implemented. Currently, I can only help with GCP VMs.",
        needs_clarification=False,
        session_id=session_id,
        status="unavailable",
        mode=current_mode
    )
```

## Phase 6: Testing

### Task 6.1: Restart All Services
- [ ] Stop all containers: `docker-compose down`
- [ ] Rebuild and start: `docker-compose up --build`
- [ ] Wait for all services to be healthy

### Task 6.2: Test Environment Inference
- [ ] Run test:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a Linux server for development", "session_id": null}'
```
- [ ] Verify: Should NOT ask for environment
- [ ] Verify: Should show "Inferred appEnvironment: NONPROD, appEnvironmentSubtype: dev"

### Task 6.3: Test No OS Default
- [ ] Run test:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a server for development", "session_id": null}'
```
- [ ] Verify: Should ask for OS type
- [ ] Verify: Should NOT default to RHEL9

### Task 6.4: Test Unavailable Specialist
- [ ] Run test:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a VM in AWS", "session_id": null}'
```
- [ ] Verify: Should return "AWS EC2 specialist is not yet implemented"

### Task 6.5: Test Production Environment
- [ ] Run test:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Deploy a production Windows server", "session_id": null}'
```
- [ ] Verify: Should infer PROD environment
- [ ] Verify: Should default Windows to WINDOWS_22

### Task 6.6: Test MCP Endpoint
- [ ] Run test:
```bash
curl http://localhost:8001/specialists
```
- [ ] Verify: Returns list of all specialists with availability status

## Phase 7: Validation

### Task 7.1: Check Logs
- [ ] Check API logs: `docker logs taxi-chatbot-api-1`
- [ ] Verify: Orchestrator shows "Inferred environment: NONPROD (subtype: dev)"
- [ ] Verify: Compute Agent shows MCP query attempts
- [ ] Verify: GCE Specialist shows context usage

### Task 7.2: Edge Cases
- [ ] Test: "Create a database VM for QA" → Should infer NONPROD/qa
- [ ] Test: "Set up a staging server" → Should infer NONPROD/test
- [ ] Test: "Performance testing environment" → Should infer NONPROD/perf
- [ ] Test: "Create a VM" (no details) → Should ask for cloud provider

## Phase 8: Commit Changes

### Task 8.1: Stage and Commit
- [ ] Check git status: `git status`
- [ ] Stage all changes: `git add -A`
- [ ] Commit with message:
```bash
git commit -m "Fix environment inference with MCP-based specialist discovery

- GCE Specialist now uses context from upstream agents
- Compute Agent queries MCP for available specialists
- Removed hardcoded GCP default and incorrect OS defaults
- Environment inference now works correctly for obvious cases
- Added proper error messages for unavailable specialists

Fixes:
- No more asking 'Which environment?' for 'development server'
- No more defaulting 'server' to RHEL9
- Proper routing based on specialist availability"
```

## Rollback Plan

If issues occur:
1. [ ] Revert commit: `git revert HEAD`
2. [ ] Rebuild containers: `docker-compose up --build`
3. [ ] Verify system returns to previous behavior
4. [ ] Document specific issues encountered

## Success Criteria

- [ ] Environment correctly inferred for obvious cases
- [ ] No unnecessary clarification questions
- [ ] Proper error messages for unavailable specialists
- [ ] OS defaults only applied when OS type mentioned
- [ ] All test cases passing
- [ ] No performance degradation
- [ ] Logs show proper context usage

## Notes

- Always test incrementally after each phase
- Monitor logs closely during testing
- The MCP discovery can be extended later for other agent types
- Context usage pattern can be applied to other agents

## Time Estimate
- Phase 1-2: 30 minutes
- Phase 3-4: 20 minutes
- Phase 5: 10 minutes
- Phase 6-7: 30 minutes
- Phase 8: 10 minutes
- **Total: ~1.5-2 hours**