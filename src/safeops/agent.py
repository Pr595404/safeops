"""Strands agent wiring. Do not import from unit tests.

Default Bedrock model id matches the official Decider example:
  us.anthropic.claude-haiku-4-5-20251001-v1:0
Credentials come from the environment / AWS SDK default chain. Never hardcoded.

Official seam: InterventionHandler.before_tool_call returning Proceed, Guide, or Deny.
See https://github.com/strands-labs/strands-decider/blob/main/examples/strands/tool_call_intervention.py
"""

from __future__ import annotations

import os
from typing import Any

from strands import Agent, tool
from strands.interventions import Deny, Guide, InterventionHandler, Proceed

from safeops import tools as mock_tools
from safeops.decider_client import Decider
from safeops.guardrails import GuardrailDecision, render_conversation, review_tool_call

DEFAULT_BEDROCK_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

SYSTEM_PROMPT = (
    "You are SafeOps, an incident investigation assistant. You diagnose synthetic "
    "cloud incidents using read-only mock tools only. Never reboot, terminate, "
    "delete, or otherwise mutate resources. Never guess resource ids or names; "
    "if the user did not name a resource, ask. Prefer list_incidents, get_incident, "
    "get_resource, get_metrics, get_logs, and list_alarms. All data is synthetic."
)


def to_strands_action(decision: GuardrailDecision) -> Deny | Guide | Proceed:
    if decision.kind == "deny":
        return Deny(reason=decision.feedback)
    if decision.kind == "guide":
        return Guide(feedback=decision.feedback)
    return Proceed()


class SafeOpsToolReviewer(InterventionHandler):
    """before_tool_call gate: policy first, then Decider noul questions."""

    name = "safeops-tool-call-reviewer"

    def __init__(self, decider: Decider) -> None:
        self._decider = decider
        self.log: list[dict[str, object]] = []

    def before_tool_call(self, event, **kwargs):
        name = event.tool_use["name"]
        arguments = event.tool_use.get("input") or {}
        conversation = render_conversation(event.agent.messages)
        decision = review_tool_call(
            tool_name=name,
            arguments=arguments,
            conversation=conversation,
            decider=self._decider,
        )
        self.log.append({"tool": name, "kind": decision.kind, "scores": decision.scores})
        return to_strands_action(decision)


@tool
def list_incidents() -> str:
    """List synthetic open incidents."""
    return mock_tools.list_incidents()


@tool
def get_incident(incident_id: str) -> str:
    """Return one synthetic incident by id, for example INC-001."""
    return mock_tools.get_incident(incident_id)


@tool
def get_resource(resource: str) -> str:
    """Describe a synthetic resource by name (web-api-prod) or mock id."""
    return mock_tools.get_resource(resource)


@tool
def get_metrics(resource: str) -> str:
    """Return synthetic latency and error metrics for a resource."""
    return mock_tools.get_metrics(resource)


@tool
def get_logs(resource: str) -> str:
    """Return synthetic application logs for a resource."""
    return mock_tools.get_logs(resource)


@tool
def list_alarms() -> str:
    """List synthetic alarms."""
    return mock_tools.list_alarms()


@tool
def terminate_instance(resource_id: str) -> str:
    """Must never be used. Destructive. Deterministic policy denies this tool."""
    return mock_tools.terminate_instance(resource_id)


DIAGNOSTIC_TOOLS = [
    list_incidents,
    get_incident,
    get_resource,
    get_metrics,
    get_logs,
    list_alarms,
    terminate_instance,
]


def build_agent(decider: Decider | None = None) -> Agent:
    decider = decider or Decider()
    reviewer = SafeOpsToolReviewer(decider)
    model_id = os.environ.get("SAFEOPS_BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID)
    agent = Agent(
        model=model_id,
        tools=DIAGNOSTIC_TOOLS,
        interventions=[reviewer],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )
    agent._safeops_reviewer = reviewer  # type: ignore[attr-defined]
    return agent


def run_investigation(user_request: str) -> str:
    decider = Decider()
    decider.health()
    agent = build_agent(decider)
    return str(agent(user_request))
