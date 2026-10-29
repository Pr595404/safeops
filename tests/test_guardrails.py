from __future__ import annotations

import unittest

from safeops.guardrails import (
    YES,
    _noul,
    build_state,
    render_conversation,
    review_tool_call,
)
from tests.fakes import SAFE_SCORES, FakeDecider


class GuardrailTests(unittest.TestCase):
    def test_unsafe_destructive_denied_without_calling_decider(self) -> None:
        decider = FakeDecider(SAFE_SCORES)
        decision = review_tool_call(
            tool_name="terminate_instance",
            arguments={"resource_id": "i-0safeops01"},
            conversation="user: Please investigate INC-001 on web-api-prod.",
            decider=decider,
        )
        self.assertEqual(decision.kind, "deny")
        self.assertEqual(decider.calls, [])
        self.assertIn("destructive", decision.feedback.lower())

    def test_safe_grounded_diagnostic_proceeds(self) -> None:
        decider = FakeDecider(SAFE_SCORES)
        decision = review_tool_call(
            tool_name="get_logs",
            arguments={"resource": "web-api-prod"},
            conversation="user: INC-001 checkout latency is high on web-api-prod.",
            decider=decider,
        )
        self.assertEqual(decision.kind, "proceed")
        self.assertEqual(len(decider.calls), 1)

    def test_ungrounded_arguments_are_guided(self) -> None:
        decider = FakeDecider({**SAFE_SCORES, "args_grounded": 0.12})
        decision = review_tool_call(
            tool_name="get_logs",
            arguments={"resource": "i-guessed-999"},
            conversation="user: What's wrong with production?",
            decider=decider,
        )
        self.assertEqual(decision.kind, "guide")
        self.assertIn("grounded", decision.feedback.lower())

    def test_premature_call_is_guided(self) -> None:
        decider = FakeDecider({**SAFE_SCORES, "premature": 0.81})
        decision = review_tool_call(
            tool_name="get_metrics",
            arguments={"resource": "web-api-prod"},
            conversation="user: something feels slow",
            decider=decider,
        )
        self.assertEqual(decision.kind, "guide")
        self.assertIn("too early", decision.feedback.lower())

    def test_inappropriate_diagnostic_is_guided(self) -> None:
        decider = FakeDecider({**SAFE_SCORES, "diagnostic_appropriate": 0.05})
        decision = review_tool_call(
            tool_name="get_logs",
            arguments={"resource": "payments-worker"},
            conversation="user: Investigate checkout latency on web-api-prod.",
            decider=decider,
        )
        self.assertEqual(decision.kind, "guide")
        self.assertIn("appropriate diagnostic", decision.feedback.lower())

    def test_threshold_boundary_matches_official_yes_knob(self) -> None:
        self.assertEqual(YES, 0.45)
        just_below = FakeDecider({**SAFE_SCORES, "args_grounded": 0.449})
        decision = review_tool_call(
            tool_name="get_resource",
            arguments={"resource": "web-api-prod"},
            conversation="user: look at web-api-prod",
            decider=just_below,
        )
        self.assertEqual(decision.kind, "guide")

    def test_render_conversation(self) -> None:
        self.assertEqual(render_conversation([]), "(no conversation yet)")

        messages_str = [{"role": "user", "content": "Help with INC-001"}]
        self.assertIn("user: Help with INC-001", render_conversation(messages_str))

        messages_blocks = [
            {"role": "assistant", "content": [{"text": "Checking logs..."}]}
        ]
        self.assertIn("assistant: Checking logs...", render_conversation(messages_blocks))

    def test_build_state(self) -> None:
        state = build_state("user: latency high", "get_metrics", {"resource": "web-api-prod"})
        self.assertIn("--- CONVERSATION ---", state)
        self.assertIn("--- PROPOSED TOOL CALL ---", state)
        self.assertIn("tool: get_metrics", state)
        self.assertIn('"resource": "web-api-prod"', state)

    def test_noul_parsing(self) -> None:
        self.assertEqual(_noul({"q": {"noul": 0.75}}, "q"), 0.75)
        self.assertEqual(_noul({"q": 0.65}, "q"), 0.65)
        with self.assertRaises(KeyError):
            _noul({}, "missing_key")
        with self.assertRaises(KeyError):
            _noul({"q": "not-a-number"}, "q")


if __name__ == "__main__":
    unittest.main()
