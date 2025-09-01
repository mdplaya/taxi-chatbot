# Implementation TODO - Fix TAXI Chatbot JSON Output Issue

## Pre-Implementation Tasks
- [ ] Create new git branch: `fix/chatbot-json-output`
- [ ] Review current test coverage for affected components
- [ ] Back up current orchestrator.py and api/main.py files
- [ ] Set up test environment for validation

## Phase 1: Fix Orchestrator Fast-Path Logic

### Task 1.1: Enhance Keyword Detection (orchestrator.py)
- [ ] Expand vm_keywords list (line ~121)
  - Add: 'virtual machine', 'virtual-machine', 'instance', 'instances', 'server', 'servers', 'machine', 'box', 'node'
  - Make case-insensitive comparison
- [ ] Add database_keywords expansion (line ~122)
  - Include: 'rds', 'cloudsql', 'datastore'
- [ ] Test keyword detection with various inputs

### Task 1.2: Improve Provider Detection (orchestrator.py)
- [ ] Create provider_patterns dictionary (after line ~122)
  ```python
  provider_patterns = {
      'gcp': ['gcp', 'google', 'gce', 'google cloud'],
      'aws': ['aws', 'amazon', 'ec2', 'amazon web services'],
      'azure': ['azure', 'microsoft', 'windows azure'],
      'onprem': ['on-prem', 'on prem', 'onprem', 'datacenter']
  }
  ```
- [ ] Implement provider detection logic in fast-path (lines 183-186)
- [ ] Test provider detection for all cloud providers

### Task 1.3: Add OS Detection (orchestrator.py)
- [ ] Create os_patterns dictionary
  ```python
  os_patterns = {
      'windows': ['windows', 'win', 'w2k', 'win2022', 'win2019'],
      'linux': ['linux', 'ubuntu', 'centos', 'debian', 'fedora'],
      'rhel': ['rhel', 'redhat', 'red hat', 'red-hat']
  }
  ```
- [ ] Add OS extraction in fast-path section (lines 183-190)
- [ ] Test OS detection with various patterns

### Task 1.4: Enhance Fast-Path Trigger Logic (orchestrator.py)
- [ ] Modify fast-path condition (line 179)
  - Change from: `if is_simple and "vm" in processed_input.lower()`
  - To: `if is_simple and is_vm_request`
- [ ] Add comprehensive VM request detection
- [ ] Test with edge cases and variations

### Task 1.5: Improve Field Extraction (orchestrator.py)
- [ ] Add zone/region extraction logic
- [ ] Add machine type detection (if specified)
- [ ] Add use type detection (app server, database, web server)
- [ ] Add line of business detection
- [ ] Test field extraction completeness

## Phase 2: Fix API Endpoint Logic

### Task 2.1: Add Logging for Debugging (api/main.py)
- [ ] Add logging before orchestrator call (line ~295)
- [ ] Log orchestrator result details (line ~296)
- [ ] Log routing decision and reasoning
- [ ] Add timestamp to all log entries

### Task 2.2: Implement Fallback Recovery (api/main.py)
- [ ] Modify clarification handler (lines 307-325)
- [ ] Add VM keyword detection in clarification branch
- [ ] Implement force-routing to compute agent when VM detected
- [ ] Add retry logic for failed routing
- [ ] Test fallback recovery mechanism

### Task 2.3: Enhance Error Messages (api/main.py)
- [ ] Create context-aware error messages
- [ ] Include detected intent in error response
- [ ] Suggest specific missing information
- [ ] Test error message clarity

## Phase 3: Improve LLM Reasoning

### Task 3.1: Simplify Routing Prompts (orchestrator.py)
- [ ] Simplify prompt in _direct_reasoning (lines 251-263)
- [ ] Add explicit VM routing examples
- [ ] Reduce prompt complexity for simple requests
- [ ] Test prompt effectiveness

### Task 3.2: Add Validation Logic (orchestrator.py)
- [ ] Validate LLM routing decisions (after line 290)
- [ ] Add confidence threshold checking
- [ ] Implement decision correction for obvious errors
- [ ] Test validation logic

