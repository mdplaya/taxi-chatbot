# LLM Hybrid System Implementation TODOs

## Project: Add True LLM/Agentic Functionality with Offline Fallback
**Created**: 2025-08-23  
**Status**: Planning Complete, Ready for Implementation

---

## 📋 Master TODO List

### Phase 1: Core Infrastructure (Foundation)
- [ ] **Create LLM Manager Module** (`backend/utils/llm_manager.py`)
  - [ ] Check OpenAI API key availability on init
  - [ ] Implement mode detection method (returns "online" or "offline")
  - [ ] Add 5-minute cache for mode status to avoid repeated API checks
  - [ ] Implement 3-second timeout for all LLM calls
  - [ ] Create async wrapper methods for Marvin AI calls
  - [ ] Add fallback handling when LLM unavailable
  - [ ] Include retry logic with exponential backoff

### Phase 2: Data Model Updates
- [ ] **Expand Machine Types** (`backend/models/taxi_models.py`)
  - [ ] Remove current limited MachineType enum (only has 4 types)
  - [ ] Add E2 Series (Cost Optimized):
    - [ ] E2_MICRO = "e2-micro"
    - [ ] E2_SMALL = "e2-small"  
    - [ ] E2_MEDIUM = "e2-medium"
    - [ ] E2_STANDARD_2 = "e2-standard-2"
    - [ ] E2_STANDARD_4 = "e2-standard-4"
    - [ ] E2_STANDARD_8 = "e2-standard-8"
  - [ ] Add N1 Series (Previous Gen):
    - [ ] N1_STANDARD_1 = "n1-standard-1"
    - [ ] N1_STANDARD_2 = "n1-standard-2"
    - [ ] N1_STANDARD_4 = "n1-standard-4"
    - [ ] N1_STANDARD_8 = "n1-standard-8"
  - [ ] Add N2 Series (Balanced):
    - [ ] N2_STANDARD_2 = "n2-standard-2"
    - [ ] N2_STANDARD_4 = "n2-standard-4"
    - [ ] N2_STANDARD_8 = "n2-standard-8"
    - [ ] N2_HIGHMEM_2 = "n2-highmem-2"
    - [ ] N2_HIGHMEM_4 = "n2-highmem-4"
  - [ ] Add C2 Series (Compute Optimized):
    - [ ] C2_STANDARD_4 = "c2-standard-4"
    - [ ] C2_STANDARD_8 = "c2-standard-8"

### Phase 3: Agent Enhancements (4-Agent Architecture)

#### 3.1 Orchestrator Agent (`backend/agents/orchestrator.py`)
- [ ] Import LLMManager at top of file
- [ ] Initialize LLMManager in __init__ method
- [ ] Create `analyze_user_request_llm()` function:
  - [ ] Add @marvin.fn decorator
  - [ ] Define proper return type hints
  - [ ] Include docstring with examples
- [ ] Keep existing `analyze_user_request()` as `analyze_user_request_pattern()`
- [ ] Enhance pattern matching in offline version:
  - [ ] Add more intent keywords
  - [ ] Support partial matches
  - [ ] Add confidence scoring
- [ ] Modify main `process()` method:
  - [ ] Check LLM mode from manager
  - [ ] Route to appropriate function based on mode
  - [ ] Add mode to return dict
- [ ] Maintain conversation history for context

#### 3.2 Compute Agent (`backend/agents/compute.py`)
- [ ] Import LLMManager
- [ ] Create `extract_vm_requirements_llm()`:
  - [ ] Use @marvin.fn for entity extraction
  - [ ] Support natural language variations
  - [ ] Handle context from previous messages
- [ ] Rename current function to `extract_vm_requirements_pattern()`
- [ ] Enhance pattern matching:
  - [ ] Add fuzzy matching for "RHEL 8"/"RHEL8"/"rhel-8"
  - [ ] Support partial machine type matches ("n1" → "n1-standard-1")
  - [ ] Add all new machine type patterns
  - [ ] Include common synonyms ("small" → "e2-small")
  - [ ] Support "compute optimized" → C2 series mapping
- [ ] Update `process()` method for mode switching
- [ ] Return extraction confidence score

#### 3.3 Clarification Agent (`backend/agents/clarification.py`)
- [ ] Import LLMManager
- [ ] Create `generate_natural_questions()` for online mode:
  - [ ] Use LLM to create conversational questions
  - [ ] Consider context from chat history
  - [ ] Generate follow-up questions dynamically
- [ ] Keep template questions for offline mode
- [ ] Add `get_clarifications()` mode switching:
  - [ ] Check LLM availability
  - [ ] Use natural or template questions accordingly
- [ ] Support both form-based and conversational responses
- [ ] Track which fields have been asked about

#### 3.4 GCE Specialist Agent (`backend/agents/gce_specialist.py`)
- [ ] Update machine type validation for new types
- [ ] Ensure TAXI payload uses correct enum values
- [ ] Add validation for new instance families
- [ ] No LLM needed (deterministic provisioning)

### Phase 4: API Layer Updates

#### 4.1 Main API (`backend/api/main.py`)
- [ ] Import LLMManager at startup
- [ ] Initialize and check mode on app startup
- [ ] Update ChatResponse model:
  - [ ] Add `mode: Literal["online", "offline"]` field
  - [ ] Include in OpenAPI schema
- [ ] Modify `/chat` endpoint:
  - [ ] Get current mode from LLMManager
  - [ ] Include mode in all responses
  - [ ] Add mode to session data
- [ ] Update `/health` endpoint:
  - [ ] Include current mode
  - [ ] Show LLM availability status
- [ ] Add `/status` endpoint for mode checking
- [ ] Implement graceful degradation on LLM failure

### Phase 5: Frontend Updates

