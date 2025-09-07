# Error Correction System Fix - Implementation TODO

## Pre-Implementation Checklist
- [ ] Read FIX_ERROR_CORRECTION_SYSTEM.md completely
- [ ] Backup current error_correction.py file
- [ ] Ensure Docker environment is running
- [ ] Have test session ID ready

## Implementation Tasks

### Phase 1: Update ErrorCorrectionSystem Class
**File: `/backend/utils/error_correction.py`**

- [ ] Add datetime import at top of file (line 5)
  ```python
  from datetime import datetime
  ```

- [ ] Add `corrected` property to CorrectionResult class (after line 21)
  - [ ] Add @property decorator
  - [ ] Return self.corrected_text
  - [ ] Add docstring

- [ ] Update `__init__` method (lines 29-30)
  - [ ] Add self.learning_cache = {}
  - [ ] Add self.max_cache_size = 100
  - [ ] Keep existing model assignment

- [ ] Add `detect_and_correct()` method (after line 79)
  - [ ] Make it async
  - [ ] Accept text and context parameters
  - [ ] Return await self.correct(text, context)
  - [ ] Add proper docstring

- [ ] Add `learn_from_feedback()` method (after detect_and_correct)
  - [ ] Make it async
  - [ ] Accept original, corrected, success, error parameters
  - [ ] Implement cache storage with key
  - [ ] Implement size limit enforcement
  - [ ] Add logging without sensitive data
  - [ ] Add proper docstring

### Phase 2: Rebuild and Test

- [ ] Rebuild Docker container
  ```bash
  docker-compose build api
  docker-compose up -d api
  ```

- [ ] Check for startup errors
  ```bash
  docker logs taxi-chatbot-api --tail 50
  ```

- [ ] Test basic chat flow
  ```bash
  curl -X POST http://localhost:8000/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Deploy a Windows 2022 VM in us-east4-a for retail production", "session_id": null}'
  ```

- [ ] Note the session_id from response

### Phase 3: Test Answer Endpoint

- [ ] Test with machine type normalization
  ```bash
  curl -X POST http://localhost:8000/answer \
    -H "Content-Type: application/json" \
    -d '{
      "session_id": "[SESSION_ID_FROM_ABOVE]",
      "answers": {
        "machineType": "4gb n1 std"
      }
    }'
  ```

- [ ] Verify no AttributeError in logs
- [ ] Verify "4gb n1 std" normalizes to "n1-standard-4"

### Phase 4: Test Other Fields

- [ ] Test appEnvironment normalization
  - [ ] "production" → "PROD"
  - [ ] "nonprod" → "NONPROD"

- [ ] Test os normalization
  - [ ] "windows 2022" → "WINDOWS_22"
  - [ ] "rhel 8" → "LINUX_RHEL8"

- [ ] Test useType normalization
  - [ ] "application" → "app"
  - [ ] "database" → "database"

### Phase 5: Verify Memory Management

- [ ] Monitor memory usage before changes
  ```bash
  docker stats taxi-chatbot-api
  ```

- [ ] Submit 150+ corrections to test cache limit
- [ ] Verify memory doesn't grow unbounded
- [ ] Check logs for cache_size in learning messages

### Phase 6: Integration Testing

- [ ] Complete full VM provisioning flow
- [ ] Test with various input variations:
  - [ ] "4gb n1 std"
  - [ ] "n1 standard with 4gb"
  - [ ] "n1-standard-4"
  - [ ] "4 gb n1 standard"

- [ ] Verify all fields populate correctly in final TAXI payload

### Phase 7: Documentation

- [ ] Document the fix in commit message
- [ ] Update any API documentation if needed
- [ ] Add comments in code for future maintainers

## Verification Checklist

### Functional Verification
- [ ] No AttributeError for detect_and_correct
- [ ] No AttributeError for learn_from_feedback  
- [ ] Field access correction_result.corrected works
- [ ] Machine type normalization works

### Performance Verification
- [ ] Response times acceptable (<2s)
- [ ] Memory usage stable
- [ ] No blocking operations
- [ ] Cache size limited to 100

### Error Handling
- [ ] Graceful handling of invalid inputs
- [ ] Proper error messages to users
- [ ] No sensitive data in logs
- [ ] Learning continues despite errors

## Rollback Plan (If Needed)

If critical issues occur:

1. [ ] In clarification.py line 531:
   - Change `detect_and_correct` to `correct`

2. [ ] In clarification.py lines 571 and 969:
   - Comment out the entire `learn_from_feedback` call

3. [ ] Rebuild and redeploy:
   ```bash
   docker-compose build api
   docker-compose up -d api
   ```

## Success Metrics

- ✅ Zero AttributeError exceptions in logs
- ✅ Answer endpoint returns 200 status
- ✅ Machine type "4gb n1 std" → "n1-standard-4"
- ✅ All field normalizations working
- ✅ Memory usage < 500MB after 100 requests
- ✅ Learning cache size stays at or below 100

## Notes

- Keep FIX_ERROR_CORRECTION_SYSTEM.md for reference
- Test in staging before production if available
- Monitor for 24 hours after deployment
- Consider adding unit tests in future sprint

## Sign-off

- [ ] Development complete
- [ ] Testing complete
- [ ] Documentation complete
- [ ] Ready for production

---
Created: 2025-09-05
Priority: HIGH - Blocking user answer flow
Estimated Time: 1-2 hours
Actual Time: ___