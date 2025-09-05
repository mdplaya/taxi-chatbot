import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend package is on PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
import api.main as api_main
from agents.orchestrator import OrchestratorAgent
from agents.compute import ComputeAgent
from agents.gce_specialist import GCESpecialistAgent
from agents.clarification import ClarificationAgent


def test_business_questions_routed_to_clarification(monkeypatch):
    client = TestClient(app)

    # Force orchestrator -> compute
    async def orch_proc(self, context, session_id=None, progress_callback=None):
        return {
            "action": {
                "type": "route_to_compute",
                "agent": "compute",
                "confidence": 0.9,
                "parameters": {"raw_request": "dummy"}
            },
            "context": {"original_request": "dummy"},
            "mode": "agentic"
        }

    monkeypatch.setattr(OrchestratorAgent, "process", orch_proc)

    # Force compute -> gce_specialist
    async def compute_proc(self, context, progress_callback=None):
        return {
            "action": {"agent": "gce_specialist"},
            "context": {"raw_request": "Create VM"},
            "next_agent": "gce_specialist"
        }

    monkeypatch.setattr(ComputeAgent, "process", compute_proc)

    # GCE needs clarification with business field 'id' missing; no id question provided
    async def gce_create(self, context, config=None):
        return {
            "success": False,
            "needs_clarification": True,
            "missing_fields": ["id", "project"],
            "questions": [
                {"field": "project", "question": "Which GCP project?"}
            ],
            "partial_data": {}
        }

    monkeypatch.setattr(GCESpecialistAgent, "create_instance", gce_create)

    # Clarification should supply the id question
    async def clar_get(self, vm_request, context):
        return {
            "complete": False,
            "questions": [{"field": "id", "question": "What is your email?"}]
        }

    monkeypatch.setattr(ClarificationAgent, "get_clarifications", clar_get)

    # Trigger the chat flow
    r = client.post("/chat", json={"message": "start a vm request"})
    assert r.status_code == 200
    body = r.json()
    qs = body.get("questions", [])
    fields = [q.get("field") for q in qs if isinstance(q, dict)]
    assert "id" in fields, f"Expected Clarification-provided id question, got: {qs}"
