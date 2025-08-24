# TODO: Timeout and Progress Feedback Fix Execution Checklist

## Phase 1: Immediate Timeout Relief (PRIORITY: CRITICAL)

### Task 1: Update LLM Manager Timeout
- [ ] Open `backend/utils/llm_manager.py`
- [ ] Change line 20: `"3000"` to `"75000"` (3s → 75s)
- [ ] Add comment explaining production timeout
- [ ] Test LLM calls don't timeout prematurely

### Task 2: Fix Reasoning Engine Timeouts
- [ ] Open `backend/utils/reasoning.py`
- [ ] Change line 366: `timeout=3.0` to `timeout=60.0`
- [ ] Update lines 82-88: Change `max_time` from 5.0/10.0 to 60.0/120.0
- [ ] Add configurable timeout from environment
- [ ] Test reasoning doesn't timeout

### Task 3: Fix Clarification Agent Timeout
- [ ] Open `backend/agents/clarification.py`
- [ ] Change line 218: `timeout=3.0` to `timeout=60.0`
- [ ] Add try/catch for better timeout handling
- [ ] Log timeout occurrences for monitoring

### Task 4: Create Environment Configuration
- [ ] Create `backend/.env.example` file
- [ ] Add timeout configurations:
  ```
  LLM_TIMEOUT=75000
  REASONING_TIMEOUT_SIMPLE=60
  REASONING_TIMEOUT_COMPLEX=120
  API_TIMEOUT=90000
  ```
- [ ] Document each setting with comments
- [ ] Update `.gitignore` to exclude `.env`

## Phase 2: Progress Tracking Infrastructure (PRIORITY: HIGH)

### Task 5: Enhance Session Model
- [ ] Open `backend/models/taxi_models.py`
- [ ] Add to ChatSession class:
  ```python
  progress_steps: List[Dict[str, Any]] = []
  current_agent: Optional[str] = None
  current_step: Optional[str] = None
  last_progress_update: Optional[datetime] = None
  ```
- [ ] Add ProgressStep model
- [ ] Add progress helper methods

### Task 6: Add Progress to BaseAgent
- [ ] Open `backend/agents/base_agent.py`
- [ ] Add `emit_progress()` method
- [ ] Add progress tracking to observe/think/act/reflect
- [ ] Implement percentage calculation logic
- [ ] Add progress event structure

### Task 7: Create Progress Manager Utility
- [ ] Create `backend/utils/progress_manager.py`
- [ ] Implement progress event queue
- [ ] Add SSE event formatting
- [ ] Create progress aggregation logic
- [ ] Add progress history management

## Phase 3: SSE Backend Implementation (PRIORITY: HIGH)

### Task 8: Install SSE Dependencies
- [ ] Add `sse-starlette` to requirements.txt
- [ ] Run `pip install sse-starlette`
- [ ] Update docker image with new dependency
- [ ] Verify import works

### Task 9: Create SSE Chat Endpoint
- [ ] Open `backend/api/main.py`
- [ ] Import SSE dependencies
- [ ] Create `/chat/stream` endpoint
- [ ] Implement event generator
- [ ] Add authentication check
- [ ] Test SSE connection

### Task 10: Add Progress Polling Fallback
- [ ] Add `/session/{id}/progress` endpoint
- [ ] Return last N progress events
- [ ] Add timestamp filtering
- [ ] Implement pagination
- [ ] Test polling endpoint

## Phase 4: Agent Progress Integration (PRIORITY: MEDIUM)

### Task 11: Update Orchestrator Agent
- [ ] Open `backend/agents/orchestrator.py`
- [ ] Add progress emissions:
  - "Analyzing user request..."
  - "Determining intent..."
  - "Routing to {agent}..."
- [ ] Include confidence scores in progress
- [ ] Test progress events emit

### Task 12: Update Clarification Agent  
- [ ] Open `backend/agents/clarification.py`
- [ ] Add progress emissions:
  - "Reviewing current information..."
  - "Identifying missing fields..."
  - "Generating natural questions..."
- [ ] Add field completion percentage
- [ ] Test progress flow

### Task 13: Update Compute Agent
- [ ] Open `backend/agents/compute.py`
- [ ] Add progress emissions:
  - "Extracting VM requirements..."
  - "Detecting cloud provider..."
  - "Validating specifications..."
- [ ] Note: This agent still needs refactoring from pattern matching
- [ ] Test with current implementation

### Task 14: Update GCE Specialist Agent
- [ ] Open `backend/agents/gce_specialist.py`
- [ ] Add progress emissions:
  - "Preparing TAXI payload..."
  - "Validating GCP configuration..."
  - "Submitting provisioning request..."
- [ ] Include validation progress
- [ ] Test payload generation progress

## Phase 5: Frontend Real-time Updates (PRIORITY: MEDIUM)

