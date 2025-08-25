# TAXI Chatbot Optimization Plan
## Fixing Reasoning Timeout and Simplifying Agent Architecture

### Problem Statement
The TAXI chatbot is experiencing 120+ second timeouts during reasoning, with excessive LLM API calls and overly complex error correction that asks for unnecessary fields (firewall rules, SSH keys, service accounts) not required by the TAXI API.

### Root Cause Analysis
1. **ReasoningEngine timeout**: Set to 120s with up to 5 iterations, each making multiple LLM calls
2. **Error correction over-expansion**: Simple requests like "Create a Linux server" get expanded to 15+ parameters
3. **Redundant validation loops**: Multiple agents validating the same data
4. **Excessive reasoning iterations**: Simple requests trigger full reasoning chains

### Solution Architecture

## 1. Agent Hierarchy and Responsibilities

### Orchestrator Agent (120s timeout)
- **Purpose**: Determine resource category through LLM reasoning
- **Keeps**: Error correction system for complex requests
- **Keeps**: Full reasoning engine
- **Routes to**: compute, database (future), storage (future), network (future)
- **No changes to core logic**

### Compute Agent (45s timeout) 
- **Purpose**: Route to appropriate compute specialist
- **Removes**: ALL field extraction logic
- **Removes**: VMRequest building
- **Keeps**: Pure LLM routing to specialists
- **Available specialists**:
  - GCP: gce_specialist, gke_specialist (future), cloud_run_specialist (future)
  - AWS: ec2_specialist (future), eks_specialist (future), lambda_specialist (future)
  - Azure: azure_vm_specialist (future), aks_specialist (future)

### Specialist Agents (15-20s timeout)
- **Purpose**: Extract fields, apply corrections, generate TAXI JSON
- **Adds**: Field extraction (moved from Compute Agent)
- **Adds**: Intelligent error correction
- **Adds**: Bypass flags for validation/improvements
- **Generates**: TAXI-compliant JSON payload

### Clarification Agent (Universal)
- Works with ALL agents
- Can be invoked at any level for missing information
- Maintains conversational flow

## 2. Implementation Details

### 2.1 Compute Agent Simplification

```python
async def process(self, context):
    # Pure LLM routing - NO pattern matching
    routing_prompt = f"""
    Analyze this compute request: {context["raw_request"]}
    
    Available specialists:
    - gce_specialist: Google Cloud VMs/instances
    - gke_specialist: Google Kubernetes Engine
    - ec2_specialist: AWS EC2 instances
    - eks_specialist: AWS Kubernetes
    - azure_vm_specialist: Azure VMs
    
    Determine which specialist should handle this request.
    Apply corrections for typos and variations.
    
    Return JSON:
    {{
        "specialist": "specialist_name",
        "reasoning": "why this specialist",
        "detected_provider": "gcp/aws/azure",
        "detected_type": "vm/kubernetes/serverless",
        "corrections_applied": [],
        "confidence": 0.0-1.0
    }}
    """
    
    result = self._llm_reason(routing_prompt)
    return {
        "next_agent": result["specialist"],
        "context": context,
        "routing_metadata": result
    }
```

### 2.2 GCE Specialist Enhancement

```python
async def create_instance(self, context, config=None):
    config = config or {
        "skip_validation": True,      # Bypass for speed
        "skip_improvements": True,     # Bypass for speed
        "skip_quota_check": True      # Bypass for speed
    }
    
    # Extract AND correct in one LLM pass
    extraction_prompt = f"""
    Extract VM requirements from: {context["raw_request"]}
    
    Apply intelligent corrections:
    - "red 8" or "rhel 8" → LINUX_RHEL8
    - "windows 2022" or "win22" → WINDOWS_22
    - "us-east" → identify as region, need zone clarification
    - "cheap vm" → suggest e2-micro
    - "n1" alone → n1-standard-1
    - Fix common typos and variations
    
    Extract ONLY TAXI required fields:
    - appEnvironment: NONPROD/PROD
    - appEnvironmentSubtype: dev/qa/test/perf (if NONPROD)
    - lineOfBusiness: RETAIL/ISTS/EDML
    - costCenter: 5-digit code
    - project: GCP project ID
    - zone: Full zone (e.g., us-east4-a)
    - os: LINUX_RHEL8/LINUX_RHEL9/WINDOWS_19/WINDOWS_22
    - useType: app/database
    - machineType: Valid GCP machine type
    - id: User email
    
    Return JSON:
    {{
        "extracted_fields": {{}},
        "corrections_applied": [],
        "missing_fields": [],
        "clarifications_needed": [],
        "confidence": 0.0-1.0
    }}
    """
    
    result = self._llm_reason(extraction_prompt)
    
    # Check for clarifications
    if result["clarifications_needed"]:
        return {
            "needs_clarification": True,
            "questions": result["clarifications_needed"],
            "partial_data": result["extracted_fields"]
        }
    
    # Skip validation if configured
    if not config["skip_validation"]:
        validation = await self._validate_config_llm(result["extracted_fields"])
        if not validation["valid"]:
            return {"error": "Validation failed", "issues": validation["issues"]}
    
    # Build TAXI payload
    taxi_payload = self._build_taxi_payload(result["extracted_fields"])
    
    # Provision
    provision_result = self._provision_instance(taxi_payload)
    
    return {
        "success": True,
        "payload": taxi_payload,
        "result": provision_result,
        "corrections": result["corrections_applied"]
    }
```

