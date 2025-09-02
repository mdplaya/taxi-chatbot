# Fix Duplicate Questions - Implementation Plan

## STATUS: COMPLETED ✅
All implementation phases have been successfully completed. The duplicate questions issue has been resolved.

## Issue Summary (RESOLVED)
Users were seeing duplicate questions for the same field (particularly lineOfBusiness) because:
1. ~~GCE Specialist extracts ALL fields including business metadata~~ **Fixed: GCE now only handles technical fields**
2. ~~ClarificationAgent's `asked_fields` tracking is lost between API calls~~ **Fixed: Session persistence implemented**
3. ~~No deduplication between agents~~ **Fixed: Deduplication logic added**

## Solution Architecture

### Responsibility Division
- **Orchestrator**: Extracts obvious business metadata from initial request
- **Clarification Agent**: Asks for missing business metadata via conversation
- **GCE Specialist**: Handles only technical VM fields (zone, os, machineType, etc.)

### Business Metadata Fields (to be handled by Orchestrator/Clarification)
- `$.options.requestor.id` (user email)
- `$.resourceMetadata.costCenter` (5-digit billing code)
- `$.resourceMetadata.lineOfBusiness` (RETAIL/ISTS/EDML)
- `$.resourceMetadata.appEnvironment` (PROD/NONPROD)
- `$.resourceMetadata.appEnvironmentSubtype` (dev/qa/test/perf)

## Implementation Tasks

### Setup
- [x] Create new git branch: `fix-duplicate-questions`
- [x] Switch to the new branch

### Phase 1: Enhance Orchestrator Agent
**File: `backend/agents/orchestrator.py`**

- [x] Add business metadata extraction logic in fast path (around line 217)
  - [x] Add email regex pattern for `requestor.id` extraction
  - [x] Add 5-digit number regex for `costCenter` extraction
  - [x] Add line of business keyword mapping:
    ```python
    lob_patterns = {
        'RETAIL': ['retail', 'storefront', 'store', 'shop', 'commerce'],
        'ISTS': ['ists', 'it services', 'technology services', 'it support'],
        'EDML': ['edml', 'data management', 'data lake', 'analytics']
    }
    ```
  - [x] Enhance existing environment detection (lines 256-286)
  - [x] Ensure all extracted business metadata is added to `extracted` dict

- [x] Update context passed to compute agent (around line 324)
  - [x] Include extracted business metadata in `extracted_requirements`
  - [x] Add new field `business_metadata` with extracted values

- [x] Update LLM reasoning prompt (around line 425)
  - [x] Add business metadata extraction to the prompt
  - [x] Include examples of business field extraction

### Phase 2: Update GCE Specialist Agent
**File: `backend/agents/gce_specialist.py`**

- [x] Modify `_extract_vm_requirements` method (lines 163-296)
  - [x] Update LLM prompt to EXCLUDE business metadata fields
  - [x] Remove from extraction prompt (lines 215-226):
    - appEnvironment
    - appEnvironmentSubtype
    - lineOfBusiness
    - costCenter
    - id
  - [x] Remove from expected JSON output (lines 237-246)
  - [x] Keep ONLY technical fields:
    - zone
    - os
    - useType
    - machineType
    - project

- [x] Update context merging logic (lines 266-279)
  - [x] Accept business metadata from context
  - [x] Merge business fields from `context.get('business_metadata', {})`
  - [x] Preserve business fields passed from Orchestrator

- [x] Update clarification generation (lines 282-294)
  - [x] Check context for already-extracted business fields
  - [x] Filter out questions for fields present in context
  - [x] Ensure no duplicate questions for business metadata

### Phase 3: Fix ClarificationAgent Session Persistence
**File: `backend/api/main.py`**

- [x] Update ClarificationAgent instantiation (lines 348, 440, 561)
  - [x] Pass session's `asked_fields` via context
  - [x] Retrieve `asked_fields` from session data if exists

- [x] Modify session handling
  - [x] Store `asked_fields` in ChatSession or AgentSession
  - [x] Pass to ClarificationAgent via context:
    ```python
    context = {
        'raw_request': message,
        'session_id': session_id,
        'asked_fields': session.get('asked_fields', set()),
        ...
    }
    ```

