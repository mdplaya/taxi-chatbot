# TODO: Execute Pydantic Enum Validation Fix

## Pre-Execution Checklist
- [ ] Read FIX_PYDANTIC_ENUM_VALIDATION.md completely
- [ ] Ensure you're in the correct repository directory
- [ ] Verify Docker is running
- [ ] Back up current work (if any)

## Execution Steps

### Step 1: Create New Branch
```bash
git checkout main
git pull origin main
git checkout -b fix/pydantic-enum-validation
```

### Step 2: Add Normalization Helper Function
- [ ] Open `backend/api/main.py`
- [ ] Add the `normalize_vm_field_value` function after imports (around line 20)
- [ ] Verify function handles all enum fields properly

### Step 3: Fix setattr Locations in main.py
- [ ] Fix Line 218: Add normalization before setattr
- [ ] Fix Line 357: Add normalization before setattr  
- [ ] Fix Line 723: Add normalization before setattr
- [ ] Verify all three locations use `normalize_vm_field_value`

### Step 4: Fix VMRequest Creation from Dict
- [ ] Fix Line 475: Normalize dict values before creating VMRequest
- [ ] Ensure the normalized_vm dict is created properly
- [ ] Test with sample dict data

### Step 5: Update GCE Specialist
- [ ] Open `backend/agents/gce_specialist.py`
- [ ] Find `_extract_vm_requirements` method (around line 150)
- [ ] Add enum value requirements to the extraction prompt (after line 244)
- [ ] Verify prompt emphasizes exact enum values

### Step 6: Test Changes Locally
```bash
# Test the normalization function
cd backend
python3 -c "
from api.main import normalize_vm_field_value
print(normalize_vm_field_value('os', 'linux'))  # Should print: LINUX_RHEL8
print(normalize_vm_field_value('appEnvironment', 'nonprod'))  # Should print: NONPROD
print(normalize_vm_field_value('useType', 'application'))  # Should print: app
"
```

### Step 7: Rebuild Docker Containers
```bash
# Stop existing containers
docker-compose down

# Rebuild with changes
docker-compose build --no-cache

# Start containers
docker-compose up -d

# Check logs for errors
docker-compose logs -f api
```

### Step 8: Test the Fix

#### Test 1: Direct API Test
```bash
# Create a session
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a Linux VM", "session_id": null}'

# Save the session_id from response, then test answer endpoint
curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "answers": {
      "os": "linux",
      "appEnvironment": "nonprod",
      "appEnvironmentSubtype": "dev",
      "lineOfBusiness": "retail",
      "costCenter": "12345",
      "project": "test-project",
      "zone": "us-east4-a",
      "useType": "app",
      "machineType": "e2-small",
      "id": "test@example.com"
    }
  }'
```

#### Test 2: Frontend Test
1. Open http://localhost:3000
2. Type: "I need a Linux VM for development"
3. Fill in clarification form with lowercase/mixed values
4. Verify no 500 errors occur

#### Test 3: Edge Cases
```bash
# Test with Windows variations
curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "answers": {
      "os": "Windows Server 2022"
    }
  }'

# Test with RHEL variations
curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "answers": {
      "os": "RHEL 9"
    }
  }'
```

### Step 9: Verify Fix
- [ ] Check API logs for any validation errors
- [ ] Verify normalized values in session data
- [ ] Test complete flow from chat to provisioning
- [ ] Ensure no regression in existing functionality

### Step 10: Commit Changes
```bash
# Stage all changes
git add backend/api/main.py
git add backend/agents/gce_specialist.py

# Commit with descriptive message
git commit -m "Fix Pydantic enum validation errors in VMRequest

- Add normalize_vm_field_value helper function
- Normalize values before setattr in 4 locations
- Normalize dict values before VMRequest creation
- Update GCE specialist to return proper enum values
- Handles variations like 'linux' -> 'LINUX_RHEL8'

Fixes #500 error in /answer endpoint"

# Push branch
git push origin fix/pydantic-enum-validation
```

### Step 11: Create Pull Request
```bash
# Create PR using GitHub CLI
gh pr create \
  --title "Fix Pydantic enum validation errors" \
  --body "## Summary
- Fixes 500 error when processing clarification answers
- Adds centralized enum value normalization
- Handles all common variations of user input

## Test Results
- Tested with lowercase values: ✅
- Tested with mixed case: ✅
- Tested with variations (RHEL 8, Windows 2022): ✅
- Full flow test: ✅

Fixes validation error: \`Input should be 'LINUX_RHEL8', 'LINUX_RHEL9', 'WINDOWS_19' or 'WINDOWS_22'\`"
```

### Step 12: Post-Merge Cleanup
```bash
# After PR is merged
git checkout main
git pull origin main
git branch -d fix/pydantic-enum-validation
```

## Verification Checklist
- [ ] No Pydantic validation errors in logs
- [ ] `/answer` endpoint responds with 200
- [ ] Clarification flow completes successfully
- [ ] VM provisioning receives proper enum values
- [ ] All tests pass

## Rollback Instructions (if needed)
```bash
# If issues occur, revert to main
git checkout main
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Notes
- The normalization function is defensive - it returns values as-is if not recognized
- This fix is backward compatible with existing data
- No database migrations required
- Performance impact is minimal (simple string operations)

## Success Criteria
✅ No more `pydantic_core._pydantic_core.ValidationError` in logs
✅ Clarification answers process successfully regardless of case/format
✅ All enum values properly validated before storage
✅ Complete user flow works end-to-end