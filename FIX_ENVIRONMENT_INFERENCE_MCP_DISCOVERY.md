# Fix Environment Inference with MCP-Based Specialist Discovery

## Executive Summary
Users are experiencing poor UX when requesting VMs - the system asks obvious questions like "Which environment?" when the user says "development server". This document provides a complete solution using MCP-based specialist discovery to fix environment inference while maintaining agent autonomy.

## Problem Statement

### Current User Experience Issue
**Input**: "Create a Linux server for development"
**Current Behavior**: System asks "Is this workload for PROD or NONPROD?"
**Expected Behavior**: System should infer NONPROD/dev from "development" keyword

### Root Causes

1. **Context Not Used**: The GCE Specialist receives `extracted_requirements` from the Orchestrator (containing environment: NONPROD, appEnvironmentSubtype: dev) but completely ignores it, re-extracting everything from raw text.

2. **Hardcoded GCP Default**: Compute Agent defaults to `gce_specialist` for unclear requests instead of checking what's actually available.

3. **Incorrect OS Defaults**: Generic "server" defaults to LINUX_RHEL9, which is incorrect.

4. **No Dynamic Discovery**: No way to dynamically know which specialists are implemented.

## Solution Architecture: Option 3 - MCP-Based Discovery with LLM Routing

### Design Principles
1. **Agent Autonomy**: Each agent makes its own decisions
2. **Context Awareness**: Agents can leverage upstream context as hints
3. **Single Source of Truth**: MCP server maintains what specialists exist
4. **LLM-Driven Routing**: The Compute Agent's LLM sees all options and chooses

### Data Flow
```
User Input → Orchestrator → Compute Agent → GCE Specialist → TAXI API
                ↓                ↓                ↓
         Extracts env      Queries MCP      Uses context
         (NONPROD/dev)     for specialists   (sees NONPROD/dev)
```

## Detailed Implementation

### Component 1: MCP Server Enhancement
**File**: `backend/mcp_server/server.py`

Add a new endpoint to list available specialists (after line 166):

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

### Component 2: Compute Agent with MCP Discovery
**File**: `backend/agents/compute.py`

#### Add imports (line 10):
```python
import httpx
from typing import Optional, List
```

#### Add specialist discovery (after line 30):
```python
def __init__(self):
    super().__init__()
    self.mcp_url = "http://localhost:8001"
    self._available_specialists = None  # Cache
    
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

#### Update routing method (replace `_detect_compute_type` at line 235):
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

#### Remove hardcoded default (delete lines 338-344):
```python
# DELETE THESE LINES:
# Default to GCE if unclear but looks like VM request
if not specialist or specialist == "unclear":
    if any(kw in raw_request.lower() for kw in ['vm', 'server', 'instance', 'linux', 'windows']):
        specialist = "gce_specialist"
```

### Component 3: GCE Specialist Context Usage
**File**: `backend/agents/gce_specialist.py`

#### Update extraction to use context (modify `_extract_vm_requirements` at line 150):
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
    
    Apply intelligent corrections and inference:
    
    ENVIRONMENT INFERENCE (with automatic subtype):
    - Development keywords: "development", "dev", "develop", "sandbox", "demo", "poc", 
      "proof of concept", "prototype", "experimental", "training", "learning", "education"
      → appEnvironment: NONPROD, appEnvironmentSubtype: dev
    
    - Testing keywords: "testing", "test", "unit test", "integration", "staging", 
      "stage", "pre-prod", "preprod", "uat", "user acceptance"
      → appEnvironment: NONPROD, appEnvironmentSubtype: test
    
    - QA keywords: "qa", "quality", "quality assurance", "validation", "verification"
      → appEnvironment: NONPROD, appEnvironmentSubtype: qa
    
    - Performance keywords: "performance", "perf", "load test", "stress test", 
      "benchmark", "capacity"
      → appEnvironment: NONPROD, appEnvironmentSubtype: perf
    
    - Production keywords: "production", "prod", "live", "operational", "operations", 
      "critical", "customer-facing", "public"
      → appEnvironment: PROD
    
    OS DEFAULTS (only when OS type is mentioned):
    - "Linux" or "linux server" without specific distro → LINUX_RHEL9
    - "Windows" or "windows server" without version → WINDOWS_22
    - "RHEL" or "Red Hat" without version → LINUX_RHEL9
    - DO NOT default "server" alone to any OS
    
    USE TYPE INFERENCE:
    - Web/Frontend keywords: "web", "website", "frontend", "ui" → useType: app
    - Database keywords: "database", "db", "mysql", "postgres", "storage" → useType: database
    - Backend/API keywords: "api", "backend", "service", "microservice" → useType: app
    - Default if unclear → useType: app
```

#### Remove incorrect OS default (in the prompt above):
```python
# REMOVE this line from the prompt:
- "server" alone without OS specified → LINUX_RHEL9

# REPLACE with:
- DO NOT default "server" alone to any OS
```

### Component 4: Orchestrator OS Default Fix
**File**: `backend/agents/orchestrator.py`

#### Fix OS detection (modify lines 252-256):
```python
# REMOVE these lines:
elif 'server' in user_lower:
    extracted["os"] = "LINUX_RHEL9"  # Default for generic "server"

# The check should only apply OS defaults when OS type is explicitly mentioned
```

## Test Scenarios

### Test 1: Environment Inference
**Input**: "Create a Linux server for development"
**Expected**:
- Orchestrator extracts: environment=NONPROD, appEnvironmentSubtype=dev
- Compute Agent queries MCP, routes to gce_specialist
- GCE Specialist uses context, sees NONPROD/dev
- NO environment question asked
- Only asks for: lineOfBusiness, costCenter, project, zone

### Test 2: No OS Default for Generic Server
**Input**: "Create a server for development"
**Expected**:
- Should ask for OS type
- Should NOT default to RHEL9

### Test 3: Unavailable Specialist
**Input**: "Create a VM in AWS"
**Expected**:
- Compute Agent queries MCP
- Sees ec2_specialist is not available
- Returns: "AWS EC2 specialist is not yet implemented"

### Test 4: Ambiguous Request with One Specialist
**Input**: "Create a Linux VM"
**Expected**:
- No cloud provider specified
- Compute Agent sees only gce_specialist available
- Routes to GCE with message: "No cloud provider specified, routing to available GCP specialist"

### Test 5: Production Inference
**Input**: "Deploy a production Windows server"
**Expected**:
- Infers environment=PROD
- Defaults Windows to WINDOWS_22
- Routes to GCE specialist

## Validation Checklist

### Architecture
✅ Maintains agent autonomy - each agent decides with context
✅ Single source of truth - MCP server for specialists
✅ No hardcoded defaults - dynamic discovery
✅ LLM-driven decisions - not rules-based

### Implementation
✅ Context flows properly through pipeline
✅ Extracted requirements used as hints, not mandates
✅ MCP discovery with fallback
✅ Removed incorrect OS defaults

### User Experience
✅ No obvious questions (environment inference works)
✅ Clear error messages for unavailable specialists
✅ Proper routing based on availability

## Rollback Plan
If issues occur:
1. Remove MCP endpoint (non-breaking)
2. Revert Compute Agent to previous routing
3. Remove context usage from GCE Specialist
4. System returns to current behavior

## Summary
This solution fixes the environment inference issue by ensuring the GCE Specialist uses context from upstream agents while maintaining agent autonomy. The MCP-based discovery ensures proper routing without hardcoded defaults. The result is a better user experience with fewer unnecessary questions.