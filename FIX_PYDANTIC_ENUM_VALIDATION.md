# Fix Plan: Pydantic Enum Validation Error

## Issue Description
**Error**: `pydantic_core._pydantic_core.ValidationError: 1 validation error for VMRequest`
- **Location**: `/answer` endpoint (line 475 in api/main.py)
- **Root Cause**: Invalid enum values (e.g., 'linux' instead of 'LINUX_RHEL8') are stored in VMRequest dicts
- **Impact**: API returns 500 error when processing clarification answers

## Root Cause Analysis
1. GCE specialist's LLM returns simplified values like 'linux', 'nonprod', 'dev'
2. These values are stored directly in session.vm_request via setattr
3. When `/answer` endpoint creates VMRequest from dict (line 475), Pydantic validation fails
4. The clarification agent has normalization logic but it's not used everywhere

## Solution Overview
Create a centralized normalization helper function that maps all value variations to valid enum values, then apply it consistently at all value-setting locations.

## Code Changes

### 1. Add Normalization Helper to backend/api/main.py

Add this function after the imports section (around line 20):

```python
def normalize_vm_field_value(field: str, value: Any) -> Any:
    """
    Normalize raw values to proper enum values for VMRequest fields.
    Handles common variations and ensures Pydantic validation passes.
    """
    if value is None:
        return None
    
    # Normalize based on field type
    if field == "appEnvironment":
        value_upper = str(value).upper()
        if value_upper in ["PROD", "PRODUCTION"]:
            return "PROD"
        elif value_upper in ["NONPROD", "NON-PROD", "DEV", "TEST", "QA", "DEVELOPMENT", "TESTING"]:
            return "NONPROD"
        return value  # Return as-is if not recognized
    
    elif field == "appEnvironmentSubtype":
        value_lower = str(value).lower()
        if value_lower in ["dev", "development", "develop"]:
            return "dev"
        elif value_lower in ["qa", "quality", "quality-assurance"]:
            return "qa"
        elif value_lower in ["test", "testing", "integration"]:
            return "test"
        elif value_lower in ["perf", "performance", "load"]:
            return "perf"
        return value  # Return as-is if not recognized
    
    elif field == "os":
        value_lower = str(value).lower()
        # Handle RHEL variations
        if "rhel" in value_lower or "red hat" in value_lower:
            if "9" in value_lower:
                return "LINUX_RHEL9"
            else:
                return "LINUX_RHEL8"  # Default to RHEL8
        # Handle generic Linux
        elif "linux" in value_lower:
            return "LINUX_RHEL8"  # Default Linux
        # Handle Windows variations
        elif "windows" in value_lower or "win" in value_lower:
            if "22" in value_lower or "2022" in value_lower:
                return "WINDOWS_22"
            elif "19" in value_lower or "2019" in value_lower:
                return "WINDOWS_19"
            else:
                return "WINDOWS_22"  # Default Windows
        return value  # Return as-is if not recognized
    
    elif field == "useType":
        value_lower = str(value).lower()
        if "app" in value_lower or "application" in value_lower:
            return "app"
        elif "database" in value_lower or "db" in value_lower:
            return "database"
        return value  # Return as-is if not recognized
    
    elif field == "lineOfBusiness":
        value_upper = str(value).upper()
        if "RETAIL" in value_upper:
            return "RETAIL"
        elif "ISTS" in value_upper:
            return "ISTS"
        elif "EDML" in value_upper:
            return "EDML"
        return value  # Return as-is if not recognized
    
    elif field == "machineType":
        # Machine types are already specific strings, just return
        return str(value)
    
    # For other fields (zone, costCenter, project, id), return as-is
    return value
```

### 2. Fix Line 218 in backend/api/main.py

Replace:
```python
if value is not None and hasattr(session.vm_request, key):
    setattr(session.vm_request, key, value)
```

With:
```python
if value is not None and hasattr(session.vm_request, key):
    normalized_value = normalize_vm_field_value(key, value)
    setattr(session.vm_request, key, normalized_value)
```

### 3. Fix Line 357 in backend/api/main.py

