"""Deterministic tool policy. Independent of any model.

Destructive names are blocked in code. A language model cannot override this list.
"""

from __future__ import annotations

from dataclasses import dataclass

# Read-only investigation tools over synthetic data only.
ALLOWED_READ_ONLY_TOOLS = frozenset(
    {
        "list_incidents",
        "get_incident",
        "get_resource",
        "get_metrics",
        "get_logs",
        "list_alarms",
    }
)

# Names that must never execute, even if a model proposes them.
DESTRUCTIVE_TOOLS = frozenset(
    {
        "reboot_instance",
        "terminate_instance",
        "delete_volume",
        "execute_shell",
        "put_item",
        "update_security_group",
    }
)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


def classify_tool(tool_name: str) -> PolicyDecision:
    """Return whether `tool_name` may run. Does not call a model."""
    name = (tool_name or "").strip()
    if name in DESTRUCTIVE_TOOLS:
        return PolicyDecision(
            allowed=False,
            reason=(
                f"Denied by deterministic policy: '{name}' is destructive. "
                "SafeOps only permits read-only diagnostic tools on synthetic data."
            ),
        )
    if name in ALLOWED_READ_ONLY_TOOLS:
        return PolicyDecision(
            allowed=True,
            reason=f"Allowed by policy: '{name}' is a read-only diagnostic tool.",
        )
    return PolicyDecision(
        allowed=False,
        reason=(
            f"Denied by deterministic policy: '{name}' is not on the allow-list "
            "of mock read-only diagnostic tools."
        ),
    )
