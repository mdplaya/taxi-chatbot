# Fix Hardcoded Defaults Implementation Plan

## Problem Statement
When a user says "Create a Linux server for qa", the system is guessing/hardcoding values instead of asking for clarification:
- costCenter: '00000'
- project: 'gcp-nonprod-project'
- id: 'unknown@example.com'
- machineType: 'e2-standard-4'
- zone: 'us-central1-a'
- lineOfBusiness: 'RETAIL'

## Solution Overview
Remove inappropriate hardcoded defaults while keeping sensible OS defaults. Ensure missing fields trigger clarification questions.

## Git Workflow
```bash
# 1. Create and checkout new branch
git checkout -b fix-hardcoded-defaults

# 2. Make all changes (see implementation steps below)

# 3. Test the changes

# 4. Commit changes
git add -A
git commit -m "Remove hardcoded business defaults, keep OS defaults

- Remove hardcoded business values (costCenter, project, zone, etc)
- Keep sensible OS defaults (Linux→RHEL9, Windows→WIN22)
- Ensure missing fields trigger clarification
- Update tests to match new behavior"

# 5. After testing is complete, merge to main
git checkout main
git merge fix-hardcoded-defaults
git branch -d fix-hardcoded-defaults
```

## Implementation Steps

### 1. Update Orchestrator (`backend/agents/orchestrator.py`)

**Line 337 - Remove useType default:**
```python
# OLD CODE (around line 337):
else:
    # Default use type if unclear
    extracted["use_type"] = "app"

# NEW CODE:
else:
    # Don't default use_type - let clarification handle it
    pass  # or just remove the else block entirely
```

**Keep these OS defaults (lines 263-278):**
- Keep the Linux → LINUX_RHEL9 default
- Keep the Windows → WINDOWS_22 default
- These are sensible UX defaults

**Keep business metadata extraction (lines 221-244):**
- Email extraction (id field)
- Cost center extraction (5-digit numbers)
- Line of business extraction
- These should be extracted if present, but NOT defaulted

### 2. Update GCE Specialist (`backend/agents/gce_specialist.py`)

**Lines 570-590 - Remove ALL fallback values:**
```python
# OLD CODE (around lines 570-590):
else:
    # Fallback to direct mapping with safe defaults
    self.logger.warning("[GCE] Using fallback payload building")
    filtered_dict = {k: v for k, v in vm_dict.items() if v is not None}
    taxi_payload = {
        "cloud": "gcp",
        "resourceType": "compute",
        "action": "create",
        "appEnvironment": filtered_dict.get("appEnvironment", "NONPROD"),
        "os": filtered_dict.get("os", "LINUX_RHEL8"),
        "useType": filtered_dict.get("useType", "app"),
        "machineType": filtered_dict.get("machineType", "e2-small"),
        "zone": filtered_dict.get("zone", "us-central1-a"),
        "lineOfBusiness": filtered_dict.get("lineOfBusiness", "RETAIL"),
        "costCenter": str(filtered_dict.get("costCenter", "00000")),
        "project": filtered_dict.get("project", "default-project"),
        "id": filtered_dict.get("id", "vm-instance")
    }

# NEW CODE:
else:
    # Fallback to direct mapping WITHOUT defaults
    self.logger.warning("[GCE] Using fallback payload building")
    filtered_dict = {k: v for k, v in vm_dict.items() if v is not None}
    
    # Check for required fields
    missing_fields = []
    required_fields = ["appEnvironment", "os", "useType", "machineType", "zone", 
                      "lineOfBusiness", "costCenter", "project", "id"]
    
    for field in required_fields:
        if field not in filtered_dict or filtered_dict[field] is None:
            missing_fields.append(field)
    
    if missing_fields:
        self.logger.error(f"[GCE] Missing required fields for TAXI payload: {missing_fields}")
        # Return error or trigger clarification
        return {
            "success": False,
            "needs_clarification": True,
            "missing_fields": missing_fields
        }
    
    taxi_payload = {
        "cloud": "gcp",
        "resourceType": "compute",
        "action": "create",
        **filtered_dict  # Use only the values we have
    }
    
    # Ensure costCenter is string if present
    if "costCenter" in taxi_payload:
        taxi_payload["costCenter"] = str(taxi_payload["costCenter"])
```

### 3. Update API (`backend/api/main.py`)

**Lines 87 and 90 - Update Linux default to RHEL9:**
```python
# OLD CODE (around lines 86-90):
if "9" in value_lower:
    return "LINUX_RHEL9"
else:
    return "LINUX_RHEL8"  # Default to RHEL8
# Handle generic Linux
elif "linux" in value_lower:
    return "LINUX_RHEL8"  # Default Linux

# NEW CODE:
if "9" in value_lower:
    return "LINUX_RHEL9"
elif "8" in value_lower:
    return "LINUX_RHEL8"
else:
    return "LINUX_RHEL9"  # Default to RHEL9
# Handle generic Linux
elif "linux" in value_lower:
    return "LINUX_RHEL9"  # Default Linux to RHEL9
```

### 4. Update Test Files

Search for test files that expect hardcoded defaults and update them:
- `backend/tests/test_clarification.py`
- `backend/tests/test_gce_specialist.py`
- `backend/tests/test_orchestrator.py`

Update assertions to NOT expect hardcoded business values, but still expect OS defaults.

## Testing Instructions

### 1. Rebuild Docker Containers
```bash
# Stop existing containers
docker-compose down

# Rebuild with new changes
docker-compose up --build

# Or if you need to force rebuild:
docker-compose build --no-cache
docker-compose up
```

### 2. Test the Fix
```bash
# Test case 1: "Create a Linux server for qa"
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a Linux server for qa", "session_id": null}'

# Expected: Should ask for missing fields (id, costCenter, lineOfBusiness, zone, machineType, useType, project)
# OS should default to LINUX_RHEL9
# Environment should be NONPROD with subtype qa
```

### 3. Verify Clarification Flow
The system should:
1. Extract OS=LINUX_RHEL9 (default for Linux)
2. Extract environment=NONPROD/qa
3. NOT guess costCenter, project, zone, lineOfBusiness, machineType, useType, or id
4. Ask user for all missing fields
5. Accept user's answers and proceed with provisioning

## Expected Behavior After Fix

| Field | Before | After |
|-------|--------|-------|
| OS (Linux) | LINUX_RHEL8 | LINUX_RHEL9 (kept default) |
| OS (Windows) | WINDOWS_22 | WINDOWS_22 (kept default) |
| useType | "app" (guessed) | Ask user |
| costCenter | "00000" (fake) | Ask user |
| project | "default-project" (fake) | Ask user |
| zone | "us-central1-a" (guessed) | Ask user |
| lineOfBusiness | "RETAIL" (guessed) | Ask user |
| machineType | "e2-small" (guessed) | Ask user |
| id | "vm-instance" (fake) | Ask user for email |

## Architecture Notes

### Separation of Concerns
- **Orchestrator**: Handles business metadata extraction (id, costCenter, lineOfBusiness)
- **Compute Agent**: Routes to cloud specialists
- **GCE Specialist**: Handles technical VM configuration
- **Clarification Agent**: Gathers missing information naturally

### Key Principles
1. Only apply sensible defaults (OS versions)
2. Never guess business-critical values
3. Always ask for missing required fields
4. Maintain conversational flow

## Rollback Plan
If issues are found:
```bash
git checkout main
git branch -D fix-hardcoded-defaults
docker-compose down
docker-compose up --build
```