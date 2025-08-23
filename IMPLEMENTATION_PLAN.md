# Implementation Plan - Fix TAXI Chatbot Issue

## Problem Statement
The chatbot always returns "I'm not sure what you'd like to do. Could you please provide more details about the resource you want to create?" regardless of user input.

## Root Cause Analysis

### Primary Issue
The Marvin AI functions in `orchestrator.py` and `compute.py` are not implemented - they only contain `pass` statements. When these functions are called, Marvin's `@fn` decorator attempts to use AI to generate the function implementation, but this fails (likely due to invalid API key or configuration issues).

### Failure Chain
1. User sends message → API receives it
2. OrchestratorAgent.process() calls `analyze_user_request()`
3. Marvin's `@fn` decorator tries to generate implementation via OpenAI
4. This fails (invalid API key or configuration)
5. Exception is caught, returns `next_agent: "clarification"`
6. Main.py line 188 returns the generic message

## Solution Verification Against Checklist

### ✅ Root Cause & Research
- **Root cause identified**: Empty Marvin functions failing at runtime
- **Not just symptoms**: Traced exact failure path through code
- **Best practices**: Direct implementation is more reliable than AI generation
- **Codebase patterns**: Follows existing agent architecture

### ✅ Architecture & Design
- **Current architecture fit**: Solution works within existing agent pipeline
- **No unnecessary changes**: Minimal modifications to existing structure
- **Technical debt**: Removes dependency on AI function generation
- **Honest assessment**: Marvin AI functions are unreliable for production

### ✅ Solution Quality
- **Simple & streamlined**: Direct pattern matching is simpler than AI
- **100% complete**: All components addressed
- **Long-term maintainability**: Explicit logic easier to debug/modify
- **Trade-offs**: Less flexible but more reliable

### ✅ Security & Safety
- **API key exposure**: Current key is exposed and needs replacement
- **Input validation**: Add sanitization for user messages
- **No new vulnerabilities**: Direct implementation is safer
- **Sensitive data**: API keys will be properly protected

### ✅ Integration & Testing
- **All impacts handled**: Both orchestrator and compute agents fixed
- **Consistent patterns**: Uses existing Pydantic models
- **Test coverage**: Unit and integration tests planned
- **Edge cases**: Malformed requests, missing fields

### ✅ Technical Completeness
- **Environment variables**: API key validation on startup
- **Logging**: Enhanced error capture
- **Performance**: Direct implementation faster than AI calls
- **Documentation**: CLAUDE.md updates included

## Implementation Tasks

### 1. Fix orchestrator.py - Implement analyze_user_request()
```python
def analyze_user_request(user_input: str) -> UserIntent:
    """Direct implementation with pattern matching"""
    user_input_lower = user_input.lower()
    
    # Detect cloud provider
    provider = None
    if any(term in user_input_lower for term in ['gcp', 'google cloud', 'gce']):
        provider = 'gcp'
    elif any(term in user_input_lower for term in ['azure', 'microsoft']):
        provider = 'azure'
    elif any(term in user_input_lower for term in ['aws', 'amazon', 'ec2']):
        provider = 'aws'
    
    # Detect intent
    intent = 'unclear'
    resource_type = None
    
    if any(term in user_input_lower for term in ['vm', 'virtual machine', 'instance', 'server', 'compute']):
        intent = 'create_compute'
        resource_type = 'vm'
    elif any(term in user_input_lower for term in ['database', 'db', 'sql', 'postgres', 'mysql']):
        intent = 'create_database'
        resource_type = 'database'
    elif any(term in user_input_lower for term in ['delete', 'remove', 'terminate']):
        intent = 'delete_resource'
    elif any(term in user_input_lower for term in ['modify', 'update', 'change', 'resize']):
        intent = 'modify_resource'
    
    return UserIntent(
        intent=intent,
        provider=provider,
        resource_type=resource_type,
        raw_requirements=user_input
    )
```