#### 5.1 React UI (`frontend/app/page.tsx`)
- [ ] Create StatusBadge component:
  ```tsx
  - [ ] Green "ONLINE" for LLM mode
  - [ ] Yellow "OFFLINE" for pattern mode
  - [ ] Fixed position (top-right corner)
  - [ ] Include tooltip with explanation
  ```
- [ ] Update state management:
  - [ ] Add `systemMode` state variable
  - [ ] Parse mode from API responses
  - [ ] Update badge on mode change
- [ ] Modify chat interface:
  - [ ] Show mode-specific hints
  - [ ] Adjust expectations based on mode
- [ ] Add visual feedback for mode switches
- [ ] Include reconnection attempt indicator

### Phase 6: Configuration & Environment

- [ ] Create `.env.example`:
  ```
  - [ ] OPENAI_API_KEY=sk-...
  - [ ] LLM_TIMEOUT=3000
  - [ ] LLM_CACHE_TTL=300
  ```
- [ ] Update `.gitignore`:
  - [ ] Ensure .env is excluded
  - [ ] Add any new config files
- [ ] Create configuration documentation
- [ ] Add setup instructions to README

### Phase 7: Testing Suite

#### 7.1 Unit Tests
- [ ] Test LLMManager:
  - [ ] Mode detection with/without API key
  - [ ] Cache behavior
  - [ ] Timeout handling
- [ ] Test each agent in both modes:
  - [ ] Orchestrator intent detection
  - [ ] Compute requirement extraction
  - [ ] Clarification question generation
- [ ] Test pattern matching enhancements:
  - [ ] "RHEL 8" variations
  - [ ] "n1" partial matches
  - [ ] All new machine types

#### 7.2 Integration Tests
- [ ] Full chat flow in online mode
- [ ] Full chat flow in offline mode
- [ ] Mode switching during conversation
- [ ] API response validation
- [ ] Frontend mode indicator updates

#### 7.3 Edge Cases
- [ ] LLM API timeout scenarios
- [ ] Invalid API key handling
- [ ] Mode cache expiration
- [ ] Concurrent request handling
- [ ] Network failure recovery

### Phase 8: Documentation

- [ ] Update README.md:
  - [ ] LLM setup instructions
  - [ ] Mode explanation
  - [ ] Troubleshooting guide
- [ ] Update CLAUDE.md:
  - [ ] New architecture details
  - [ ] Pattern matching rules
  - [ ] LLM integration notes
- [ ] Create CONTRIBUTING.md:
  - [ ] How to add new patterns
  - [ ] Testing requirements
  - [ ] PR guidelines

### Phase 9: Security & Performance

- [ ] Security measures:
  - [ ] Validate API key format
  - [ ] Sanitize all user inputs
  - [ ] No API keys in logs
  - [ ] Rate limiting for LLM calls
  - [ ] Session security review
- [ ] Performance optimization:
  - [ ] Implement request caching
  - [ ] Add connection pooling
  - [ ] Monitor LLM latency
  - [ ] Optimize pattern matching
  - [ ] Add performance metrics

### Phase 10: Deployment & Monitoring

- [ ] Pre-deployment checklist:
  - [ ] All tests passing
  - [ ] Documentation complete
  - [ ] Security review done
  - [ ] Performance benchmarks met
- [ ] Deployment steps:
  - [ ] Update environment variables
  - [ ] Deploy backend changes
  - [ ] Deploy frontend changes
  - [ ] Verify mode detection
- [ ] Post-deployment:
  - [ ] Monitor error rates
  - [ ] Track mode usage statistics
  - [ ] Collect user feedback
  - [ ] Plan iterative improvements

---

## 🎯 Success Metrics

### Functional Requirements
- ✅ "RHEL 8" and "RHEL8" both extract correctly
- ✅ "n1" alone maps to n1-standard-1
- ✅ All GCP instance types supported
- ✅ Natural conversation in online mode
- ✅ Reliable fallback in offline mode
- ✅ Clear mode indication to users

### Non-Functional Requirements
- ✅ LLM response time < 3 seconds
- ✅ Pattern matching response time < 100ms
- ✅ 99.9% uptime with fallback
- ✅ No security vulnerabilities
- ✅ Complete test coverage
- ✅ Clear documentation

---

## 📝 Implementation Notes

### Critical Points
1. **Always prefer LLM when available** - Better user experience
2. **Graceful degradation** - Never fail completely
3. **User transparency** - Always show current mode
4. **4-agent architecture** - Maintain separation of concerns
5. **Performance first** - Cache aggressively, timeout quickly

### Known Challenges
- Marvin AI decorator syntax may need adjustment
- OpenAI API rate limits need monitoring
- Pattern matching won't catch all variations
- Mode switching mid-conversation needs testing
- Frontend state management complexity

### Dependencies
- marvin==2.3.0 (already installed)
- openai==1.6.1 (already installed)
- No new dependencies needed

---

## 📅 Timeline Estimate
- Phase 1-2: 2 hours (Foundation)
- Phase 3-4: 4 hours (Core Logic)
- Phase 5: 2 hours (Frontend)
- Phase 6-7: 3 hours (Testing)
- Phase 8-10: 2 hours (Polish)
- **Total: ~13 hours**

---

## ✅ Completion Tracking
**Started**: Not yet  
**Target**: TBD  
**Actual**: TBD  

### Phase Completion
- [ ] Phase 1: Core Infrastructure
- [ ] Phase 2: Data Models
- [ ] Phase 3: Agents
- [ ] Phase 4: API
- [ ] Phase 5: Frontend
- [ ] Phase 6: Configuration
- [ ] Phase 7: Testing
- [ ] Phase 8: Documentation
- [ ] Phase 9: Security
- [ ] Phase 10: Deployment

---

**END OF IMPLEMENTATION PLAN**