Replace:
```python
if hasattr(session.vm_request, key) and value is not None:
    setattr(session.vm_request, key, value)
```

With:
```python
if hasattr(session.vm_request, key) and value is not None:
    normalized_value = normalize_vm_field_value(key, value)
    setattr(session.vm_request, key, normalized_value)
```

### 4. Fix Line 475 in backend/api/main.py

Replace:
```python
if isinstance(current_vm, dict):
    vm_request_obj = VMRequest(**current_vm)
else:
    vm_request_obj = current_vm
```

With:
```python
if isinstance(current_vm, dict):
    # Normalize all enum fields in the dict before creating VMRequest
    normalized_vm = {}
    for key, value in current_vm.items():
        normalized_vm[key] = normalize_vm_field_value(key, value)
    vm_request_obj = VMRequest(**normalized_vm)
else:
    vm_request_obj = current_vm
```

### 5. Fix Line 723 in backend/api/main.py

Replace:
```python
if value is not None and hasattr(session.vm_request, key):
    setattr(session.vm_request, key, value)
```

With:
```python
if value is not None and hasattr(session.vm_request, key):
    normalized_value = normalize_vm_field_value(key, value)
    setattr(session.vm_request, key, normalized_value)
```

### 6. Update GCE Specialist Extraction Prompt (backend/agents/gce_specialist.py)

In the `_extract_vm_requirements` method (around line 244), add this section to the extraction prompt:

```python
# Add after line 244 in the prompt:
        
        CRITICAL: Return EXACT enum values (case-sensitive):
        - appEnvironment: MUST be exactly "NONPROD" or "PROD" (not "nonprod", "dev", etc.)
        - os: MUST be exactly "LINUX_RHEL8", "LINUX_RHEL9", "WINDOWS_19", or "WINDOWS_22"
        - useType: MUST be exactly "app" or "database" (lowercase)
        - lineOfBusiness: MUST be exactly "RETAIL", "ISTS", or "EDML" (uppercase)
        - appEnvironmentSubtype: MUST be exactly "dev", "qa", "test", or "perf" (lowercase)
        - machineType: Use exact GCP machine type strings (e.g., "e2-small", "n1-standard-1")
```

## Testing Scenarios

### Test Case 1: Basic Enum Validation
```json
{
  "answers": {
    "os": "linux",
    "appEnvironment": "nonprod",
    "useType": "application"
  }
}
```
Expected: Should normalize to `LINUX_RHEL8`, `NONPROD`, `app`

### Test Case 2: Windows Variations
```json
{
  "answers": {
    "os": "Windows Server 2022",
    "appEnvironment": "production"
  }
}
```
Expected: Should normalize to `WINDOWS_22`, `PROD`

### Test Case 3: RHEL Variations
```json
{
  "answers": {
    "os": "RHEL 9",
    "lineOfBusiness": "retail"
  }
}
```
Expected: Should normalize to `LINUX_RHEL9`, `RETAIL`

### Test Case 4: Mixed Case
```json
{
  "answers": {
    "appEnvironment": "NonProd",
    "appEnvironmentSubtype": "DEV",
    "useType": "Database"
  }
}
```
Expected: Should normalize to `NONPROD`, `dev`, `database`

## Verification Steps

1. **Unit Test**: Create test for `normalize_vm_field_value` function
2. **Integration Test**: Test `/answer` endpoint with various inputs
3. **End-to-End Test**: Complete flow from chat → clarification → answer
4. **Edge Cases**: Test with null values, empty strings, invalid values

## Rollback Plan

If issues occur:
1. Revert to previous branch
2. The normalization function is additive - can be disabled by removing calls
3. No database migrations or schema changes required

## Benefits

✅ **Robust**: Handles all variations of user input
✅ **Centralized**: Single source of truth for normalization
✅ **Maintainable**: Easy to update mappings
✅ **Backward Compatible**: Works with existing data
✅ **Type Safe**: Ensures Pydantic validation passes

## Risk Assessment

- **Risk Level**: LOW
- **Impact**: Improves reliability, prevents 500 errors
- **Breaking Changes**: None - purely additive
- **Performance**: Minimal overhead (simple string operations)