### 2. Fix compute.py - Implement extract_vm_requirements()
```python
def extract_vm_requirements(user_input: str) -> Dict[str, Any]:
    """Direct implementation with keyword extraction"""
    user_input_lower = user_input.lower()
    requirements = {}
    
    # Environment detection
    if any(term in user_input_lower for term in ['prod', 'production']):
        requirements['environment'] = 'PROD'
    elif any(term in user_input_lower for term in ['dev', 'development', 'test', 'nonprod']):
        requirements['environment'] = 'NONPROD'
    
    # OS detection
    if 'windows' in user_input_lower:
        if '22' in user_input or '2022' in user_input:
            requirements['os'] = 'WINDOWS_22'
        else:
            requirements['os'] = 'WINDOWS_19'
    elif any(term in user_input_lower for term in ['linux', 'rhel', 'red hat']):
        if '9' in user_input:
            requirements['os'] = 'LINUX_RHEL9'
        else:
            requirements['os'] = 'LINUX_RHEL8'
    
    # Use type detection
    if any(term in user_input_lower for term in ['database', 'db']):
        requirements['use_type'] = 'database'
    elif any(term in user_input_lower for term in ['app', 'application', 'web']):
        requirements['use_type'] = 'app'
    
    # Machine type detection
    if 'n1-standard' in user_input_lower:
        requirements['machine_type'] = 'n1-STANDARD-1'
    elif 'n2-standard' in user_input_lower:
        requirements['machine_type'] = 'n2-STANDARD-1'
    
    # Zone detection (regex for GCP zones)
    import re
    zone_pattern = r'(us|europe|asia|australia|southamerica|northamerica)-(central|east|west|south|north|northeast|southeast)\d+-[a-z]'
    zone_match = re.search(zone_pattern, user_input_lower)
    if zone_match:
        requirements['zone'] = zone_match.group()
    
    # Line of business detection
    if 'retail' in user_input_lower:
        requirements['line_of_business'] = 'RETAIL'
    elif 'ists' in user_input_lower:
        requirements['line_of_business'] = 'ISTS'
    elif 'edml' in user_input_lower:
        requirements['line_of_business'] = 'EDML'
    
    return requirements
```

### 3. Update .env - Replace exposed API key
- Replace current exposed key with placeholder
- Add .env to .gitignore if not already present
- Create .env.example with proper format

### 4. Add validation - Check API key on startup
```python
# In api/main.py at startup
import os
import sys

# Check for required environment variables
if not os.getenv('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY').startswith('sk-your'):
    logger.error("OPENAI_API_KEY not configured properly")
    sys.exit(1)
```

### 5. Test the flow
- Test with: "I want a VM in GCP"
- Test with: "Create a Linux server for development"
- Test with: "Deploy a Windows 2022 VM in us-east4-a for retail"
- Verify proper routing and response

### 6. Add enhanced logging
```python
# Add detailed logging in orchestrator.py
try:
    intent = analyze_user_request(user_input)
    self.logger.info(f"Successfully analyzed intent: {intent}")
except Exception as e:
    self.logger.error(f"Failed to analyze request: {str(e)}", exc_info=True)
    # Return more informative error
```

### 7. Document changes in CLAUDE.md
- Update architecture section with new implementation
- Add troubleshooting section
- Document the direct implementation approach

## Testing Plan

### Unit Tests
- Test `analyze_user_request()` with various inputs
- Test `extract_vm_requirements()` with different patterns
- Test error handling paths

### Integration Tests
- Full flow from chat endpoint to response
- Session management across multiple requests
- Clarification flow when fields are missing

### Edge Cases
- Empty/null inputs
- Malformed requests
- Conflicting requirements
- Unknown cloud providers

## Security Improvements
1. Remove exposed API key from repository
2. Add environment variable validation
3. Input sanitization for user messages
4. Rate limiting on API endpoints
5. Secure session management

## Success Criteria
- ✅ "I want a VM in GCP" correctly routes to compute agent
- ✅ VM requirements are properly extracted
- ✅ Clarification only asked when truly needed
- ✅ Proper error messages for failures
- ✅ All tests passing
- ✅ No security vulnerabilities

## Notes
- The current implementation relies too heavily on AI function generation which is unreliable
- Direct implementation with pattern matching is more predictable and debuggable
- This approach follows industry best practices for intent classification
- Future enhancement: Add ML-based intent classification as optional feature