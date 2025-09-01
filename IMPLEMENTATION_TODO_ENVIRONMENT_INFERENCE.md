# Implementation TODO - Fix Environment Inference Issue

## Pre-Implementation Checklist
- [ ] Create new git branch: `fix/environment-inference`
- [ ] Review current test coverage for affected components
- [ ] Back up current orchestrator.py and gce_specialist.py files
- [ ] Ensure Docker environment is running for testing

## Phase 1: GCE Specialist Enhancement

### Task 1.1: Update Extraction Prompt in GCE Specialist
**File**: `backend/agents/gce_specialist.py`
**Method**: `_extract_vm_requirements` (Lines 155-210)

- [ ] Locate the extraction prompt starting at line 155
- [ ] Find the section "Apply intelligent corrections:" around line 161
- [ ] Add new ENVIRONMENT INFERENCE section after line 170:
  ```python
  ENVIRONMENT INFERENCE (with automatic subtype):
  - Development keywords: "development", "dev", "develop", "sandbox", "demo", "poc", 
    "proof of concept", "prototype", "experimental", "training", "learning", "education"
    → appEnvironment: NONPROD, appEnvironmentSubtype: dev
  
  - Testing keywords: "testing", "test", "unit test", "integration", "staging", 
    "stage", "pre-prod", "preprod", "uat", "user acceptance"
    → appEnvironment: NONPROD, appEnvironmentSubtype: test
  
  - QA keywords: "qa", "quality", "quality assurance", "validation", "verification"
    → appEnvironment: NONPROD, appEnvironmentSubtype: qa
  
  - Performance keywords: "performance", "perf", "load test", "stress test", 
    "benchmark", "capacity"
    → appEnvironment: NONPROD, appEnvironmentSubtype: perf
  
  - Production keywords: "production", "prod", "live", "operational", "operations", 
    "critical", "customer-facing", "public"
    → appEnvironment: PROD
  ```

- [ ] Add OS DEFAULTS section:
  ```python
  OS DEFAULTS:
  - "Linux" or "linux server" without specific distro → LINUX_RHEL9
  - "Windows" or "windows server" without version → WINDOWS_22
  - "server" alone without OS specified → LINUX_RHEL9
  - "RHEL" or "Red Hat" without version → LINUX_RHEL9
  ```

- [ ] Add USE TYPE INFERENCE section:
  ```python
  USE TYPE INFERENCE:
  - Web/Frontend keywords: "web", "website", "frontend", "ui" → useType: app
  - Database keywords: "database", "db", "mysql", "postgres", "storage" → useType: database
  - Backend/API keywords: "api", "backend", "service", "microservice" → useType: app
  - Default if unclear → useType: app
  ```

- [ ] Keep all existing corrections below the new sections
- [ ] Ensure the JSON return structure remains unchanged (lines 191-209)

### Task 1.2: Test GCE Specialist Changes
- [ ] Start Docker containers: `docker-compose up --build`
- [ ] Test extraction with: "Create a Linux server for development"
- [ ] Verify extraction returns: appEnvironment: NONPROD, appEnvironmentSubtype: dev, os: LINUX_RHEL9
- [ ] Check logs for extraction results

## Phase 2: Orchestrator Fast-Path Enhancement

### Task 2.1: Enhance Environment Detection
**File**: `backend/agents/orchestrator.py`
**Location**: Lines 227-263 (Fast-path environment detection)

- [ ] Locate the environment detection section around line 227
- [ ] Replace simple environment detection with comprehensive logic:
  ```python
  # Comprehensive environment detection with subtype
  env_keywords = {
      'PROD': ['production', 'prod', 'live', 'operational', 'operations', 
               'critical', 'customer-facing', 'public'],
      'NONPROD': {
          'dev': ['development', 'dev', 'develop', 'sandbox', 'demo', 'poc', 
                  'proof of concept', 'prototype', 'experimental', 'training', 
                  'learning', 'education'],
          'test': ['testing', 'test', 'unit test', 'integration', 'staging', 
                   'stage', 'pre-prod', 'preprod', 'uat', 'user acceptance'],
          'qa': ['qa', 'quality', 'quality assurance', 'validation', 'verification'],
          'perf': ['performance', 'perf', 'load test', 'stress test', 
                   'benchmark', 'capacity']
      }
  }
  ```

- [ ] Implement detection logic:
  ```python
  # Check for PROD first
  for keyword in env_keywords['PROD']:
      if keyword in user_lower:
          extracted["environment"] = "PROD"
          break
  else:
      # Check for NONPROD with subtype
      for subtype, keywords in env_keywords['NONPROD'].items():
          for keyword in keywords:
              if keyword in user_lower:
                  extracted["environment"] = "NONPROD"
                  extracted["appEnvironmentSubtype"] = subtype
                  break
          if extracted.get("environment"):
              break
  ```

### Task 2.2: Enhance OS Detection in Fast-Path
- [ ] Add enhanced OS detection after environment detection:
  ```python
  # Enhanced OS detection with defaults
  if 'linux' in user_lower:
      if 'rhel' in user_lower or 'red hat' in user_lower:
          if '8' in user_lower:
              extracted["os"] = "LINUX_RHEL8"
          elif '9' in user_lower:
              extracted["os"] = "LINUX_RHEL9"
          else:
              extracted["os"] = "LINUX_RHEL9"  # Default RHEL version
      elif not any(x in user_lower for x in ['ubuntu', 'centos', 'debian']):
          extracted["os"] = "LINUX_RHEL9"  # Default Linux
  elif 'windows' in user_lower:
      if '2019' in user_lower or '19' in user_lower:
          extracted["os"] = "WINDOWS_19"
      elif '2022' in user_lower or '22' in user_lower:
          extracted["os"] = "WINDOWS_22"
      else:
          extracted["os"] = "WINDOWS_22"  # Default Windows
  elif 'server' in user_lower and not extracted.get("os"):
      extracted["os"] = "LINUX_RHEL9"  # Default for generic "server"
  ```

