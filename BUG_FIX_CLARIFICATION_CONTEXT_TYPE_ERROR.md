# Bug Fix: Clarification Agent Context Type Error

## Bug Report
**Date**: 2025-08-24  
**Severity**: High  
**Component**: Clarification Agent / API Integration  
**Error Type**: AttributeError - Type Mismatch  

### Issue Description
The `get_clarifications` method in `agents/clarification.py` expects a `Dict[str, Any]` for the context parameter, but it's being called with a string in two places in `api/main.py`, causing an AttributeError when the code tries to call `.get()` on the string.

### Error Trace
```
AttributeError: 'str' object has no attribute 'get'
File "/backend/agents/clarification.py", line 165, in _generate_natural_questions
    User's original request: {context.get('raw_request', '')}
```

### User Scenario
User filled out:
- Environment: PROD
- Line of Business: retail  
- Cost Center: (left blank)

The workflow timed out with the error when trying to generate clarification questions for the missing cost center field.

## Root Cause Analysis

### Primary Issue
**Type mismatch in API calls**:
1. `api/main.py:237` - Passing `request.message` (string) as context
2. `api/main.py:314` - Passing `""` (empty string) as context

### Expected vs Actual
- **Expected**: `context: Dict[str, Any]` with keys like `raw_request`, `conversation_history`
- **Actual**: Plain string or empty string being passed

### Impact Analysis
- Breaks clarification flow when missing fields need to be collected
- Affects user experience with 500 Internal Server Error
- Prevents natural conversation flow for gathering missing information

## Solution Design

### Approach
Two-pronged fix for robustness:
1. **Fix at source**: Update API calls to pass proper context dictionaries
2. **Add defensive handling**: Type checking in clarification agent for backwards compatibility

### Implementation Details

#### 1. Fix API Context Passing (`api/main.py`)

**Line 235-237 (Current)**:
```python
clarification_result = await clarification_agent.get_clarifications(
    session.vm_request,
    request.message
)
```

**Line 235-237 (Fixed)**:
```python
clarification_result = await clarification_agent.get_clarifications(
    session.vm_request,
    {
        'raw_request': request.message,
        'conversation_history': session.messages if hasattr(session, 'messages') else [],
        'session_id': session_id
    }
)
```

**Line 312-314 (Current)**:
```python
clarification_result = await clarification_agent.get_clarifications(
    session.vm_request,
    ""
)
```

**Line 312-314 (Fixed)**:
```python
clarification_result = await clarification_agent.get_clarifications(
    session.vm_request,
    {
        'raw_request': session.original_message if hasattr(session, 'original_message') else '',
        'conversation_history': session.messages if hasattr(session, 'messages') else [],
        'session_id': request.session_id,
        'context_type': 'answer_followup'
    }
)
```

#### 2. Add Defensive Type Checking (`agents/clarification.py`)

Add at the beginning of `get_clarifications` method (after line 77):
```python
async def get_clarifications(self, vm_request: VMRequest, context: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """
    Generate natural clarification conversation
    """
    # Defensive type handling for backwards compatibility
    if isinstance(context, str):
        logger.warning(f"Context passed as string instead of dict. Converting: {context[:50]}...")
        context = {
            'raw_request': context if context else '',
            'conversation_history': [],
            'context_type': 'legacy_string'
        }
    elif not isinstance(context, dict):
        logger.error(f"Invalid context type: {type(context)}. Using empty context.")
        context = {
            'raw_request': '',
            'conversation_history': [],
            'context_type': 'error_fallback'
        }
    
    # Rest of the method continues...
```

Also update the method signature to include proper type hints:
```python
from typing import Union, Dict, Any, List

async def get_clarifications(self, vm_request: VMRequest, context: Union[Dict[str, Any], str]) -> Dict[str, Any]:
```

## Testing Plan

### Test Scenarios
1. **Original user scenario**: PROD + retail + blank cost center
2. **Empty context**: Test with empty string context
3. **Full context**: Test with complete context dictionary
4. **Missing history**: Context with raw_request but no conversation_history
5. **Type variations**: Test with None, empty dict, populated dict

### Validation Commands
```bash
# Run from backend directory
PYTHONPATH=/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend

# Test the specific scenario
python -m pytest tests/test_clarification.py::test_get_clarifications_missing_fields -v

# Test all clarification flows
python -m pytest tests/test_clarification.py -v

# Manual API test
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a VM in prod for retail", "session_id": null}'
```

## Implementation Checklist

### Pre-Implementation
- [ ] Backup current working code
- [ ] Review all usages of get_clarifications method
- [ ] Check test coverage for affected code

### Code Changes
- [ ] Update api/main.py line 235-237 with proper context dict
- [ ] Update api/main.py line 312-314 with proper context dict  
- [ ] Add defensive type checking to clarification.py
- [ ] Add proper type hints to method signature
- [ ] Add logging for type conversion warnings

### Testing
- [ ] Test original error scenario (PROD/retail/blank)
- [ ] Test with various context types
- [ ] Run existing test suite
- [ ] Add new tests for context handling
- [ ] Verify no regression in other flows

### Post-Implementation
- [ ] Update documentation if needed
- [ ] Consider adding context builder utility
- [ ] Plan for Compute Agent refactor alignment

## Context Structure Documentation

For future reference and Compute Agent refactor:

### Standard Context Dictionary Structure
```python
context = {
    'raw_request': str,           # Original user message
    'conversation_history': List[Dict], # Previous messages
    'session_id': str,            # Current session ID
    'context_type': str,          # Type of context (optional)
    'user_preferences': Dict,     # User preferences (optional)
    'corrections': List[Dict],    # Previous corrections (optional)
    'timestamp': str              # ISO timestamp (optional)
}
```

## Notes for Agentic System Alignment

This fix maintains compatibility with the completed agentic components:
- ✅ Orchestrator Agent continues to route properly
- ✅ Clarification Agent's natural conversation preserved
- ✅ No impact on BaseAgent inheritance structure
- ✅ Prepares for Compute Agent refactor with proper context structure
- ✅ Error correction system remains functional
- ✅ Learning and memory capabilities unaffected

## Rollback Plan

If issues arise:
1. Revert api/main.py changes
2. Keep defensive handling in clarification.py (safe fallback)
3. Monitor logs for context type warnings
4. Address any downstream impacts

## Success Criteria
- No AttributeError in clarification flow
- User can complete VM request with missing fields
- All existing tests pass
- Proper context passed throughout agent communication
- Clean logs without type conversion warnings (after full migration)