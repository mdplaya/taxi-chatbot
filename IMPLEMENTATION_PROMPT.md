# Implementation Prompt for Error Correction Fix

Copy and paste this prompt into a new Claude session:

---

## PROMPT TO COPY:

I need you to implement a fix for my error correction system. I have complete documentation ready.

Please:

1. **Read these two files first:**
   - `/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/FIX_ERROR_CORRECTION_SYSTEM.md`
   - `/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/ERROR_CORRECTION_TODO.md`

2. **Implement the changes exactly as documented** in `/backend/utils/error_correction.py`:
   - Add the datetime import
   - Add the `corrected` property to CorrectionResult class
   - Update the `__init__` method to add learning_cache and max_cache_size
   - Add the `detect_and_correct()` method
   - Add the `learn_from_feedback()` method

3. **Test the implementation:**
   - Rebuild the Docker container
   - Verify no AttributeError occurs
   - Test that "4gb n1 std" normalizes to "n1-standard-4"

The working directory is: `/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot`

All the specific code changes, line numbers, and implementation details are in the FIX_ERROR_CORRECTION_SYSTEM.md file. The ERROR_CORRECTION_TODO.md file provides a complete checklist to follow.

This fix resolves AttributeError exceptions when users provide answers in the clarification flow.

---

That's it! This prompt will direct the new session to read your documentation and implement the fix exactly as specified.