### Task 3.3: Optimize Reasoning Performance (orchestrator.py)
- [ ] Reduce reasoning iterations for simple requests
- [ ] Add caching for common patterns
- [ ] Implement timeout handling
- [ ] Measure and log performance metrics

## Phase 4: Testing & Validation

### Task 4.1: Unit Tests
- [ ] Write tests for enhanced keyword detection
- [ ] Write tests for provider detection
- [ ] Write tests for OS detection
- [ ] Write tests for fast-path logic
- [ ] Write tests for fallback recovery

### Task 4.2: Integration Tests
- [ ] Test simple VM request: "I want a VM"
- [ ] Test with provider: "Create a GCP instance"
- [ ] Test detailed request: "Deploy Windows 2022 in us-east4-a"
- [ ] Test variations: "virtual machine", "server", "compute"
- [ ] Test mixed case: "I need a VM in GCP"
- [ ] Test with typos: "ceate a vm in gpc"
- [ ] Test database requests still work
- [ ] Test other resource types unaffected

### Task 4.3: End-to-End Testing
- [ ] Start all services (docker-compose up)
- [ ] Test via frontend UI with various inputs
- [ ] Verify JSON payload generation
- [ ] Test clarification flow when truly needed
- [ ] Verify session management works
- [ ] Test error recovery scenarios

### Task 4.4: Performance Testing
- [ ] Measure response time for simple requests (target: < 2s)
- [ ] Measure fast-path hit rate (target: > 90%)
- [ ] Measure clarification rate (target: < 10% for VM requests)
- [ ] Profile memory usage
- [ ] Test concurrent request handling

## Phase 5: Documentation & Deployment

### Task 5.1: Update Documentation
- [ ] Update CLAUDE.md with new patterns
- [ ] Document new fast-path logic
- [ ] Add troubleshooting guide
- [ ] Update API documentation

### Task 5.2: Code Review Preparation
- [ ] Run linters (npm run lint, python linters)
- [ ] Run type checking
- [ ] Ensure code follows conventions
- [ ] Add appropriate comments (if requested)

### Task 5.3: Deployment
- [ ] Merge to main branch after testing
- [ ] Update docker images
- [ ] Deploy to staging environment
- [ ] Run smoke tests
- [ ] Monitor logs for issues

## Success Criteria
- [ ] Simple VM requests succeed without clarification
- [ ] All test cases pass
- [ ] Response time < 2 seconds for simple requests
- [ ] JSON payload generated correctly
- [ ] No regression in other functionalities
- [ ] Clear error messages when clarification needed
- [ ] Logs provide debugging information

## Rollback Plan
- [ ] Keep backup of original files
- [ ] Document rollback procedure
- [ ] Test rollback process
- [ ] Have monitoring in place

## Notes
- Priority: Fix fast-path logic first (highest impact)
- Test after each phase before proceeding
- Keep conversational flow natural
- Maintain backward compatibility
- Use gpt-5-mini model with temperature 1.0

## Critical Files to Modify
1. `backend/agents/orchestrator.py` - Lines 117-207, 241-311
2. `backend/api/main.py` - Lines 295-325
3. `backend/agents/compute.py` - Enhancement for better extraction (optional)

## Test Commands
```bash
# Start services
docker-compose up --build

# Test simple request
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want a VM", "session_id": null}'

# Test with provider
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a GCP instance", "session_id": null}'

# Test detailed
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Deploy Windows 2022 VM in us-east4-a for retail", "session_id": null}'
```

## Estimated Time
- Phase 1: 2-3 hours
- Phase 2: 1-2 hours
- Phase 3: 1-2 hours
- Phase 4: 2-3 hours
- Phase 5: 1 hour
- **Total: 7-11 hours**

## Risk Mitigation
- Test each change incrementally
- Keep original logic as fallback
- Add feature flags if needed
- Monitor production closely after deployment