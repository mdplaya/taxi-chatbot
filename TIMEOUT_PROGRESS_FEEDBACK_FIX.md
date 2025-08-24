# Timeout and Progress Feedback Fix Implementation

## Issue Summary
**Problem**: LLM operations timeout after 3 seconds causing failures. UI shows static loading with no progress feedback.
**Impact**: Poor user experience, failed operations, no visibility into processing status
**Root Cause**: Hardcoded 3-second timeouts, no streaming/progress infrastructure

## Solution Architecture
Implement Server-Sent Events (SSE) for real-time progress updates while increasing timeouts to production-appropriate values (60-120 seconds).

## Technical Specifications

### Timeout Configuration
```
Current → Target
- LLM calls: 3s → 75s
- Reasoning engine: 5-10s → 60-120s  
- API responses: undefined → 90s
- Clarification: 3s → 60s
```

### SSE Progress Events Structure
```json
{
  "type": "progress",
  "step": "analyzing_request",
  "message": "Understanding your requirements...",
  "agent": "orchestrator",
  "percentage": 25,
  "timestamp": "2024-01-24T10:30:00Z"
}
```

### Progress Steps Flow
1. **Orchestrator**: "Analyzing request..." → "Determining intent..." → "Routing to agent..."
2. **Clarification**: "Checking requirements..." → "Identifying missing fields..." → "Generating questions..."
3. **Compute**: "Extracting VM specs..." → "Detecting cloud provider..." → "Validating requirements..."
4. **GCE Specialist**: "Preparing TAXI payload..." → "Validating configuration..." → "Submitting request..."

## Implementation Components

### 1. Backend Timeout Updates
**Files to modify**:
- `backend/utils/llm_manager.py` - Increase default timeout
- `backend/utils/reasoning.py` - Update reasoning timeouts
- `backend/agents/clarification.py` - Increase LLM timeout
- `backend/.env.example` - Add timeout configurations

### 2. SSE Infrastructure
**New endpoints**:
- `GET /chat/stream` - SSE endpoint for chat with progress
- `GET /session/{id}/progress` - Polling fallback

**Session enhancements**:
- Add `progress_steps: List[ProgressStep]` to ChatSession
- Track current agent and step
- Store timestamps for each transition

### 3. Agent Progress Emission
**Update all agents to emit progress**:
- Add `emit_progress()` method to BaseAgent
- Implement progress tracking in each agent's process flow
- Include percentage completion estimates

### 4. Frontend Real-time Updates
**Components to update**:
- Replace fetch with EventSource for chat
- Add progress message display above loading animation
- Implement reconnection logic for SSE
- Add timeout countdown display

### 5. Error Handling & Fallbacks
- Graceful degradation to polling if SSE fails
- Timeout warnings at 80% of limit
- User option to extend timeout
- Clear error messages for actual timeouts

## Migration Path
1. **Phase 1**: Increase timeouts (immediate relief)
2. **Phase 2**: Add progress tracking to session
3. **Phase 3**: Implement SSE endpoint
4. **Phase 4**: Update agents with progress emission
5. **Phase 5**: Frontend SSE integration

## Configuration

### Environment Variables
```env
# Timeout Configuration (milliseconds)
LLM_TIMEOUT=75000           # 75 seconds for LLM calls
REASONING_TIMEOUT_SIMPLE=60  # 60 seconds for simple reasoning
REASONING_TIMEOUT_COMPLEX=120 # 120 seconds for complex reasoning
API_TIMEOUT=90000            # 90 seconds for API responses
SSE_HEARTBEAT_INTERVAL=30000 # 30 seconds keepalive

# Progress Tracking
ENABLE_PROGRESS_TRACKING=true
PROGRESS_EMIT_INTERVAL=2000  # Emit progress every 2 seconds
PROGRESS_HISTORY_LIMIT=50    # Keep last 50 progress events
```

## Testing Strategy

### Unit Tests
- Test timeout configuration loading
- Test progress event generation
- Test SSE connection handling
- Test fallback to polling

### Integration Tests
- Long-running operation completion
- Progress events during agent transitions
- Timeout edge cases (just under/over limit)
- Network disconnection/reconnection

### Performance Tests
- Memory usage with SSE connections
- CPU impact of progress tracking
- Concurrent SSE connection limits
- Timeout resource cleanup

## Success Metrics
- Zero timeout failures for operations under 60s
- Progress updates every 2-5 seconds
- 100% of users see processing status
- <1% timeout rate for normal operations
- User satisfaction increase for long operations

## Risk Mitigation
- **Risk**: SSE connection limits
  - **Mitigation**: Connection pooling, max connections per user
- **Risk**: Memory leaks from long timeouts
  - **Mitigation**: Proper cleanup, resource monitoring
- **Risk**: Browser SSE compatibility
  - **Mitigation**: Polling fallback, compatibility detection

## Rollback Plan
1. Feature flag for SSE (`USE_SSE_PROGRESS=false`)
2. Revert timeout values via environment variables
3. Frontend falls back to original fetch() automatically
4. No database changes required

## Integration with Agentic System Plan
This implementation advances **Phase 3** (API Enhancements - streaming responses) and **Phase 5** (Real-time Updates - thinking indicators) of the agentic system roadmap.

## Dependencies
- FastAPI SSE support (built-in)
- Browser EventSource API (standard)
- No new external dependencies required

## Estimated Timeline
- **Day 1-2**: Timeout increases + testing
- **Day 3-4**: SSE backend implementation
- **Day 5-6**: Agent progress integration
- **Day 7-8**: Frontend updates
- **Day 9-10**: Testing and refinement

## Notes
- This fix maintains full compatibility with the agentic system architecture
- Progress tracking infrastructure will be reusable for future features
- Valkey integration (when implemented) will persist progress history
- Solution provides immediate relief (timeouts) and long-term improvement (progress)