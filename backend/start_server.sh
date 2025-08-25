#!/bin/bash

# Start TAXI Chatbot API Server with OpenAI API Key

# Load environment variables from .env file
if [ -f .env ]; then
    # Export all variables from .env file
    export $(grep -v '^#' .env | xargs)
fi

# Ensure OPENAI_API_KEY is set (fallback in case .env doesn't load)
if [ -z "$OPENAI_API_KEY" ]; then
    echo "WARNING: OPENAI_API_KEY not found in .env file"
    echo "Trying to load directly..."
    OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" .env | cut -d'=' -f2)
    export OPENAI_API_KEY
fi

# Display mode
if [ -n "$OPENAI_API_KEY" ]; then
    echo "🚀 Starting TAXI Chatbot API in ONLINE mode (LLM enabled)..."
else
    echo "⚠️  Starting TAXI Chatbot API in OFFLINE mode (pattern matching)..."
fi

# Start the server
PYTHONPATH=$(pwd) python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000