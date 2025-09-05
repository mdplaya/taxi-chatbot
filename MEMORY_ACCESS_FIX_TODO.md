# Memory Access Fix - Implementation TODO

**Branch**: backend-simplification  
**Reference**: See MEMORY_ACCESS_FIX_PLAN.md for full details

## Pre-Implementation Checklist
- [ ] Currently on backend-simplification branch
- [ ] Read MEMORY_ACCESS_FIX_PLAN.md completely
- [ ] Understand the root cause and solution
- [ ] Have Docker running

## Implementation Steps

### Phase 1: Fix base_agent.py

#### 1.1 Add SimpleMemory Class
- [ ] Open `/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend/agents/base_agent.py`
- [ ] Add SimpleMemory class after imports, before SimpleBaseAgent class:
```python
class SimpleMemory:
    """Simple memory storage for agents"""
    def __init__(self):
        self.short_term = []  # List for sequential storage
        self.long_term = {}   # Dict for key-value storage
        self.corrections = []  # List of corrections
        self.learned_patterns = []  # List of learned patterns
        self.user_preferences = {}  # Dict of preferences
```

#### 1.2 Update Memory Initialization
- [ ] In SimpleBaseAgent.__init__ method, find the memory initialization (around line 40)
- [ ] Replace the dict initialization:
  - [ ] Remove: `self.memory = {"short_term": {}, "long_term": {}, "session_data": {}}`
  - [ ] Add: `self.memory = SimpleMemory()`

### Phase 2: Fix orchestrator.py Bug

#### 2.1 Fix _get_conversation_history (Line 391-393)
- [ ] Open `/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend/agents/orchestrator.py`
- [ ] Find `_get_conversation_history` method (around line 383)
- [ ] Change line 391: `for key in self.memory.short_term.keys():` 
  - [ ] To: `for key in self.memory.long_term.keys():`
- [ ] Change line 393: `history.append(self.memory.short_term[key])`
  - [ ] To: `history.append(self.memory.long_term[key])`

#### 2.2 Fix _get_session_memory (Lines 405-406, 412)
- [ ] Find `_get_session_memory` method (around line 399)
- [ ] Change line 405: `if session_key not in self.memory.short_term:`
  - [ ] To: `if session_key not in self.memory.long_term:`
- [ ] Change line 406: `self.memory.short_term[session_key] = {`
  - [ ] To: `self.memory.long_term[session_key] = {`
- [ ] Change line 412: `return self.memory.short_term[session_key]`
  - [ ] To: `return self.memory.long_term[session_key]`

### Phase 3: Build and Test

#### 3.1 Rebuild Docker Images
- [ ] Run: `docker-compose build api`
- [ ] Verify build completes without errors

#### 3.2 Restart Containers
- [ ] Run: `docker-compose up -d`
- [ ] Check all containers are running: `docker-compose ps`
- [ ] Verify API logs: `docker logs taxi-chatbot-api --tail 30`
  - [ ] No import errors
  - [ ] Application startup complete

#### 3.3 Test Basic Chat
- [ ] Test simple request:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a Linux server for development"}' | jq .
```
- [ ] Verify NO AttributeError in response or logs
- [ ] Check response has clarification questions

#### 3.4 Test Complex Request
- [ ] Test with more details:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Deploy Windows Server 2022 VM in us-east4-a for retail production with cost center 12345"}' | jq .
```
- [ ] Verify response processes correctly
- [ ] Check no memory errors in logs

### Phase 4: Verify All Agents

#### 4.1 Check Agent Memory Access
- [ ] Check API logs for any AttributeError: `docker logs taxi-chatbot-api | grep AttributeError`
- [ ] Verify orchestrator routing works
- [ ] Verify clarification flow works
- [ ] Test answer endpoint if needed

#### 4.2 Run Tests (Optional)
- [ ] If tests are set up, run:
```bash
cd /Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend
python -m pytest tests/test_agentic_implementation.py -xvs
```

### Phase 5: Commit Changes

#### 5.1 Review Changes
- [ ] Run: `git diff` to review all changes
- [ ] Verify only 2 files changed (base_agent.py and orchestrator.py)
- [ ] Confirm changes match the plan

#### 5.2 Commit
- [ ] Stage changes: `git add -A`
- [ ] Commit with message:
```bash
git commit -m "Fix agent memory access errors

Problem: AttributeError 'dict' object has no attribute 'short_term'
Root cause: Simplified base_agent changed Memory from class to dict

Solution:
1. Created SimpleMemory class with proper attributes
2. Fixed orchestrator bug using short_term as dict instead of list

Changes:
- Added SimpleMemory class to base_agent.py
- Updated memory initialization to use SimpleMemory()
- Fixed orchestrator to use long_term for session storage (5 lines)

Result:
✅ All agents can access memory without errors
✅ Orchestrator correctly uses long_term for sessions
✅ All memory operations work as expected
✅ Chat endpoint fully functional"
```

### Phase 6: Post-Implementation Verification

#### 6.1 Final Tests
- [ ] Test health endpoint: `curl http://localhost:8000/health | jq .`
- [ ] Test MCP server health: `curl http://localhost:8001/health | jq .`
- [ ] Create a new session and verify it works end-to-end

#### 6.2 Monitor for Issues
- [ ] Watch logs for 2-3 minutes: `docker logs -f taxi-chatbot-api`
- [ ] Verify no memory-related errors appear

## Troubleshooting

### If AttributeError persists:
1. Check SimpleMemory class was added correctly
2. Verify memory initialization uses SimpleMemory()
3. Check all 5 orchestrator changes were made
4. Rebuild with --no-cache: `docker-compose build --no-cache api`

### If orchestrator fails:
1. Verify changed short_term to long_term in all 5 places
2. Check no typos in the changes
3. Ensure SimpleMemory has all required attributes

### If tests fail:
1. Tests should work without changes
2. If they fail, it means SimpleMemory is missing an attribute
3. Check error message for which attribute is missing

## Success Criteria
- ✅ No AttributeError in any logs
- ✅ Chat endpoint works for simple requests
- ✅ Chat endpoint works for complex requests  
- ✅ Clarification flow shows questions
- ✅ All Docker containers stay running
- ✅ Can create and retrieve sessions

## Rollback if Needed
```bash
# If something goes wrong:
git stash
git checkout backend-simplification  
git reset --hard HEAD~1
docker-compose build api
docker-compose up -d
```

## Notes
- Total changes: ~10 lines across 2 files
- No changes needed in other agent files
- No changes needed in test files
- This fix also corrects a bug in the original orchestrator code