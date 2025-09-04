import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api.main import app


def test_answer_returns_clarification_on_invalid_enum():
    client = TestClient(app)

    # Create a new session via /chat
    r1 = client.post("/chat", json={"message": "start a vm request"})
    assert r1.status_code == 200
    session_id = r1.json().get("session_id")
    assert session_id

    # Submit an invalid lineOfBusiness to /answer
    r2 = client.post("/answer", json={
        "session_id": session_id,
        "answers": {"lineOfBusiness": "Dwayne"}
    })

    assert r2.status_code == 200
    body = r2.json()
    assert body.get("needs_clarification") is True

    # Ensure a targeted question for lineOfBusiness is present
    questions = body.get("questions", [])
    assert any(
        (isinstance(q, dict) and q.get("field") == "lineOfBusiness") or
        (isinstance(q, dict) and "lineOfBusiness" in (q.get("question") or ""))
        for q in questions
    ), f"questions did not include lineOfBusiness: {questions}"

