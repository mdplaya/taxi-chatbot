import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Tuple
import pytest
from fastapi.testclient import TestClient
from api.main import app


def start_session(client: TestClient) -> str:
    r = client.post("/chat", json={"message": "start a vm request"})
    assert r.status_code == 200
    sid = r.json().get("session_id")
    assert sid
    return sid


@pytest.mark.parametrize(
    "field,value",
    [
        ("appEnvironment", "invalid-env"),
        ("appEnvironmentSubtype", "weird"),
        ("os", "bananaOS"),
        ("useType", "unknown-role"),
        ("machineType", "e2-notreal"),
    ],
)
def test_answer_returns_clarification_on_invalid_fields(field: str, value: str):
    client = TestClient(app)
    session_id = start_session(client)

    # Submit invalid answer
    r = client.post("/answer", json={"session_id": session_id, "answers": {field: value}})
    assert r.status_code == 200
    body = r.json()
    assert body.get("needs_clarification") is True

    # Targeted question should reference the same field
    questions = body.get("questions", [])
    assert any(
        (isinstance(q, dict) and q.get("field") == field) or
        (isinstance(q, dict) and field in (q.get("question") or ""))
        for q in questions
    ), f"questions did not include field {field}: {questions}"

