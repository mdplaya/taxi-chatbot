import pytest
import sys, os

# Ensure backend package paths are importable when running this file directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.clarification import ClarificationAgent
from models.taxi_models import VMRequest


@pytest.mark.asyncio
async def test_invalid_id_skipped_and_question_generated():
    agent = ClarificationAgent()
    vm_request = VMRequest(
        costCenter="12345",
    )

    # Provide an invalid id (not an email)
    answers = {"id": "webapp-dev-1"}
    updated = await agent.process_answers(vm_request, answers)

    # Invalid id should be skipped (remain None)
    assert updated.id is None

    # Clarification should include a question for 'id' that mentions email
    context = {'raw_request': 'Create a VM', 'conversation_history': [], 'session_id': 'test-id'}
    clarifications = await agent.get_clarifications(updated, context)

    assert clarifications.get("complete") is False
    questions = clarifications.get("questions", [])
    # Fallback ensures at least 'id' question exists
    has_id = any(q.get('field') == 'id' for q in questions)
    assert has_id, "Expected a question for requestor id"

    # The question should frame id as an email
    id_q = next(q for q in questions if q.get('field') == 'id')
    assert 'email' in id_q.get('question', '').lower()

