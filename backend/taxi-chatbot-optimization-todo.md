# TAXI Chatbot Optimization - Implementation TODO

## Phase 1: Reasoning Engine Optimization
- [ ] **File**: `backend/utils/reasoning.py`
  - [ ] Add environment variable support for timeouts (lines 83-86)
    - [ ] Add `REASONING_TIMEOUT_SIMPLE` (default 30s)
    - [ ] Add `REASONING_TIMEOUT_COMPLEX` (default 120s)
  - [ ] Reduce max_iterations for simple requests (line 77)
    - [ ] Check `context.simple_request` flag
    - [ ] Set max_iterations to 2 for simple, 5 for complex
  - [ ] Optimize LLM prompt lengths in `_observe()` and `_think()` methods

## Phase 2: Orchestrator Agent Updates
- [ ] **File**: `backend/agents/orchestrator.py`
  - [ ] Keep error correction system as-is
  - [ ] Optimize `skip_correction` logic (lines 116-138)
    - [ ] Expand conditions for skipping correction
    - [ ] Add check for "vm", "instance", "server" keywords
  - [ ] Simplify routing prompt in `_direct_reasoning()` (lines 235-264)
    - [ ] Focus on resource type detection only
    - [ ] Remove complex requirement extraction from prompt

## Phase 3: Compute Agent Simplification
- [ ] **File**: `backend/agents/compute.py`
  - [ ] Remove field extraction logic
    - [ ] Delete `_extract_requirements_llm()` method (lines 236-298)
    - [ ] Delete `_normalize_values()` method (lines 332-367)
    - [ ] Delete `_validate_requirements()` method (lines 369-395)
  - [ ] Simplify `process()` method (lines 397-551)
    - [ ] Remove VMRequest building logic
    - [ ] Remove extraction and normalization calls
    - [ ] Keep only cloud provider and specialist detection
  - [ ] Add `_detect_compute_type()` method
    - [ ] LLM determines: vm, kubernetes, serverless, etc.
    - [ ] Returns specialist name
  - [ ] Update routing logic
    - [ ] Single LLM call for provider + type → specialist
    - [ ] Pass raw context to specialist

## Phase 4: GCE Specialist Enhancement
- [ ] **File**: `backend/agents/gce_specialist.py`
  - [ ] Add `_extract_vm_requirements()` method
    - [ ] Move extraction logic from Compute Agent
    - [ ] Include intelligent corrections
    - [ ] Focus on TAXI required fields only
  - [ ] Modify `create_instance()` method (lines 478-550)
    - [ ] Add config parameter with bypass flags
    - [ ] Call extraction before validation
    - [ ] Check for missing fields and invoke clarification if needed
  - [ ] Update validation calls (lines 502-516)
    - [ ] Add `if not config["skip_validation"]` check
    - [ ] Default skip_validation to True
  - [ ] Update improvement suggestions (lines 517-520)
    - [ ] Add `if not config["skip_improvements"]` check
    - [ ] Default skip_improvements to True
  - [ ] Keep quota check but bypass by default

## Phase 5: API Endpoint Updates
- [ ] **File**: `backend/api/main.py`
  - [ ] Update `/chat` endpoint (lines 135-317)
    - [ ] Handle new Compute Agent response format
    - [ ] Remove VMRequest building in API
    - [ ] Pass raw context to specialists
  - [ ] Update SSE streaming endpoint (lines 477-628)
    - [ ] Adjust for new agent flow
    - [ ] Update progress messages
  - [ ] Add config flags to agent initialization
    - [ ] Pass skip flags to GCE specialist

## Phase 6: Error Correction Updates
- [ ] **File**: `backend/utils/error_correction.py`
  - [ ] Keep existing system
  - [ ] Add specific corrections for VM requests
    - [ ] "red hat 8" → "LINUX_RHEL8"
    - [ ] "windows 2022" → "WINDOWS_22"
    - [ ] Region vs zone detection
  - [ ] Ensure corrections don't expand simple requests

## Phase 7: Environment Configuration
- [ ] **File**: `backend/.env`
  - [ ] Add new environment variables:
    ```
    REASONING_TIMEOUT_SIMPLE=30.0
    REASONING_TIMEOUT_COMPLEX=120.0
    REASONING_MAX_ITERATIONS_SIMPLE=2
    REASONING_MAX_ITERATIONS_COMPLEX=5
    GCE_SKIP_VALIDATION=true
    GCE_SKIP_IMPROVEMENTS=true
    GCE_SKIP_QUOTA_CHECK=true
    ```

## Phase 8: Testing
- [ ] Test simple VM request flow
  - [ ] "Create a Linux server in GCP"
  - [ ] Verify < 50s response time
  - [ ] Check no unnecessary fields requested
- [ ] Test error corrections
  - [ ] "create red hat 8 vm"
  - [ ] "windows 2022 server"
  - [ ] "us-east" (region without zone)
- [ ] Test clarification flow
  - [ ] Missing required fields
  - [ ] Ambiguous requests
- [ ] Test routing to correct specialists
  - [ ] VM requests → gce_specialist
  - [ ] Future: Kubernetes → gke_specialist
- [ ] Verify no pattern matching
  - [ ] All decisions through LLM
  - [ ] No if/then logic for routing

## Phase 9: Documentation Updates
- [ ] Update CLAUDE.md with new architecture
- [ ] Document bypass flags
- [ ] Add performance metrics
- [ ] Update agent descriptions

## Phase 10: Monitoring & Rollback
- [ ] Add logging for performance metrics
  - [ ] Time per agent
  - [ ] Total request time
  - [ ] LLM API call count
- [ ] Verify rollback capability
  - [ ] Test re-enabling validation
  - [ ] Test re-enabling improvements
  - [ ] Ensure no breaking changes

---

## Implementation Order
1. Start with Phase 1 (Reasoning Engine) - Quick win for timeout reduction
2. Then Phase 4 (GCE Specialist) - Add bypass flags
3. Then Phase 3 (Compute Agent) - Simplify to routing only
4. Then Phase 5 (API updates) - Wire everything together
5. Complete with testing and documentation

## Success Criteria
- [ ] Response time < 50s for typical VM request
- [ ] No 120s timeouts for simple requests
- [ ] LLM API calls reduced by 50%
- [ ] All routing through LLM reasoning (no pattern matching)
- [ ] Intelligent error correction working
- [ ] Clarification agent integrated at all levels

## Notes
- Keep all existing code, use bypass flags
- Maintain fully agentic approach
- Focus on TAXI required fields only
- Test thoroughly before removing any code
- Document all changes

---
Document Version: 1.0
Date: 2025-01-25
Reference: taxi-chatbot-optimization-plan.md