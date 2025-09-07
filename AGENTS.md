# Repository Guidelines

## File System Navigation Policy
- You MUST use /usr/bin/cd when changing directories DO NOT run cd or z

## Project Structure & Module Organization
- backend: FastAPI services and agent logic.
  - `agents/`: Orchestrator, Clarification, Compute, GCE specialist.
  - `api/`: FastAPI app (`api.main:app`).
  - `models/`, `utils/`, `mcp_server/`, `tests/`.
- frontend: Next.js (TypeScript + Tailwind) app in `frontend/app`.
- Root: `docker-compose.yml`, `.env(.example)`, README and design docs.

## Build, Test, and Development Commands
- Docker (all services): `docker-compose up --build` → UI on `http://localhost:3000`, API on `http://localhost:8000`.
- Backend (local):
  - `cd backend && pip install -r requirements.txt`
  - Run MCP: `python mcp_server/server.py`
  - Run API: `uvicorn api.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend (local):
  - `cd frontend && npm install`
  - Dev server: `npm run dev`
- Tests (backend): `pytest -q backend` (ensure `pytest` is installed in your venv).

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indent, type hints required in new/changed code.
  - Files/modules: `snake_case.py`; classes: `PascalCase`; functions/vars: `snake_case`.
- TypeScript/React: follow Next.js defaults and ESLint (`npm run lint`).
  - Files in `app/` kebab- or folder-based routes; components `PascalCase.tsx`.
- Keep prompts/config in `backend/agents/*.py` small and cohesive; prefer helper functions in `utils/`.

## Testing Guidelines
- Framework: `pytest` with async tests where applicable.
- Location: `backend/tests/test_*.py` and select `backend/test_*.py` helpers.
- Conventions: one behavior per test, clear arrange/act/assert, prefer fixtures.
- Add tests for new logic and bug fixes; keep external I/O mocked.
- You MUST test all changes prior to asking the user to test.  You should not provide the code back until you get no errors, use a subagent to do this.  Do not use the main agent context window
- You MUST create test to verify all changes before you start.

## Commit & Pull Request Guidelines
- Commits: imperative, concise, scoped when helpful (examples: "Fix environment inference", "Remove hardcoded GCP default").
- PRs must include:
  - Summary, linked issues, and rationale.
  - Testing notes (commands, screenshots/GIFs for UI changes).
  - Check that `pytest` passes and `npm run lint` shows no errors.
- For every new change you MUST run git add and commit to the changed files and write a brief and detailed commit summary

## Security & Configuration Tips
- Never commit secrets. Copy `.env.example` to `.env` (root and `backend/` as needed).
- Required keys include `OPENAI_API_KEY`; validate ports `8000/8001/3000` are free.
- Prefer `docker-compose` for parity; keep environment-specific settings out of code.
- You MUST make sure there are no security issues with the code prior to giving it to the user.
- You MUST scan the code for common security vulnerabilities prior to giving it to the user.

## Agent-Specific Instructions
- Update agent behavior in `backend/agents/` (orchestrator/clarification/compute/gce_specialist).
- Extend TAXI models in `backend/models/taxi_models.py` and corresponding builders in `backend/mcp_server/tools.py`.

## Initialization Policy
- You MUST source .venv/bin/activate before running any python commands
## - You MUST run python -m venv .venv if you need to run python and the pythong environment does not exist

## Checklist and Planning
- You MUST always show your code and files changed before actually editing files.
- You MUST provide a detailed explaination of each change before editing the files, with the pros and cons of each action.   
- You MUST present at least two options for changes that impliment more than 10 lines of code.
- You MUST verify your plan against this checklist, before moving forward
- You MUST provide the pros and cons to the user before executing any plan 
- You MUST review your plan, before moving forward with any code change

## Solution Verification Checklist

## Root Cause & Research

- [ ]  Identified root cause, not symptoms
- [ ]  Researched industry best practices
- [ ]  Analyzed existing codebase patterns
- [ ]  Conducted additional research where needed

## Architecture & Design

- [ ]  Evaluated current architecture fit
- [ ]  Recommended changes if beneficial
- [ ]  Identified technical debt impact
- [ ]  Challenged suboptimal patterns
- [ ]  NOT a yes-man - honest assessment

## Solution Quality

- [ ]  [Claude.md](http://claude.md/) compliant
- [ ]  Simple, streamlined, no redundancy
- [ ]  100% complete (not 99%)
- [ ]  Best solution with trade-offs explained
- [ ]  Prioritized long-term maintainability

## Security & Safety

- [ ]  No security vulnerabilities introduced
- [ ]  Input validation and sanitization added
- [ ]  Authentication/authorization properly handled
- [ ]  Sensitive data protected (encryption, no logging)
- [ ]  OWASP guidelines followed

## Integration & Testing

- [ ]  All upstream/downstream impacts handled
- [ ]  All affected files updated
- [ ]  Consistent with valuable patterns
- [ ]  Fully integrated, no silos
- [ ]  Tests with edge cases added

## Technical Completeness

- [ ]  Environment variables configured
- [ ]  DB / Storage rules updated
- [ ]  Utils and helpers checked
- [ ]  Performance analyzed

## Your APP specific validation // Update as needed

- [ ]  Agentic system integrity maintained
- [ ]  The model used should always be gpt-5-mini. The temperature is 1.0
- [ ]  Minimize rules based system
- [ ]  Conversational system
- [ ]  Conversational LLM flows validated
- [ ]  Maintain Agents
- [ ]  Maintain Orchestrator Agent (agents/orchestrator.py) functionality below
    - Main conversation manager
    - Maintains context across interactions
    - Routes to appropriate agents either Clarification Agent or Compute Agent
    - Handles conversation state
- [ ]  Maintain Clarification Agent (agents/clarification.py) functionality below
    - Shows ALL known information upfront
    - Asks only for missing data
    - Allows editing any field anytime
    - Uses AI for natural conversation to get more information
    - Integrates error correction with AI
- [ ]  Compute Agent (agents/compute.py) functionality below
    - Detects ALL cloud providers (Azure/GCP/AWS/OnPrem) for Compute instances ONLY
    - Uses AI error correction for field values
    - Extracts requirements intelligently
    - Chooses Specialist Agent
- [ ]  GCE-Specialist Agent (agents/gce_specialist.py) functionality below
    - Focus only on GCE provisioning
    - Validates corrected inputs
    - Generates TAXI payloads

## ANALYZE ALL ITEMS IN THIS CHECKLIST ONE BY ONE. ACHIEVE 100% COVERAGE. DO NOT MISS A SINGLE ITEM.

## Process: READ → RESEARCH → ANALYZE ROOT CAUSE → CHALLENGE → THINK → RESPOND
