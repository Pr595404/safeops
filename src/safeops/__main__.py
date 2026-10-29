"""CLI entrypoint for SafeOps.

- `safeops review`: Guardrail review with scripted scores (offline) or `--live-decider` (local 2B server).
- `safeops investigate`: Live agent (Amazon Bedrock + local Decider server).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python -m safeops` from a checkout without installation.
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from safeops.guardrails import GuardrailDecision, review_tool_call  # noqa: E402
from safeops.policy import classify_tool  # noqa: E402


class ScriptedDecider:
    """Deterministic stand-in for unit/offline review. Not the 2B model."""

    def __init__(self, answers: dict[str, float]) -> None:
        self.answers = answers

    def ask(self, state, questions):
        return {key: {"type": "noul", "noul": self.answers[key]} for key in questions}


def _configure_terminal_encoding() -> None:
    """Ensure utf-8 output encoding across Windows and POSIX shells."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _print_decision(decision: GuardrailDecision) -> None:
    print(f"kind: {decision.kind}")
    print(f"feedback: {decision.feedback}")
    if decision.scores:
        print("scores:")
        for key, value in decision.scores.items():
            print(f"  {key}: {value:.3f}")


def parse_tool_arguments(raw: str, pairs: list[str] | None) -> dict:
    """Accept JSON, PowerShell-friendly single quotes, or --set key=value."""
    try:
        arguments = json.loads(raw)
    except json.JSONDecodeError:
        try:
            arguments = json.loads(raw.replace("'", '"'))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON passed to --args: {raw!r}") from exc
    if not isinstance(arguments, dict):
        raise ValueError("--args must be a JSON object")
    for item in pairs or []:
        if "=" not in item:
            raise ValueError(f"--set expects key=value, got {item!r}")
        key, value = item.split("=", 1)
        arguments[key] = value
    return arguments


def cmd_review(args: argparse.Namespace) -> int:
    policy = classify_tool(args.tool)
    print(f"policy: {'allow' if policy.allowed else 'deny'} - {policy.reason}")
    try:
        arguments = parse_tool_arguments(args.args, args.set)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.live_decider:
        from safeops.decider_client import Decider, ServerUnavailable

        decider = Decider(url=args.decider_url)
        try:
            decider.health()
        except ServerUnavailable as exc:
            print(f"Decider server unavailable: {exc}", file=sys.stderr)
            return 1
    else:
        decider = ScriptedDecider(
            {
                "args_grounded": args.args_grounded,
                "premature": args.premature,
                "diagnostic_appropriate": args.appropriate,
            }
        )

    decision = review_tool_call(
        tool_name=args.tool,
        arguments=arguments,
        conversation=args.conversation,
        decider=decider,
    )
    _print_decision(decision)
    return 0 if decision.kind != "deny" else 2


def cmd_investigate(args: argparse.Namespace) -> int:
    # Live path: Bedrock + local Decider server. Requires AWS credentials and local decider.
    try:
        from safeops.agent import run_investigation
    except ImportError as exc:
        print(
            "strands-agents is not installed. Install it with: pip install 'safeops[strands]'",
            f"({exc})",
            file=sys.stderr,
        )
        return 1

    from safeops.decider_client import ServerUnavailable

    try:
        print(run_investigation(args.prompt))
    except ServerUnavailable as exc:
        print(exc, file=sys.stderr)
        return 1
    except Exception as exc:
        # Gracefully handle missing AWS credentials or Bedrock access errors
        error_msg = str(exc)
        print(
            f"Agent execution failed: {error_msg}\n"
            "Ensure AWS credentials (AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY) "
            "and Bedrock model access are configured in your environment.",
            file=sys.stderr,
        )
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="safeops",
        description="Guarded investigation of synthetic cloud incidents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser(
        "review",
        help="Offline guardrail review with scripted noul scores or local Decider 2B.",
    )
    review.add_argument("--tool", required=True, help="Tool name to evaluate (e.g. get_logs, terminate_instance).")
    review.add_argument("--args", default="{}", help="Tool arguments as JSON string.")
    review.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Tool argument; repeatable. Preferred in PowerShell over escaping JSON.",
    )
    review.add_argument(
        "--conversation",
        default="user: Checkout API latency is high on web-api-prod (INC-001).",
        help="Simulated prior conversation history.",
    )
    review.add_argument(
        "--live-decider",
        action="store_true",
        help="Query a running Strands Decider HTTP server at STRANDS_DECIDER_URL instead of scripted scores.",
    )
    review.add_argument(
        "--decider-url",
        default=None,
        help="URL of the Strands Decider server (defaults to STRANDS_DECIDER_URL or http://127.0.0.1:8099).",
    )
    review.add_argument("--args-grounded", type=float, default=0.9, help="Scripted score for args_grounded.")
    review.add_argument("--premature", type=float, default=0.1, help="Scripted score for premature.")
    review.add_argument("--appropriate", type=float, default=0.85, help="Scripted score for diagnostic_appropriate.")
    review.set_defaults(func=cmd_review)

    live = sub.add_parser(
        "investigate",
        help=(
            "Live Strands agent (Amazon Bedrock + local strands-decider). "
            "Uses AWS credentials from the environment and may incur Bedrock cost. "
            "Do not run unless you intend that."
        ),
    )
    live.add_argument(
        "--prompt",
        default=(
            "INC-001: checkout latency is high on web-api-prod. "
            "Investigate with read-only tools only."
        ),
        help="Investigation task prompt for the Bedrock agent.",
    )
    live.set_defaults(func=cmd_investigate)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_terminal_encoding()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