### 2.3 Reasoning Engine Optimization

```python
# Add to utils/reasoning.py
async def reason(self, context: ReasoningContext, input_data: Any):
    # Reduce iterations for simple requests
    if context.simple_request:
        context.max_iterations = 2  # Instead of 5
    
    # Configure timeouts based on request complexity
    simple_timeout = float(os.getenv('REASONING_TIMEOUT_SIMPLE', '30.0'))
    complex_timeout = float(os.getenv('REASONING_TIMEOUT_COMPLEX', '120.0'))
    max_time = simple_timeout if context.simple_request else complex_timeout
    
    # Rest of reasoning logic...
```

## 3. Error Correction Examples

### Intelligent Corrections at Each Level

**Orchestrator**:
- "create a databse" → "database" (typo)
- "make me a server" → "create a VM" (intent)

**Compute Agent**:
- "deploy on Google" → gce_specialist
- "k8s cluster" → gke_specialist
- "cheap linux on gcp" → gce_specialist

**GCE Specialist**:
- "red hat 8" → LINUX_RHEL8
- "us-east" → "You specified region us-east4. Which zone (a, b, or c)?"
- "windows server 2022" → WINDOWS_22
- "n1" → n1-standard-1
- "e2" → "Which e2 type? (micro, small, medium, standard-2/4/8)?"

## 4. Performance Targets

### Before Optimization
- Orchestrator: 120s with error correction expansion
- Compute: 45s with extraction
- GCE: 40s with validation
- **Total**: 120-200s typical

### After Optimization  
- Orchestrator: 30s for simple requests (reduced iterations)
- Compute: 20s (routing only)
- GCE: 15s (extraction + JSON, no validation)
- **Total**: 40-50s typical

## 5. Configuration Changes

### Environment Variables
```bash
# Reasoning timeouts
REASONING_TIMEOUT_SIMPLE=30.0
REASONING_TIMEOUT_COMPLEX=120.0
REASONING_MAX_ITERATIONS_SIMPLE=2
REASONING_MAX_ITERATIONS_COMPLEX=5

# Agent models (keep consistent)
AGENT_REASONING_MODEL=gpt-5-mini

# Specialist configuration
GCE_SKIP_VALIDATION=true
GCE_SKIP_IMPROVEMENTS=true
GCE_SKIP_QUOTA_CHECK=true
```

## 6. Testing Scenarios

### Scenario 1: Simple VM Request
**Input**: "Create a Linux server for development in GCP in project dwayne-1234"
- Orchestrator: Detects compute → Compute Agent (5s)
- Compute: Routes to gce_specialist (10s)
- GCE: Extracts fields, identifies missing (zone, LOB, cost center), calls clarification (10s)
- **Total**: ~25s

### Scenario 2: Typos and Corrections
**Input**: "create red hat 8 vm in gcp us-east cheap"
- Orchestrator: Detects compute → Compute Agent (5s)
- Compute: Routes to gce_specialist (10s)
- GCE: Corrects "red hat 8" → LINUX_RHEL8, asks for zone in us-east4, suggests e2-micro (15s)
- **Total**: ~30s

### Scenario 3: Ambiguous Request
**Input**: "I need a server"
- Orchestrator: Unclear, calls clarification for cloud provider (10s)
- User: "GCP"
- Orchestrator: Routes to Compute Agent (5s)
- Compute: Routes to gce_specialist (10s)
- GCE: Asks for required fields (15s)
- **Total**: ~40s

## 7. Critical Requirements

### Must Maintain
1. **Fully agentic**: NO pattern matching, all LLM reasoning
2. **Error correction**: Keep intelligent corrections at all levels
3. **Clarification**: Universal agent works with all
4. **Model consistency**: gpt-5-mini with temperature=1.0
5. **Four-agent architecture**: Orchestrator, Compute, Specialists, Clarification

### Must Remove/Reduce
1. **Excessive iterations**: Cap at 2 for simple requests
2. **Unnecessary fields**: Only TAXI required fields
3. **Redundant validation**: Bypass by default
4. **Complex error expansion**: Don't add firewall, SSH, etc.

## 8. Rollback Plan

All changes preserve existing code with bypass flags:
- Validation code remains, just bypassed
- Improvement suggestions remain, just bypassed
- Can re-enable by changing config flags
- No destructive changes to core logic

## 9. Success Metrics

1. **Response time**: < 50s for typical VM request
2. **Timeout reduction**: No more 120s timeouts for simple requests
3. **API calls**: Reduce LLM calls by 50%
4. **User experience**: Faster responses, fewer unnecessary questions
5. **Accuracy**: Maintain intelligent corrections and clarifications

## 10. Implementation Priority

1. **Phase 1**: Reasoning engine timeout optimization
2. **Phase 2**: Move extraction from Compute to Specialists
3. **Phase 3**: Add bypass flags to GCE specialist
4. **Phase 4**: Simplify Compute Agent to routing only
5. **Phase 5**: Test and tune timeouts

---
Document Version: 1.0
Date: 2025-01-25
Author: Claude Code Assistant