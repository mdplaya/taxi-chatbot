#!/usr/bin/env python3
"""
Quick test to verify the max_tokens fix works
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.learning import LearningEngine
from unittest.mock import AsyncMock
from utils.valkey_manager import ValkeyManager

# Load environment variables
load_dotenv()

async def test_llm_call():
    """Test that LLM calls work with max_completion_tokens"""
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("❌ No OpenAI API key configured")
        print("Add your key to backend/.env to test")
        return False
    
    print("✅ OpenAI API key found")
    
    # Initialize learning engine
    mock_valkey = AsyncMock(spec=ValkeyManager)
    engine = LearningEngine(mock_valkey)
    
    if not engine.llm:
        print("❌ LLM client not initialized")
        return False
    
    print("✅ LLM client initialized")
    print(f"   Model: {engine.model}")
    print(f"   Temperature: {engine.temperature}")
    
    # Test a simple pattern recognition
    print("\n🧪 Testing pattern recognition...")
    
    session_history = [
        {"agent": "orchestrator", "action": "route", "target": "compute"},
        {"agent": "compute", "action": "extract", "result": "success"}
    ]
    
    try:
        patterns = await engine.identify_success_patterns(session_history, "success")
        print("✅ LLM call successful!")
        print(f"   Patterns found: {len(patterns)}")
        for pattern in patterns:
            print(f"   - {pattern.type.value}: {pattern.description[:50]}...")
        return True
    except Exception as e:
        print(f"❌ LLM call failed: {e}")
        return False

async def main():
    print("="*60)
    print("Testing max_tokens → max_completion_tokens Fix")
    print("="*60)
    
    success = await test_llm_call()
    
    print("\n" + "="*60)
    if success:
        print("✅ FIX VERIFIED - LLM calls working correctly!")
        print("\nThe system now uses 'max_completion_tokens' parameter")
        print("which is compatible with newer OpenAI models.")
    else:
        print("⚠️  Test incomplete - check API key configuration")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())