- [ ] Add use type detection:
  ```python
  # Detect use type
  if any(x in user_lower for x in ['database', 'db', 'mysql', 'postgres', 'storage']):
      extracted["use_type"] = "database"
  elif any(x in user_lower for x in ['web', 'frontend', 'ui', 'api', 'backend', 'service']):
      extracted["use_type"] = "app"
  ```

### Task 2.3: Update Fast-Path Logging
- [ ] Add logging for extracted environment and subtype
- [ ] Log OS inference when defaults are applied
- [ ] Ensure extracted fields are logged at INFO level

## Phase 3: Integration Testing

### Task 3.1: Basic Test Cases
- [ ] Test: "Create a Linux server for development"
  - Expected: No environment question, NONPROD/dev inferred
- [ ] Test: "Deploy a Windows VM for testing"
  - Expected: No environment question, NONPROD/test inferred
- [ ] Test: "Need a production server"
  - Expected: No environment question, PROD inferred
- [ ] Test: "Set up a staging environment"
  - Expected: No environment question, NONPROD/test inferred

### Task 3.2: Edge Cases
- [ ] Test: "Create a VM" (no environment keywords)
  - Expected: Still asks for environment
- [ ] Test: "Development and testing server"
  - Expected: NONPROD/dev (first match)
- [ ] Test: "Linux RHEL server for demo"
  - Expected: NONPROD/dev, respects RHEL
- [ ] Test: "Windows 2019 for production"
  - Expected: PROD, WINDOWS_19

### Task 3.3: Complex Scenarios
- [ ] Test: "Create a load testing environment with Linux"
  - Expected: NONPROD/perf, LINUX_RHEL9
- [ ] Test: "Deploy customer-facing application server"
  - Expected: PROD, useType: app
- [ ] Test: "Set up a MySQL database for QA"
  - Expected: NONPROD/qa, useType: database
- [ ] Test: "Sandbox for training purposes"
  - Expected: NONPROD/dev
- [ ] Test: "UAT server for client validation"
  - Expected: NONPROD/test

## Phase 4: Validation & Verification

### Task 4.1: Verify Agent Integrity
- [ ] Confirm Orchestrator still routes correctly
- [ ] Verify Clarification Agent is called less frequently
- [ ] Ensure Compute Agent passes context properly
- [ ] Check GCE Specialist generates correct TAXI payloads

### Task 4.2: Check System Behavior
- [ ] Verify gpt-5-mini model is still used
- [ ] Confirm temperature is 1.0
- [ ] Check that conversational flow is maintained
- [ ] Ensure corrections are shown to user

### Task 4.3: Performance Testing
- [ ] Measure response time (should be unchanged)
- [ ] Check memory usage
- [ ] Verify no new errors in logs
- [ ] Monitor Docker container health

## Phase 5: Documentation & Cleanup

### Task 5.1: Update Documentation
- [ ] Update CLAUDE.md with new inference behavior
- [ ] Document new environment keywords
- [ ] Add examples of intelligent inference
- [ ] Update troubleshooting guide

### Task 5.2: Code Review Preparation
- [ ] Run linters on modified files
- [ ] Check for any hardcoded values
- [ ] Ensure consistent code style
- [ ] Remove any debug logging

### Task 5.3: Commit Changes
- [ ] Stage all modified files
- [ ] Write comprehensive commit message
- [ ] Include test results in commit message
- [ ] Reference the issue being fixed

## Phase 6: Deployment Preparation

### Task 6.1: Final Testing
- [ ] Run full test suite
- [ ] Test with real user scenarios
- [ ] Verify all agents working correctly
- [ ] Check error handling

### Task 6.2: Merge and Deploy
- [ ] Create pull request to main branch
- [ ] Include test evidence in PR description
- [ ] Get code review if required
- [ ] Merge after approval
- [ ] Monitor production logs post-deployment

## Success Criteria Checklist
- [ ] Environment correctly inferred for obvious cases
- [ ] No unnecessary clarification questions
- [ ] OS defaults working (LINUX_RHEL9 for Linux)
- [ ] Use type inference functional
- [ ] All test cases passing
- [ ] No performance degradation
- [ ] Logs show intelligent corrections

## Rollback Plan
If issues occur:
1. [ ] Git checkout previous commit
2. [ ] Rebuild Docker containers
3. [ ] Verify system returns to previous behavior
4. [ ] Document issues encountered
5. [ ] Plan fixes for next iteration

## Test Commands Reference
```bash
# Start services
docker-compose up --build

# Test simple development request
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a Linux server for development", "session_id": null}'

# Test production request
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Deploy a production Windows server", "session_id": null}'

# Test staging environment
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Set up staging environment", "session_id": null}'

# Test with no environment specified
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a VM", "session_id": null}'
```

## Notes
- Always test changes incrementally
- Keep original code commented for easy rollback
- Monitor logs closely during testing
- Document any unexpected behavior
- Consider A/B testing if possible

## Time Estimate
- Phase 1: 45 minutes
- Phase 2: 30 minutes
- Phase 3: 60 minutes
- Phase 4: 30 minutes
- Phase 5: 20 minutes
- Phase 6: 30 minutes
- **Total: ~3.5 hours**

## Risk Mitigation
- Low risk changes (prompt modifications only)
- Extensive testing before deployment
- Clear rollback plan
- No structural changes to agents