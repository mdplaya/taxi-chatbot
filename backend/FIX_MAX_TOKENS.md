# Fix: max_tokens Parameter Error

## Issue
When running `test_phase4_demo_with_llm.py` with an OpenAI API key, the following error occurred:
```
LLM analysis error: Error code: 400 - {'error': {'message': "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.", 'type': 'invalid_request_error', 'param': 'max_tokens', 'code': 'unsupported_parameter'}}
```

## Cause
Newer OpenAI models (including gpt-4-turbo and later) have deprecated the `max_tokens` parameter in favor of `max_completion_tokens` for more precise control over response length.

## Solution
Updated the `_llm_analyze` method in `backend/utils/learning.py` (line 489):

**Before:**
```python
response = self.llm.chat.completions.create(
    model=self.model,
    messages=[...],
    temperature=self.temperature,
    max_tokens=2000  # Old parameter
)
```

**After:**
```python
response = self.llm.chat.completions.create(
    model=self.model,
    messages=[...],
    temperature=self.temperature,
    max_completion_tokens=2000  # New parameter
)
```

## Files Modified
- `backend/utils/learning.py` - Line 489

## Testing
Created `test_llm_fix.py` to verify the fix works with actual API calls.

To test with your API key:
```bash
# Add your API key to .env
echo "OPENAI_API_KEY=sk-your-key-here" >> backend/.env

# Run the test
PYTHONPATH=/path/to/backend python test_llm_fix.py

# Or run the full demo
PYTHONPATH=/path/to/backend python test_phase4_demo_with_llm.py
```

## Impact
This fix ensures compatibility with:
- Latest OpenAI models (gpt-4-turbo, gpt-4o, etc.)
- Future model releases
- The gpt-5-mini model specified in configuration

## Note
The parameter `max_completion_tokens` serves the same purpose as `max_tokens` but is the newer, preferred parameter name in the OpenAI API.