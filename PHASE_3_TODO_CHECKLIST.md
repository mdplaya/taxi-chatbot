# Phase 3 TODO Checklist: Valkey Integration & Conversational State Management

## 🎯 Execution Checklist

### ✅ Prerequisites
- [ ] Verify Valkey is installed locally (`valkey-cli ping`)
- [ ] Ensure gpt-5-mini model is configured with temperature=1.0
- [ ] Confirm Phase 1 & 2 are complete (16/17 tests passing)
- [ ] Review PHASE_3_VALKEY_IMPLEMENTATION.md for detailed instructions

### 📦 1. Valkey Setup & Configuration

#### 1.1 Local Valkey Setup
- [ ] Start local Valkey server: `valkey-server`
- [ ] Test connection: `valkey-cli ping` (should return PONG)
- [ ] Configure Valkey for persistence: `valkey-cli CONFIG SET appendonly yes`

#### 1.2 Python Dependencies
- [ ] Add to requirements.txt:
  ```
  valkey-py==1.0.0
  ```
- [ ] Run: `pip install valkey-py`
- [ ] Verify import works: `python -c "import valkey"`

#### 1.3 Environment Configuration
- [ ] Create `.env` file from `.env.example`
- [ ] Add Valkey configuration variables:
  ```
  VALKEY_HOST=localhost
  VALKEY_PORT=6379
  VALKEY_AGENT_DB=1
  VALKEY_PASSWORD=
  VALKEY_SSL=false
  VALKEY_CONNECTION_POOL_SIZE=10
  VALKEY_MAX_CONNECTIONS=50
  ```
- [ ] Add memory TTL configurations:
  ```
  AGENT_MEMORY_TTL=86400
  SHORT_TERM_MEMORY_TTL=3600
  LONG_TERM_MEMORY_TTL=604800
  CORRECTION_MEMORY_TTL=2592000
  ```
- [ ] Add learning configurations:
  ```
  CORRECTION_LEARNING_THRESHOLD=0.8
  PATTERN_CONFIDENCE_THRESHOLD=0.7
  CROSS_SESSION_LEARNING=true
  ```

#### 1.4 Docker Configuration
- [ ] Update docker-compose.yml with Valkey service
- [ ] Add Valkey health check
- [ ] Configure Valkey volume for persistence
- [ ] Update API service dependencies
- [ ] Add Valkey environment variables to API service

### 💾 2. Memory Persistence Implementation

#### 2.1 Create Valkey Manager
- [ ] Create `backend/utils/valkey_manager.py`
- [ ] Implement connection pooling (sync and async)
- [ ] Add save_agent_memory() method
- [ ] Add load_agent_memory() method
- [ ] Add save_learned_pattern() method
- [ ] Add get_learned_patterns() method
- [ ] Add save_session() method
- [ ] Add load_session() method
- [ ] Add append_conversation() method
- [ ] Add get_conversation_history() method
- [ ] Add health_check() method
- [ ] Add cleanup_expired_sessions() method
- [ ] Create singleton instance

#### 2.2 Update BaseAgent
- [ ] Import valkey_manager in base_agent.py
- [ ] Implement save_memory() method with Valkey
- [ ] Implement load_memory() method with Valkey
- [ ] Add async support for memory operations
- [ ] Test memory persistence
- [ ] Add error handling and logging

#### 2.3 Create Session Model
- [ ] Create `backend/models/agent_session.py`
- [ ] Define ConversationState enum
- [ ] Create Message model
- [ ] Create AgentMemorySnapshot model
- [ ] Create AgentSession model
- [ ] Add add_message() method
- [ ] Add save_agent_memory() method
- [ ] Add add_correction() method
- [ ] Add update_state() method
- [ ] Add get_recent_context() method
- [ ] Add to_valkey_dict() method
- [ ] Add from_valkey_dict() class method

### 🔄 3. API Transformation

#### 3.1 Update Main API
- [ ] Import valkey_manager in api/main.py
- [ ] Import AgentSession model
- [ ] Replace in-memory sessions dict with Valkey
- [ ] Create get_session() function
- [ ] Create save_session() function
- [ ] Update /chat endpoint to use Valkey sessions
- [ ] Remove form-based patterns
- [ ] Add session persistence after each interaction

#### 3.2 Add Conversational Endpoints
- [ ] Create CorrectionRequest model
- [ ] Implement POST /correct endpoint
- [ ] Create ConfirmRequest model
- [ ] Implement POST /confirm endpoint
- [ ] Create FeedbackRequest model
- [ ] Implement POST /learn endpoint
- [ ] Add request/response models for each endpoint

#### 3.3 Implement Streaming
- [ ] Add SSE support for progress updates
- [ ] Create GET /stream/{session_id} endpoint
- [ ] Implement event_generator for real-time updates
- [ ] Add WebSocket support (optional)
- [ ] Test streaming with frontend

### 🤖 4. Agent Integration

#### 4.1 Orchestrator Agent
- [ ] Add session loading at start
- [ ] Save conversation state after routing
- [ ] Persist user preferences
- [ ] Store routing decisions
- [ ] Save memory after each interaction

#### 4.2 Clarification Agent
- [ ] Load known information from session
- [ ] Save clarified fields to session
- [ ] Persist correction history
- [ ] Store natural language patterns
- [ ] Update session state

#### 4.3 Compute Agent
- [ ] Load extraction patterns from memory
- [ ] Save successful extractions
- [ ] Persist cloud detection patterns
- [ ] Store requirement mappings
- [ ] Learn from corrections

#### 4.4 GCE Specialist Agent
- [ ] Load validation patterns
- [ ] Save successful provisions
- [ ] Store configuration patterns
- [ ] Persist best practices learned
- [ ] Update session with results

