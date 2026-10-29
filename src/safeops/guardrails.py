"""Reusable guardrails decision pattern.

The Decider classifies. Python owns thresholds and side effects.

Order of checks (fail closed):
1. Deterministic policy — block destructive / unknown tools with no model call.
2. Strands Decider noul questions — grounding and diagnostic appropriateness.
3. Code maps probabilities to proceed | guide | deny.

Question types and the /v1/systemone request follow
https://github.com/strands-labs/strands-decider/blob/main/examples/strands/tool_call_intervention.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from safeops.decider_client import Decider
from safeops.policy import classify_tool

# Official example uses 0.45 as an illustrative "yes" threshold. Code owns this knob.
YES = 0.45

QUESTIONS = {
    "args_grounded": Decider.noul(
        "Are the tool's argument values grounded in facts the user actually provided?",
        {
            "true": "every argument value traces back to something the user said",
            "false": "an argument value was guessed or invented, not stated by the user",
        },
    ),
    "premature": Decider.noul(
        "Is it premature to call this tool now, before clarifying with the user?",
        {
            "true": "the assistant should ask a clarifying question before calling the tool",
            "false": "there is nothing left to clarify; calling now is appropriate",
        },
    ),
    "diagnostic_appropriate": Decider.noul(
        "Is this proposed tool call a grounded, appropriate diagnostic for the incident?",
        {
            "true": (
                "the tool is a read-only diagnostic whose arguments match the incident "
                "the user described"
            ),
            "false": (
                "the tool is unrelated, speculative, or not a reasonable next diagnostic"
            ),
        },
    ),
}


class DeciderLike(Protocol):
    def ask(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class GuardrailDecision:
    """Framework-agnostic verdict. Map to Strands Deny/Guide/Proceed at the edge."""

    kind: str  # "deny" | "guide" | "proceed"
    feedback: str
    scores: dict[str, float] = field(default_factory=dict)
    policy_reason: str = ""


def render_conversation(messages: list[dict[str, Any]]) -> str:
    """Flatten Strands-style message lists: role + text blocks only."""
    lines: list[str] = []
    for message in messages:
        role = message.get("role", "unknown")
        content = message.get("content", [])
        if isinstance(content, str):
            lines.append(f"{role}: {content}")
            continue
        for block in content:
            if isinstance(block, dict) and "text" in block:
                lines.append(f"{role}: {block['text']}")
    return "\n".join(lines) if lines else "(no conversation yet)"


def build_state(conversation: str, tool_name: str, arguments: dict[str, Any]) -> str:
    return (
        "A conversation between a user and an AI assistant is below, followed by a "
        "tool call the assistant now wants to make.\n\n"
        f"--- CONVERSATION ---\n{conversation}\n\n"
        f"--- PROPOSED TOOL CALL ---\ntool: {tool_name}\n"
        f"arguments: {json.dumps(arguments)}"
    )


def _noul(answers: dict[str, Any], key: str) -> float:
    if key not in answers:
        raise KeyError(f"missing answer for question {key!r}")
    value = answers[key]
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict) and "noul" in value:
        return float(value["noul"])
    raise KeyError(f"expected noul answer for {key!r}, got {value!r}")


def review_tool_call(
    *,
    tool_name: str,
    arguments: dict[str, Any] | None,
    conversation: str,
    decider: DeciderLike,
    yes_threshold: float = YES,
) -> GuardrailDecision:
    """Classify a proposed tool call. Never executes the tool."""
    policy = classify_tool(tool_name)
    if not policy.allowed:
        return GuardrailDecision(
            kind="deny",
            feedback=policy.reason,
            policy_reason=policy.reason,
        )

    state = build_state(conversation, tool_name, arguments or {})
    answers = decider.ask(state, QUESTIONS)
    args_grounded = _noul(answers, "args_grounded")
    premature = _noul(answers, "premature")
    diagnostic_appropriate = _noul(answers, "diagnostic_appropriate")
    scores = {
        "args_grounded": args_grounded,
        "premature": premature,
        "diagnostic_appropriate": diagnostic_appropriate,
    }

    if args_grounded < yes_threshold:
        return GuardrailDecision(
            kind="guide",
            feedback=(
                "The arguments are not grounded in anything the user said -- they look "
                "guessed. Ask the user to confirm the values instead of inventing them."
            ),
            scores=scores,
            policy_reason=policy.reason,
        )
    if premature >= yes_threshold:
        return GuardrailDecision(
            kind="guide",
            feedback=(
                "It is too early to call this tool. Clarify with the user first, then "
                "try again."
            ),
            scores=scores,
            policy_reason=policy.reason,
        )
    if diagnostic_appropriate < yes_threshold:
        return GuardrailDecision(
            kind="guide",
            feedback=(
                "This tool call does not look like an appropriate diagnostic for the "
                "incident. Pick a read-only tool that matches the reported resource "
                "and symptoms, or ask a clarifying question."
            ),
            scores=scores,
            policy_reason=policy.reason,
        )
    return GuardrailDecision(
        kind="proceed",
        feedback="Diagnostic tool call is grounded and appropriate.",
        scores=scores,
        policy_reason=policy.reason,
    )