**File: `backend/agents/clarification.py`**

- [x] Update `__init__` method (lines 29-46)
  - [x] Accept `asked_fields` from context if provided
  - [x] Initialize from context or create new set

- [x] Update `_generate_natural_questions` (lines 191-289)
  - [x] Use context-provided `asked_fields` if available
  - [x] Return updated `asked_fields` for session storage

### Phase 4: Update Context Flow
**File: `backend/api/main.py`**

- [x] Update orchestrator result handling (lines 254-386)
  - [x] Extract business metadata from orchestrator result
  - [x] Merge into VMRequest before passing to specialists
  - [x] Pass business metadata in context to compute agent

- [x] Update compute agent context (lines 256-282)
  - [x] Include business metadata from orchestrator
  - [x] Pass through to GCE specialist

- [x] Update GCE specialist context (lines 278-325)
  - [x] Ensure business metadata is included
  - [x] Pass to clarification agent if needed

### Phase 5: Add Deduplication Logic
**File: `backend/agents/gce_specialist.py`**

- [x] Enhance question filtering (lines 282-294)
  - [x] Create a set of already-known fields from context
  - [x] Filter `clarifications_needed` to exclude known fields
  - [x] Add field-based deduplication:
    ```python
    known_fields = set(extracted_fields.keys())
    if context.get('business_metadata'):
        known_fields.update(context['business_metadata'].keys())
    
    filtered_questions = []
    for question in clarifications_needed:
        if isinstance(question, dict):
            field = question.get('field')
            if field not in known_fields:
                filtered_questions.append(question)
    ```

### Phase 6: Testing

- [x] Create test script `backend/tests/test_no_duplicate_questions.py`
  - [x] Test orchestrator extracts business metadata
  - [x] Test GCE specialist doesn't extract business fields
  - [x] Test clarification agent doesn't ask for extracted fields
  - [x] Test full flow with partial business metadata

- [x] Manual testing scenarios:
  - [x] "I want a VM in GCP for our retail app"
  - [x] "Create a production server with cost center 12345"
  - [x] "Deploy a test instance for ISTS team"
  - [x] Verify only ONE question per field

### Phase 7: Docker and Deployment

- [x] Rebuild Docker containers:
  ```bash
  docker-compose down
  docker-compose build --no-cache
  docker-compose up
  ```

- [x] Test in Docker environment:
  - [x] Frontend at http://localhost:3000
  - [x] Backend at http://localhost:8000
  - [x] Verify no duplicate questions in UI

### Phase 8: Commit and Merge

- [x] Run all tests:
  ```bash
  cd backend
  python -m pytest tests/
  ```

- [x] Commit changes:
  ```bash
  git add -A
  git commit -m "Fix duplicate questions by moving business metadata extraction to Orchestrator

  - Orchestrator now extracts business metadata (id, costCenter, lineOfBusiness, appEnvironment, appEnvironmentSubtype)
  - GCE Specialist focuses only on technical VM fields
  - ClarificationAgent tracks asked_fields across session
  - Added deduplication logic to prevent duplicate questions
  - Improved separation of concerns between agents"
  ```

- [ ] Create pull request
- [ ] Merge to main after approval

## Success Criteria

1. ✅ No duplicate questions for any field
2. ✅ Business metadata extracted by Orchestrator
3. ✅ Technical fields handled by specialists
4. ✅ Session persistence for asked_fields
5. ✅ Clean separation of concerns
6. ✅ All tests passing
7. ✅ Docker containers rebuilt and working

## Rollback Plan

If issues arise:
1. Checkout main branch: `git checkout main`
2. Delete feature branch: `git branch -D fix-duplicate-questions`
3. Rebuild containers: `docker-compose build --no-cache`

## Notes

- Maintain LLM-based reasoning throughout (no hardcoded rules)
- Preserve conversational nature of the system
- Ensure backward compatibility with existing sessions
- Keep temperature at 1.0 for all agents
- Use gpt-5-mini model consistently

## References

- Original issue: Duplicate "lineOfBusiness" questions
- JSONPath specs for business metadata fields
- Architecture requirement: Orchestrator handles common metadata
- ClarificationAgent design: Natural conversation for missing data