### ✅ 5. Testing & Validation

#### 5.1 Unit Tests
- [ ] Create test_valkey_manager.py
- [ ] Test connection and pooling
- [ ] Test save/load operations
- [ ] Test TTL expiration
- [ ] Test pattern storage
- [ ] Test session management
- [ ] Test conversation history
- [ ] Test error handling

#### 5.2 Integration Tests
- [ ] Create test_valkey_integration.py
- [ ] Test agent memory persistence
- [ ] Test cross-session learning
- [ ] Test conversation continuity
- [ ] Test correction learning
- [ ] Test streaming updates
- [ ] Test session cleanup

#### 5.3 End-to-End Tests
- [ ] Test complete VM provisioning flow
- [ ] Test correction and retry flow
- [ ] Test session recovery after restart
- [ ] Test multiple concurrent sessions
- [ ] Test memory limits and cleanup

### 🔒 6. Security & Performance

#### 6.1 Security
- [ ] Add password to Valkey in production
- [ ] Configure SSL/TLS for Valkey
- [ ] Implement input sanitization
- [ ] Add rate limiting for Valkey operations
- [ ] Set up audit logging
- [ ] Review key naming for security

#### 6.2 Performance
- [ ] Configure connection pool sizes
- [ ] Optimize TTL values
- [ ] Implement lazy loading
- [ ] Add caching where appropriate
- [ ] Monitor memory usage
- [ ] Set up Valkey persistence

### 📋 7. Documentation & Cleanup

#### 7.1 Documentation
- [ ] Update README with Valkey setup
- [ ] Document new API endpoints
- [ ] Add memory management guide
- [ ] Create troubleshooting section
- [ ] Update architecture diagram

#### 7.2 Cleanup
- [ ] Remove old in-memory session code
- [ ] Clean up unused imports
- [ ] Remove deprecated endpoints
- [ ] Update error messages
- [ ] Review and update logging

### 🚀 8. Deployment Preparation

#### 8.1 Local Testing
- [ ] Run all tests with Valkey
- [ ] Test with docker-compose
- [ ] Verify memory persistence
- [ ] Check performance metrics
- [ ] Test failure scenarios

#### 8.2 Production Readiness
- [ ] Configure production Valkey settings
- [ ] Set up monitoring
- [ ] Plan backup strategy
- [ ] Document scaling approach
- [ ] Create deployment runbook

## 🎯 Validation Checklist

### System Integrity
- [ ] NO pattern matching in any agent code
- [ ] ALL decisions via LLM reasoning (gpt-5-mini)
- [ ] Temperature set to 1.0 everywhere
- [ ] Pure conversational flow maintained
- [ ] No rules-based logic introduced

### Agent Functionality
- [ ] Orchestrator routes via reasoning only
- [ ] Clarification uses natural conversation
- [ ] Compute detects all clouds via LLM
- [ ] GCE Specialist validates intelligently
- [ ] All agents have memory persistence

### Memory & Learning
- [ ] Sessions persist across restarts
- [ ] Agents learn from corrections
- [ ] Cross-session patterns work
- [ ] Conversation history maintained
- [ ] User preferences remembered

### API & Integration
- [ ] All endpoints use Valkey sessions
- [ ] Streaming responses work
- [ ] Corrections handled properly
- [ ] Confirmation flow works
- [ ] Learning endpoint functional

### Performance & Security
- [ ] Response times acceptable
- [ ] Memory usage optimized
- [ ] No security vulnerabilities
- [ ] Rate limiting in place
- [ ] Audit logging functional

## 📊 Success Criteria

### Must Have (Phase 3 Core)
- [ ] Valkey integration complete
- [ ] Memory persistence working
- [ ] Session management via Valkey
- [ ] BaseAgent save/load functional
- [ ] All agents using Valkey

### Should Have
- [ ] Conversational endpoints added
- [ ] Streaming responses working
- [ ] Cross-session learning active
- [ ] Correction history tracked
- [ ] User preferences stored

### Nice to Have
- [ ] WebSocket support
- [ ] Advanced caching
- [ ] Memory analytics
- [ ] Pattern visualization
- [ ] Auto-cleanup routines

## 🏁 Completion Criteria

### Phase 3 is COMPLETE when:
1. [ ] All MUST HAVE items checked
2. [ ] Tests passing with Valkey
3. [ ] Memory persists across restarts
4. [ ] Sessions managed via Valkey
5. [ ] No pattern matching remains
6. [ ] Pure LLM reasoning maintained
7. [ ] Documentation updated
8. [ ] Code reviewed and cleaned

## 📝 Notes

### Important Reminders
- Model MUST be gpt-5-mini with temperature=1.0
- NO pattern matching or rules-based logic
- ALL decisions through LLM reasoning
- Maintain conversational flow
- Test thoroughly before marking complete

### Common Issues & Solutions
- **Valkey Connection Failed**: Check if Valkey server is running
- **Import Error**: Ensure valkey-py is installed
- **Memory Not Persisting**: Check TTL configurations
- **Session Not Found**: Verify session ID format
- **Slow Performance**: Review connection pool settings

### Resources
- Main implementation doc: PHASE_3_VALKEY_IMPLEMENTATION.md
- Valkey documentation: https://valkey.io/docs/
- Original plan: AGENTIC_SYSTEM_IMPLEMENTATION_PLAN.md

## 🎉 Phase 3 Complete!

Once all items are checked, Phase 3 is complete and the system will have:
- ✅ Persistent memory across sessions
- ✅ Learning from corrections
- ✅ Cross-session pattern recognition
- ✅ Real-time streaming updates
- ✅ Pure conversational flow
- ✅ 100% LLM-based reasoning