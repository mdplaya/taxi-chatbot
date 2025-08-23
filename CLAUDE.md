# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Frontend (Next.js)
- `npm run dev` - Start development server on port 3000
- `npm run build` - Build production bundle
- `npm run start` - Start production server
- `npm run lint` - Run Next.js linter

### Backend (FastAPI)
- `uvicorn api.main:app --reload --host 0.0.0.0 --port 8000` - Start API server
- `python mcp_server/server.py` - Start MCP server on port 8001

### Docker
- `docker-compose up --build` - Build and start all services
- `docker-compose down` - Stop all services

## Architecture Overview

This is a TAXI Chatbot system for infrastructure provisioning with the following components:

### Backend (`/backend`)
- **FastAPI API** (`api/main.py`): REST API with endpoints for chat, clarifications, and session management
- **Agent System** (`agents/`):
  - `orchestrator.py`: Routes requests to appropriate agents
  - `clarification.py`: Handles missing information gathering
  - `compute.py`: Extracts VM requirements from natural language
  - `gce_specialist.py`: Handles GCP-specific provisioning
- **MCP Server** (`mcp_server/server.py`): Model Context Protocol server for TAXI API integration
- **Models** (`models/taxi_models.py`): Pydantic models for VM requests and chat sessions

### Frontend (`/frontend`)
- **Next.js Application**: React-based chat interface
- **Main Chat Component** (`app/page.tsx`): Handles user interactions, message display, and clarification forms
- **API Integration**: Communicates with backend on `http://localhost:8000`

### Key Workflows

1. **Chat Flow**: User message → Orchestrator → Compute Agent → Clarification (if needed) → GCE Specialist → TAXI payload
2. **Session Management**: Sessions tracked in-memory with unique IDs
3. **Clarification System**: Dynamic form generation for missing VM configuration fields

## Important Implementation Details

- Uses Marvin.ai for NLP processing (requires OPENAI_API_KEY)
- CORS enabled for cross-origin requests
- Docker Compose orchestrates three services: mcp-server, api, and frontend
- VM provisioning currently mocked (returns simulated TAXI responses)
- Required VM fields defined in `VMRequest.get_missing_fields()`

## Testing Endpoints

- Health check: `GET http://localhost:8000/health`
- Chat: `POST http://localhost:8000/chat` with `{"message": "...", "session_id": null}`
- Answer clarifications: `POST http://localhost:8000/answer` with `{"session_id": "...", "answers": {...}}`
- Session status: `GET http://localhost:8000/session/{session_id}/status`