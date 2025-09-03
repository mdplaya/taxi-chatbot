# Current Issue Summary - TAXI Chatbot

## Main Problem
The system is not properly asking for clarification when fields are missing. Instead, the LLM (OpenAI API) is generating/guessing values for missing fields during the extraction phase.

## What We Fixed
1. **Removed hardcoded defaults** from GCE specialist fallback logic (lines 570-590)
2. **Updated Linux defaults** from RHEL8 to RHEL9 across codebase
3. **Removed default use_type** assignment in orchestrator
4. **Added validation** to check for missing required fields

## Remaining Issue
When the user says "Create a Linux server for qa", the system should:
- ✅ Default OS to LINUX_RHEL9 (this works)
- ✅ Extract environment as NONPROD/qa (this works)
- ❌ Ask for missing fields: id, costCenter, lineOfBusiness, zone, machineType, useType, project

**But instead**: The LLM generates fake values for all missing fields, so no clarification questions are asked.

## Root Cause
The GCE Specialist's `_extract_vm_requirements` method uses LLM reasoning (OpenAI API) to extract fields from the request. The LLM is being too "helpful" and generating reasonable-sounding values instead of marking them as missing.

## Location of Issue
- **File**: `backend/agents/gce_specialist.py`
- **Method**: `_extract_vm_requirements` (lines 150-320)
- **Problem**: LLM prompt asks to extract fields, and the LLM generates values instead of returning null for missing fields

## Potential Solutions
1. **Modify LLM prompt** to explicitly instruct NOT to generate values
2. **Use pattern matching** instead of LLM for field extraction
3. **Add validation layer** after LLM extraction to verify fields are actually present in input
4. **Switch to a two-phase approach**: first detect what's present, then extract values

## Testing Command
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a Linux server for qa", "session_id": null}'
```

## Expected Behavior
Should ask for: id (email), costCenter, lineOfBusiness, zone, machineType, useType, project

## Current Behavior  
Returns immediately with all fields filled with generated values

## Files Already Modified
- `backend/agents/orchestrator.py` - Removed use_type default
- `backend/agents/gce_specialist.py` - Removed fallback defaults
- `backend/api/main.py` - Updated Linux defaults to RHEL9
- `backend/tests/test_compute.py` - Updated tests for RHEL9
- `backend/tests/test_compute_simple.py` - Updated tests for RHEL9

## Next Steps
Need to fix the LLM extraction logic to properly identify missing fields instead of generating values for them.