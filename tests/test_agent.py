from __future__ import annotations

import unittest
from unittest.mock import MagicMock

try:
    import strands
    from strands.interventions import Deny, Guide, Proceed

    from safeops.agent import (
        DEFAULT_BEDROCK_MODEL_ID,
        DIAGNOSTIC_TOOLS,
        SafeOpsToolReviewer,
        build_agent,
        to_strands_action,
    )

    HAS_STRANDS = True
except ImportError:
    HAS_STRANDS = False

from safeops.guardrails import GuardrailDecision
from tests.fakes import SAFE_SCORES, FakeDecider


@unittest.skipUnless(HAS_STRANDS, "strands-agents is not installed in this environment")
class AgentWiringTests(unittest.TestCase):
    def test_to_strands_action_mappings(self) -> None:
        deny_action = to_strands_action(GuardrailDecision("deny", "action blocked"))
        self.assertIsInstance(deny_action, Deny)
        self.assertEqual(deny_action.reason, "action blocked")

        guide_action = to_strands_action(GuardrailDecision("guide", "please clarify"))
        self.assertIsInstance(guide_action, Guide)
        self.assertEqual(guide_action.feedback, "please clarify")

        proceed_action = to_strands_action(GuardrailDecision("proceed", "safe"))
        self.assertIsInstance(proceed_action, Proceed)

    def test_reviewer_blocks_destructive_call(self) -> None:
        decider = FakeDecider(SAFE_SCORES)
        reviewer = SafeOpsToolReviewer(decider)  # type: ignore[arg-type]

        mock_event = MagicMock()
        mock_event.tool_use = {"name": "terminate_instance", "input": {"resource_id": "i-0safeops01"}}
        mock_event.agent.messages = [{"role": "user", "content": "investigate latency"}]

        action = reviewer.before_tool_call(mock_event)
        self.assertIsInstance(action, Deny)
        self.assertIn("destructive", action.reason.lower())
        self.assertEqual(decider.calls, [])
        self.assertEqual(len(reviewer.log), 1)
        self.assertEqual(reviewer.log[0]["kind"], "deny")

    def test_reviewer_allows_grounded_diagnostic_call(self) -> None:
        decider = FakeDecider(SAFE_SCORES)
        reviewer = SafeOpsToolReviewer(decider)  # type: ignore[arg-type]

        mock_event = MagicMock()
        mock_event.tool_use = {"name": "get_logs", "input": {"resource": "web-api-prod"}}
        mock_event.agent.messages = [{"role": "user", "content": "check web-api-prod"}]

        action = reviewer.before_tool_call(mock_event)
        self.assertIsInstance(action, Proceed)
        self.assertEqual(len(decider.calls), 1)
        self.assertEqual(reviewer.log[0]["kind"], "proceed")

    def test_reviewer_guides_ungrounded_call(self) -> None:
        decider = FakeDecider({**SAFE_SCORES, "args_grounded": 0.1})
        reviewer = SafeOpsToolReviewer(decider)  # type: ignore[arg-type]

        mock_event = MagicMock()
        mock_event.tool_use = {"name": "get_metrics", "input": {"resource": "random-host"}}
        mock_event.agent.messages = [{"role": "user", "content": "check the server"}]

        action = reviewer.before_tool_call(mock_event)
        self.assertIsInstance(action, Guide)
        self.assertIn("grounded", action.feedback.lower())

    def test_build_agent_wiring(self) -> None:
        decider = FakeDecider(SAFE_SCORES)
        agent = build_agent(decider)  # type: ignore[arg-type]
        self.assertEqual(len(agent.tool_names), len(DIAGNOSTIC_TOOLS))
        self.assertTrue(hasattr(agent, "_safeops_reviewer"))
        self.assertIsInstance(agent._safeops_reviewer, SafeOpsToolReviewer)


if __name__ == "__main__":
    unittest.main()
