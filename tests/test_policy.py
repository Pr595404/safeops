from __future__ import annotations

import unittest

from safeops.policy import classify_tool
from safeops.tools import terminate_instance


class PolicyTests(unittest.TestCase):
    def test_read_only_tools_are_allowed(self) -> None:
        for name in (
            "list_incidents",
            "get_incident",
            "get_resource",
            "get_metrics",
            "get_logs",
            "list_alarms",
        ):
            decision = classify_tool(name)
            self.assertTrue(decision.allowed, name)

    def test_destructive_tools_are_denied(self) -> None:
        for name in ("reboot_instance", "terminate_instance", "delete_volume", "execute_shell"):
            decision = classify_tool(name)
            self.assertFalse(decision.allowed, name)
            self.assertIn("destructive", decision.reason.lower())

    def test_unknown_tools_are_denied(self) -> None:
        decision = classify_tool("drop_database")
        self.assertFalse(decision.allowed)

    def test_destructive_stub_cannot_execute(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            terminate_instance("i-0safeops01")
        self.assertIn("destructive", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
