# Backend Simplification Execution Todo List
**Branch**: backend-simplification  
**IMPORTANT**: Keep gpt-5-mini model and temperature 1.0

## Phase 1: Utils Directory Cleanup

### utils/reasoning.py (473→100 lines)
- [ ] Extract basic `_llm_reason()` function to keep
- [ ] Remove ReAct pattern implementation (lines 50-350)
- [ ] Remove multi-step reasoning loops
- [ ] Remove reflection and self-critique systems
- [ ] Remove advanced thought generation
- [ ] Keep only simple prompt formatting and response parsing
- [ ] Update imports in files that use this module

### utils/error_correction.py (512→50 lines)
- [ ] Extract basic field validation functions to keep
- [ ] Remove complex error detection patterns (lines 100-400)
- [ ] Remove multi-layer correction strategies
- [ ] Remove advanced pattern matching for corrections
- [ ] Remove historical error tracking
- [ ] Keep simple normalization helpers
- [ ] Update all files importing this module

### utils/learning.py (508→100 lines)
- [ ] Extract basic user preference storage to keep
- [ ] Remove cross-agent learning coordination (lines 150-350)
- [ ] Remove complex pattern recognition
- [ ] Remove advanced preference learning
- [ ] Remove multi-session pattern detection
- [ ] Keep session-based preferences only
- [ ] Update Valkey storage calls

### utils/progress_manager.py (291→100 lines)
- [ ] Extract basic progress update functions
- [ ] Remove SSE streaming complexity (lines 50-200)
- [ ] Remove complex event management
- [ ] Remove redundant progress tracking
- [ ] Keep simple status tracking
- [ ] Update API endpoints using progress manager

### utils/valkey_manager.py (348→200 lines)
- [ ] Remove complex learning storage operations
- [ ] Remove multi-index pattern storage
- [ ] Remove advanced query operations
- [ ] Keep basic session storage
- [ ] Keep simple key-value operations
- [ ] Consolidate duplicate functions
- [ ] Test session persistence

### utils/llm_manager.py
- [ ] Remove unused LLM functions
- [ ] Consolidate duplicate prompt formatting
- [ ] Remove experimental features
- [ ] Keep core LLM interaction methods

## Phase 2: Agent Architecture Simplification

### agents/base_agent.py (750→200 lines)
- [ ] Remove ReAct pattern implementation (lines 200-500)
- [ ] Remove learning engine integration
- [ ] Remove complex memory management
- [ ] Remove reflection and improvement systems
- [ ] Remove advanced progress callbacks
- [ ] Keep basic LLM interaction
- [ ] Keep simple session context
- [ ] Keep core agent interface
- [ ] Update all agent subclasses

### agents/orchestrator.py (30% reduction)
- [ ] Remove unused learning integration calls
- [ ] Remove complex context building
- [ ] Remove redundant validation
- [ ] Simplify conversation management
- [ ] Keep core routing logic
- [ ] Keep state handling
- [ ] Keep agent selection logic
- [ ] Test routing to clarification and compute agents

### agents/clarification.py (20% reduction)
- [ ] Remove complex learning patterns
- [ ] Remove redundant field processing
- [ ] Keep business-first logic intact
- [ ] Keep natural conversation flow
- [ ] Keep field collection
- [ ] Keep error correction with AI
- [ ] Ensure ALL known fields are shown
- [ ] Test question generation

### agents/compute.py (25% reduction)
- [ ] Remove unused pattern detection
- [ ] Remove complex reasoning loops
- [ ] Keep cloud provider detection (GCP/AWS/Azure/OnPrem)
- [ ] Keep requirement extraction
- [ ] Keep specialist agent routing
- [ ] Test all cloud provider paths
- [ ] Verify field extraction

### agents/gce_specialist.py (20% reduction)
- [ ] Remove unused improvement suggestions
- [ ] Remove complex validation loops
- [ ] Keep GCE validation
- [ ] Keep TAXI payload generation
- [ ] Keep field normalization
- [ ] Test TAXI payload structure
- [ ] Verify all required fields

## Phase 3: API and Main Module Cleanup

