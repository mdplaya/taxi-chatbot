# TODO: Fix Hardcoded Defaults

## Pre-Implementation
- [ ] Create new git branch: `git checkout -b fix-hardcoded-defaults`
- [ ] Review FIX_HARDCODED_DEFAULTS_IMPLEMENTATION.md for full context

## Code Changes

### 1. Orchestrator Updates (`backend/agents/orchestrator.py`)
- [ ] Remove useType default at line 337
  - [ ] Find the else block that sets `extracted["use_type"] = "app"`
  - [ ] Remove or comment out this default assignment
- [ ] Verify OS defaults are kept (Linux→RHEL9, Windows→WIN22)
- [ ] Verify business metadata extraction is preserved (id, costCenter, lineOfBusiness)

### 2. GCE Specialist Updates (`backend/agents/gce_specialist.py`)
- [ ] Remove fallback values (lines 570-590)
  - [ ] Remove hardcoded "appEnvironment": "NONPROD"
  - [ ] Remove hardcoded "os": "LINUX_RHEL8" 
  - [ ] Remove hardcoded "useType": "app"
  - [ ] Remove hardcoded "machineType": "e2-small"
  - [ ] Remove hardcoded "zone": "us-central1-a"
  - [ ] Remove hardcoded "lineOfBusiness": "RETAIL"
  - [ ] Remove hardcoded "costCenter": "00000"
  - [ ] Remove hardcoded "project": "default-project"
  - [ ] Remove hardcoded "id": "vm-instance"
- [ ] Add missing fields check and return clarification needed response
- [ ] Update fallback to only use existing values

### 3. API Updates (`backend/api/main.py`)
- [ ] Update Linux default from RHEL8 to RHEL9 at line 87
- [ ] Update Linux default from RHEL8 to RHEL9 at line 90
- [ ] Verify Windows defaults remain as WIN22

### 4. Test Updates
- [ ] Search for tests expecting hardcoded defaults
- [ ] Update test_clarification.py if needed
- [ ] Update test_gce_specialist.py if needed
- [ ] Update test_orchestrator.py if needed
- [ ] Ensure tests expect OS defaults but not business defaults

## Testing

### 5. Docker Rebuild
- [ ] Stop containers: `docker-compose down`
- [ ] Rebuild containers: `docker-compose up --build`
- [ ] Verify all services start correctly

### 6. Manual Testing
- [ ] Test: "Create a Linux server for qa"
  - [ ] Verify OS defaults to LINUX_RHEL9
  - [ ] Verify environment is NONPROD/qa
  - [ ] Verify system asks for: id (email), costCenter, lineOfBusiness, zone, machineType, useType, project
- [ ] Test: "Deploy a Windows VM"
  - [ ] Verify OS defaults to WINDOWS_22
  - [ ] Verify system asks for missing fields
- [ ] Test: "I need a server"
  - [ ] Verify NO OS default (should ask)
  - [ ] Verify system asks for all fields

### 7. Integration Testing
- [ ] Complete a full flow from request to TAXI payload
- [ ] Verify clarification agent properly gathers all missing fields
- [ ] Verify TAXI payload contains all required fields
- [ ] Check logs for any errors or warnings

## Post-Implementation

### 8. Git Operations
- [ ] Stage all changes: `git add -A`
- [ ] Review changes: `git diff --staged`
- [ ] Commit with descriptive message:
  ```
  git commit -m "Remove hardcoded business defaults, keep OS defaults
  
  - Remove hardcoded business values (costCenter, project, zone, etc)
  - Keep sensible OS defaults (Linux→RHEL9, Windows→WIN22)
  - Ensure missing fields trigger clarification
  - Update tests to match new behavior"
  ```

### 9. Final Verification
- [ ] Run full test suite
- [ ] Verify no regression in existing functionality
- [ ] Document any issues found

### 10. Merge to Main
- [ ] Switch to main: `git checkout main`
- [ ] Merge branch: `git merge fix-hardcoded-defaults`
- [ ] Delete feature branch: `git branch -d fix-hardcoded-defaults`
- [ ] Push to remote if needed

## Rollback (if needed)
- [ ] `git checkout main`
- [ ] `git branch -D fix-hardcoded-defaults`
- [ ] `docker-compose down`
- [ ] `docker-compose up --build`

## Success Criteria
- ✅ System no longer guesses business-critical values
- ✅ OS defaults remain for better UX
- ✅ Missing fields trigger natural clarification questions
- ✅ All tests pass
- ✅ Docker containers rebuild successfully
- ✅ Full flow works end-to-end