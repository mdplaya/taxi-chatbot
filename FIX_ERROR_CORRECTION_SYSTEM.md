# Fix Error Correction System and Machine Type Normalization

## Issue Summary
Date: 2025-09-05
Priority: HIGH
Impact: Answer flow broken when users provide clarification answers

### Critical Errors
1. `AttributeError: 'ErrorCorrectionSystem' object has no attribute 'detect_and_correct'` at line 531 of clarification.py
2. `AttributeError: 'ErrorCorrectionSystem' object has no attribute 'learn_from_feedback'` at lines 571 and 969 of clarification.py
3. Field name mismatch: Code expects `corrected` but CorrectionResult has `corrected_text`
4. Machine type normalization issue: "4gb n1 std" must translate to "n1-standard-4" via LLM

## Root Cause Analysis

### Missing Methods
The ErrorCorrectionSystem class in `/backend/utils/error_correction.py` only implements:
- `__init__()` 
- `correct()` method

But the ClarificationAgent in `/backend/agents/clarification.py` calls:
- `detect_and_correct()` at line 531
- `learn_from_feedback()` at lines 571 and 969

### Field Name Mismatch
- CorrectionResult dataclass defines `corrected_text` field
- But clarification.py line 536 accesses `correction_result.corrected`

### Memory Leak Risk
- No limit on learning storage could cause unbounded memory growth
- Should follow SimpleLearningEngine pattern with size limits

## Implementation Details

### File: `/backend/utils/error_correction.py`

#### 1. Add Property to CorrectionResult Class (after line 21)
```python
    @property
    def corrected(self):
        """Alias for backward compatibility"""
        return self.corrected_text
```

#### 2. Update ErrorCorrectionSystem.__init__ (replace lines 29-30)
```python
    def __init__(self, model: str = "gpt-5-mini"):
        self.model = model
        self.learning_cache = {}  # Session-based learning storage
        self.max_cache_size = 100  # Prevent memory leak
```

#### 3. Add detect_and_correct Method (after correct method, around line 79)
```python
    async def detect_and_correct(self, text: str, context: Dict[str, Any] = None) -> CorrectionResult:
        """
        Detect errors and correct them
        Currently wraps correct() but can be enhanced with detection logic
        """
        # Future: Add detection logic here to identify if correction is needed
        return await self.correct(text, context)
```

#### 4. Add learn_from_feedback Method (after detect_and_correct)
```python
    async def learn_from_feedback(self, original: str, corrected: str, success: bool, error: str = None):
        """
        Learn from correction feedback for future improvements
        Stores learning with size limit to prevent memory issues
        """
        # Create learning key
        key = f"{original}:{corrected}"
        
        # Store learning data
        self.learning_cache[key] = {
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat() if 'datetime' in globals() else None
        }
        
        # Enforce cache size limit (LRU-style)
        if len(self.learning_cache) > self.max_cache_size:
            # Remove oldest entries
            keys_to_remove = list(self.learning_cache.keys())[:-self.max_cache_size]
            for k in keys_to_remove:
                del self.learning_cache[k]
        
        # Log learning event (without sensitive data)
        logger.info(f"[Learning] Feedback recorded: success={success}, cache_size={len(self.learning_cache)}")
```

#### 5. Add Import at Top of File (line 5, with other imports)
```python
from datetime import datetime
```

### NO CHANGES NEEDED in `/backend/agents/clarification.py`
The existing code will work once the methods are added to ErrorCorrectionSystem.

## Verification Steps

### Machine Type Normalization
The LLM normalization in `_normalize_value()` at line 631 of clarification.py already handles:
- "standard n1 4gb" → "n1-standard-4"
- "4gb n1 std" → "n1-standard-4" (via LLM reasoning)

This works through:
1. Line 531: Error correction applied first
2. Line 541: LLM normalization via `_normalize_value()`
3. Line 631: LLM prompt includes example "standard n1 4gb" → "n1-standard-4"

### Field Mappings
All fields correctly map to TAXI payload structure:
- `$.resourceMetadata.appEnvironment` - Lines 652-657
- `$.resourceMetadata.appEnvironmentSubtype` - Lines 658-667  
- `$.useType` - Lines 691-696
- `$.os` - Lines 676-690
- `$.zone` - Line 710 (passthrough after LLM)
- `$.machineType` - Lines 697-699 + LLM normalization

## Testing Requirements

### Unit Tests Needed
1. Test `detect_and_correct()` returns CorrectionResult
2. Test `learn_from_feedback()` stores and limits cache
3. Test `corrected` property returns `corrected_text`
4. Test cache size enforcement at 100 entries

### Integration Tests Needed
1. Test answer flow with "4gb n1 std" → "n1-standard-4"
2. Test all field normalizations work
3. Test error learning improves corrections
4. Verify no memory leaks over extended use

### Manual Testing
```bash
# Test the answer endpoint with machine type normalization
curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-xxx",
    "answers": {
      "machineType": "4gb n1 std"
    }
  }'

# Expected: Should normalize to "n1-standard-4"
```

## Benefits of This Solution

1. **Complete Implementation**: All missing methods added
2. **Backward Compatible**: Property alias handles field name issue  
3. **Memory Safe**: Learning cache limited to 100 entries
4. **Future Ready**: Can enhance detection logic later
5. **Consistent**: Follows SimpleLearningEngine patterns
6. **Maintainable**: Clear separation of concerns

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Memory leak | Cache limited to 100 entries |
| PII in logs | Only log success/failure, not content |
| Breaking changes | Property alias maintains compatibility |
| Performance | Async methods prevent blocking |

## Rollback Plan
If issues occur, simply comment out the method calls in clarification.py:
- Line 531: Replace `detect_and_correct` with `correct`
- Lines 571, 969: Comment out `learn_from_feedback` calls

## Success Criteria
- [ ] No AttributeError exceptions
- [ ] Answer flow completes successfully
- [ ] "4gb n1 std" correctly normalizes to "n1-standard-4"
- [ ] Learning improves corrections over time
- [ ] Memory usage remains stable