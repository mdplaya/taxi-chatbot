#!/bin/bash

# Script to run the TAXI Chatbot API server

# Navigate to backend directory
cd /Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set Python path
export PYTHONPATH=/Users/dwayne/Documents/GitHub/demo-chat/taxi-chatbot/backend

# Check if Valkey is running
if ! valkey-cli ping > /dev/null 2>&1; then
    echo "⚠️  Warning: Valkey is not running. Starting Valkey..."
    valkey-server --daemonize yes
fi

# Run the API server
echo "🚀 Starting TAXI Chatbot API server..."
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000