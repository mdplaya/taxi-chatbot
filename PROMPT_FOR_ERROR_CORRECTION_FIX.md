# Prompt to Execute Error Correction System Fix

## Context Setting Prompt

Use this prompt after clearing context to execute the error correction system fix:

---

## Prompt:

I need to fix the error correction system in my TAXI chatbot application. I have two documentation files that contain the complete implementation plan:

1. **FIX_ERROR_CORRECTION_SYSTEM.md** - Contains the detailed analysis, root causes, and exact code changes needed
2. **ERROR_CORRECTION_TODO.md** - Contains the step-by-step implementation checklist

Please:

1. First, read both files:
   - `/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/FIX_ERROR_CORRECTION_SYSTEM.md`
   - `/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/ERROR_CORRECTION_TODO.md`

2. Then implement the fix by:
   - Adding the missing methods to `/backend/utils/error_correction.py`
   - Following the exact specifications in the documentation
   - Ensuring the memory limit of 100 entries is enforced
   - Adding the `corrected` property for backward compatibility

3. After implementation:
   - Rebuild the Docker container
   - Test that the answer endpoint works without AttributeError
   - Verify that "4gb n1 std" normalizes to "n1-standard-4"
   - Confirm all field normalizations work correctly

The main issues to fix are:
- Missing `detect_and_correct()` method causing AttributeError at line 531 of clarification.py
- Missing `learn_from_feedback()` method causing AttributeError at lines 571 and 969 of clarification.py  
- Field name mismatch where code expects `corrected` but dataclass has `corrected_text`
- Ensuring machine type inputs like "4gb n1 std" normalize to "n1-standard-4"

Please follow the implementation exactly as specified in the documentation files, including the memory management safeguards and logging practices.

---

## Alternative Shorter Prompt (if you want minimal context):

Please read and implement the error correction system fix documented in:
- `/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/FIX_ERROR_CORRECTION_SYSTEM.md` (analysis and solution)
- `/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/ERROR_CORRECTION_TODO.md` (implementation checklist)

The fix adds missing methods `detect_and_correct()` and `learn_from_feedback()` to ErrorCorrectionSystem class in `/backend/utils/error_correction.py`, plus a `corrected` property for field compatibility. Follow the exact implementation in the documentation.

---

## Verification Command After Implementation:

After the fix is complete, use this to verify:

```bash
# Test that answer endpoint works with machine type normalization
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a VM", "session_id": null}'

# Get session_id from response, then test answer:
curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "answers": {
      "machineType": "4gb n1 std"
    }
  }'
```

Expected: Should work without errors and normalize "4gb n1 std" to "n1-standard-4"