### api/main.py (1473→900 lines)
- [ ] Remove duplicate field normalization (lines 300-500)
- [ ] Remove complex field inference functions
- [ ] Remove redundant validation logic
- [ ] Remove unused endpoints
- [ ] Simplify session handling
- [ ] Keep core endpoints (/chat, /answer, /session/*)
- [ ] Keep basic field processing
- [ ] Keep error handling
- [ ] Keep health checks
- [ ] Consolidate duplicate helper functions

### Fast-Path Business Fields (No LLM)
- [ ] Make `$.resourceMetadata.lineOfBusiness` use direct catalog lookup
- [ ] Make `$.options.requestor.id` use simple email extraction
- [ ] Make `$.resourceMetadata.costCenter` use direct catalog lookup
- [ ] Remove LLM calls for these fields
- [ ] Add direct validation for these fields

## Phase 4: Configuration and Cleanup

### Environment Variables
- [ ] Audit all 118 environment variables
- [ ] Identify which are actually used
- [ ] Remove unused variables
- [ ] Document required variables
- [ ] Set sensible defaults
- [ ] Update .env.example

### Remove Dead Code
- [ ] Remove unused imports in all files
- [ ] Remove commented-out code blocks
- [ ] Remove experimental features not in use
- [ ] Remove duplicate utility functions
- [ ] Remove unused test files
- [ ] Clean up logging statements

### Update Dependencies
- [ ] Review requirements.txt
- [ ] Remove unused packages
- [ ] Update package versions if needed
- [ ] Test with clean install

## Phase 5: Testing and Validation

### Unit Tests
- [ ] Run `python -m pytest backend/tests/`
- [ ] Fix any failing tests
- [ ] Remove tests for deleted functionality
- [ ] Add tests for simplified functions
- [ ] Ensure 100% agent flow coverage

### Integration Testing
- [ ] Start backend: `uvicorn api.main:app --reload`
- [ ] Test /health endpoint
- [ ] Test /chat endpoint with various inputs
- [ ] Test /answer endpoint with clarifications
- [ ] Test session persistence
- [ ] Test all cloud provider detections

### Frontend Integration
- [ ] Start frontend: `npm run dev`
- [ ] Test complete chat flow
- [ ] Test clarification forms
- [ ] Test session management
- [ ] Test error handling
- [ ] Verify TAXI payload generation

### Agent Flow Testing
- [ ] Test: "I need a VM" → Clarification flow
- [ ] Test: "Deploy Windows VM in GCP production" → Direct provisioning
- [ ] Test: "Create compute in Azure" → Azure detection
- [ ] Test: "AWS instance for development" → AWS detection
- [ ] Test: Business-first clarification priority
- [ ] Test: Field correction and validation

## Phase 6: Documentation and Finalization

### Update Documentation
- [ ] Update README with simplified architecture
- [ ] Update CLAUDE.md with new patterns
- [ ] Document removed features
- [ ] Document simplified flows
- [ ] Add troubleshooting guide

### Performance Testing
- [ ] Measure response times before/after
- [ ] Check memory usage
- [ ] Verify no performance regression
- [ ] Test with concurrent requests

### Security Review
- [ ] Verify no new vulnerabilities
- [ ] Check input validation still works
- [ ] Ensure no secrets exposed
- [ ] Test rate limiting
- [ ] Verify CORS configuration

## Final Checklist

### Core Functionality Verification
- [ ] Orchestrator routes correctly
- [ ] Clarification shows ALL known fields
- [ ] Business-first flow prioritizes LOB/cost center
- [ ] Compute agent detects all providers
- [ ] GCE specialist generates valid TAXI
- [ ] Sessions persist correctly
- [ ] Frontend works end-to-end
- [ ] Model is still gpt-5-mini
- [ ] Temperature is still 1.0

### Code Quality Metrics
- [ ] 40-50% code reduction achieved
- [ ] All tests passing
- [ ] No lint errors
- [ ] No security issues
- [ ] Improved response times

### Git Operations
- [ ] All changes committed with clear messages
- [ ] No uncommitted files
- [ ] Branch is clean
- [ ] Ready for PR

## Completion
- [ ] Merge backend-simplification to main
- [ ] Delete feature branch
- [ ] Update deployment documentation
- [ ] Notify team of changes

## Important Reminders
1. **DO NOT** change model from gpt-5-mini
2. **DO NOT** change temperature from 1.0  
3. **MAINTAIN** all agent functionality
4. **KEEP** business-first flow
5. **TEST** after each major change
6. **COMMIT** frequently with descriptive messages

## Rollback Commands
```bash
# If something breaks:
git stash
git checkout main
git branch -D backend-simplification
```