### Task 15: Add EventSource Support
- [ ] Open `frontend/app/page.tsx`
- [ ] Import/implement EventSource
- [ ] Create SSE connection handler
- [ ] Add reconnection logic
- [ ] Handle connection errors

### Task 16: Update Chat Function for SSE
- [ ] Replace fetch with EventSource for `/chat/stream`
- [ ] Parse SSE events
- [ ] Update UI on progress events
- [ ] Handle stream completion
- [ ] Add timeout countdown

### Task 17: Enhance Loading UI
- [ ] Add progress message state
- [ ] Display current step above loading dots
- [ ] Show agent name and action
- [ ] Add progress percentage if available
- [ ] Include elapsed time counter

### Task 18: Add Fallback to Polling
- [ ] Detect SSE support
- [ ] Implement polling as fallback
- [ ] Poll `/session/{id}/progress` every 2s
- [ ] Merge progress updates
- [ ] Test fallback works

## Phase 6: Testing & Validation (PRIORITY: HIGH)

### Task 19: Unit Tests for Timeouts
- [ ] Create `backend/tests/test_timeout_config.py`
- [ ] Test timeout loading from env
- [ ] Test timeout application in agents
- [ ] Test timeout error handling
- [ ] Verify all timeout locations updated

### Task 20: Integration Tests for Progress
- [ ] Create `backend/tests/test_progress_flow.py`
- [ ] Test progress through full chat flow
- [ ] Test SSE event generation
- [ ] Test progress aggregation
- [ ] Test polling endpoint

### Task 21: Frontend E2E Tests
- [ ] Test SSE connection establishment
- [ ] Test progress message updates
- [ ] Test reconnection on disconnect
- [ ] Test fallback to polling
- [ ] Test timeout warnings

### Task 22: Performance Testing
- [ ] Test with 60+ second operations
- [ ] Monitor memory during long timeouts
- [ ] Test concurrent SSE connections
- [ ] Verify cleanup after timeout
- [ ] Check resource usage

## Phase 7: Documentation & Deployment (PRIORITY: LOW)

### Task 23: Update Documentation
- [ ] Document new environment variables
- [ ] Add SSE endpoint documentation
- [ ] Create progress event schema docs
- [ ] Update API documentation
- [ ] Add troubleshooting guide

### Task 24: Deployment Preparation
- [ ] Update Docker configuration
- [ ] Set production timeout values
- [ ] Configure SSE in reverse proxy
- [ ] Add monitoring for timeouts
- [ ] Create rollback procedure

## Validation Checklist

### Before Marking Complete
- [ ] All timeouts increased to 60+ seconds
- [ ] SSE endpoint functioning
- [ ] Progress events emitting from all agents
- [ ] Frontend shows real-time progress
- [ ] Fallback to polling works
- [ ] No memory leaks detected
- [ ] Tests passing
- [ ] Documentation updated

## Rollback Procedure
1. Set `USE_SSE_PROGRESS=false` in environment
2. Revert timeout values in `.env`
3. Frontend automatically uses original fetch
4. Monitor for issues
5. Full code rollback if needed via git

## Success Criteria
- ✅ Zero timeout errors for operations under 60s
- ✅ Progress updates visible every 2-5 seconds
- ✅ Users see what agent is processing
- ✅ Clear indication of long-running operations
- ✅ Graceful handling of actual timeouts

## Notes
- Start with Phase 1 for immediate relief
- SSE can be deployed incrementally
- Monitor timeout patterns in production
- Consider adding timeout analytics
- This integrates with Phases 3 & 5 of agentic system plan

## Time Estimates
- Phase 1: 2-3 hours (immediate)
- Phase 2: 3-4 hours
- Phase 3: 4-5 hours  
- Phase 4: 2-3 hours
- Phase 5: 5-6 hours
- Phase 6: 3-4 hours
- Phase 7: 2-3 hours
- **Total: ~24-30 hours**

## Dependencies
- No blocking dependencies for Phase 1
- SSE requires `sse-starlette` package
- Frontend requires EventSource support (standard in modern browsers)
- Testing requires updated test fixtures

## Risk Factors
- ⚠️ Compute Agent still uses pattern matching (noted in agentic plan)
- ⚠️ No Valkey integration yet (memory only)
- ⚠️ SSE connection limits in some proxies
- ⚠️ Browser compatibility for older versions

## Priority Execution Order
1. **IMMEDIATE**: Phase 1 (Tasks 1-4) - Fix timeouts now
2. **NEXT**: Phase 2-3 (Tasks 5-10) - Add progress infrastructure  
3. **THEN**: Phase 4-5 (Tasks 11-18) - Integrate progress in agents/UI
4. **FINALLY**: Phase 6-7 (Tasks 19-24) - Test and deploy