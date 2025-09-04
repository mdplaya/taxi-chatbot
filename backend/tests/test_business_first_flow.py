import os
import sys
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestBusinessFirstFlow:
    def test_routes_to_clarification_when_business_missing(self):
        """For a generic VM request without email/LOB, orchestrator should ask Business first."""
        agent = OrchestratorAgent()
        # No business metadata (no email/LOB) is present in the request below
        res = run(agent.process("Create a Linux server for development"))
        assert isinstance(res, dict)
        assert res.get("next_agent") == "clarification", (
            f"Expected 'clarification' first, got: {res.get('next_agent')} with context {res.get('context')}"
        )

        ctx = res.get("context", {})
        # Ensure missing_info includes at least one business field
        missing = set((ctx.get("missing_info") or []))
        # We consider these the Business group
        business_fields = {"lineOfBusiness", "id", "appEnvironment", "appEnvironmentSubtype", "costCenter"}
        assert missing & business_fields, f"Expected business fields missing, got: {missing}"

    # Note: We intentionally do not assert the positive case for compute routing here
    # because email detection (id) depends on the optional 'email-validator' package.
    # In CI/offline environments that package may be absent, which makes id detection
    # gracefully skip and keeps the flow in clarification (which is acceptable).
