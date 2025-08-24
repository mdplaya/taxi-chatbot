# TODO: Clarification Context Type Error Fix

## Execution Checklist

### Phase 1: Code Changes (Priority: CRITICAL)

#### Task 1: Fix API Context Passing - Line 237
- [ ] Open `/backend/api/main.py`
- [ ] Locate line 235-237 (in provision error handling)
- [ ] Replace `request.message` with proper context dict:
  ```python
  {
      'raw_request': request.message,
      'conversation_history': session.messages if hasattr(session, 'messages') else [],
      'session_id': session_id
  }
  ```
- [ ] Verify indentation and syntax

#### Task 2: Fix API Context Passing - Line 314
- [ ] In same file, locate line 312-314 (in answer_clarification endpoint)
- [ ] Replace `""` with proper context dict:
  ```python
  {
      'raw_request': session.original_message if hasattr(session, 'original_message') else '',
      'conversation_history': session.messages if hasattr(session, 'messages') else [],
      'session_id': request.session_id,
      'context_type': 'answer_followup'
  }
  ```
- [ ] Verify indentation and syntax

#### Task 3: Add Defensive Type Checking
- [ ] Open `/backend/agents/clarification.py`
- [ ] Add import at top: `from typing import Union, Dict, Any, List`
- [ ] Update method signature for `get_clarifications` to include `Union[Dict[str, Any], str]`
- [ ] Add type checking code after line 77 (beginning of method)
- [ ] Add logging for type conversion warnings
- [ ] Ensure proper error handling

### Phase 2: Testing (Priority: HIGH)

#### Task 4: Test Original Error Scenario  
- [ ] Start backend server
- [ ] Submit chat: "I need a VM in prod for retail"
- [ ] Fill clarification form with PROD, retail, leave cost center blank
- [ ] Verify no AttributeError occurs
- [ ] Check response is appropriate

#### Task 5: Run Automated Tests
- [ ] Navigate to backend directory
- [ ] Run: `PYTHONPATH=. python -m pytest tests/test_clarification.py -v`
- [ ] Ensure all tests pass
- [ ] Document any failures

#### Task 6: Test Edge Cases
- [ ] Test with completely empty session
- [ ] Test with null context
- [ ] Test with populated conversation history
- [ ] Test rapid successive clarifications

### Phase 3: Verification (Priority: MEDIUM)

#### Task 7: Check for Other Callers
- [ ] Search codebase for other `get_clarifications` calls
- [ ] Verify no other locations need updating
- [ ] Document any findings

#### Task 8: Verify Agent Communication
- [ ] Test Orchestrator → Clarification flow
- [ ] Test Clarification → Compute flow  
- [ ] Ensure context properly propagated
- [ ] Check logs for warnings

### Phase 4: Documentation (Priority: LOW)

#### Task 9: Update Tests
- [ ] Add test for string context handling
- [ ] Add test for dict context handling
- [ ] Add test for invalid context types
- [ ] Ensure backward compatibility tests

#### Task 10: Document Context Structure
- [ ] Create context structure documentation
- [ ] Add to developer notes
- [ ] Update inline comments
- [ ] Prepare notes for Compute Agent refactor

## Execution Order

1. **IMMEDIATE**: Tasks 1-3 (Code changes)
2. **AFTER CODE**: Tasks 4-6 (Testing)
3. **VALIDATION**: Tasks 7-8 (Verification)
4. **CLEANUP**: Tasks 9-10 (Documentation)

## Commands Reference

```bash
# Start backend server
cd /Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend
PYTHONPATH=. python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
PYTHONPATH=. python -m pytest tests/test_clarification.py -v

# Test API manually
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a VM in prod for retail", "session_id": null}'

# Search for other usages
grep -r "get_clarifications" --include="*.py"
```

## Rollback Commands

```bash
# If issues arise, rollback with git
git diff api/main.py agents/clarification.py
git checkout -- api/main.py  # To revert if needed
```

## Success Indicators

✅ No AttributeError in logs  
✅ Clarification flow completes successfully  
✅ All tests passing  
✅ Context properly structured in logs  
✅ No type conversion warnings after implementation  

## Time Estimate

- Code Changes: 10 minutes
- Testing: 15 minutes  
- Verification: 10 minutes
- Documentation: 5 minutes
- **Total: ~40 minutes**

## Risk Assessment

- **Low Risk**: Defensive handling ensures backward compatibility
- **Medium Risk**: Session attribute access needs validation
- **Mitigation**: Test thoroughly before considering complete

## Notes

- Keep backup of working code before changes
- Monitor logs closely during testing
- This fix aligns with agentic system goals
- Prepares for future Compute Agent refactor
- Maintains conversational flow integrity