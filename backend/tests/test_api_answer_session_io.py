import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend package is on PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
import api.main as api_main
from agents.clarification import ClarificationAgent


def test_answer_uses_valkey_session_io(monkeypatch):
    client = TestClient(app)

    class Calls:
        load = 0
        save = 0

    calls = Calls()

    async def fake_load_session(session_id: str):
        calls.load += 1
        return None  # Force legacy fallback path; we just want the call

    async def fake_save_session(session_id: str, session_data: dict):
        calls.save += 1
        return True

    # Patch the exact instance used by the API module
    monkeypatch.setattr(api_main.valkey_manager, "load_session", fake_load_session)
    monkeypatch.setattr(api_main.valkey_manager, "save_session", fake_save_session)

    # Patch ClarificationAgent.process_answers to avoid dependency on error correction internals
    async def fake_process_answers(self, vm_request, answers):
        return vm_request
    monkeypatch.setattr(ClarificationAgent, "process_answers", fake_process_answers)

    # Start a session via /chat
    r1 = client.post("/chat", json={"message": "start a vm request"})
    assert r1.status_code == 200
    session_id = r1.json().get("session_id")
    assert session_id

    # Post an answer (valid email)
    r2 = client.post("/answer", json={
        "session_id": session_id,
        "answers": {"id": "user@example.com"}
    })
    assert r2.status_code == 200

    # Verify that the API attempted to use Valkey for session I/O
    assert calls.load >= 1, "Expected load_session to be called at least once"
    assert calls.save >= 1, "Expected save_session to be called at least once"
