"""HTTP client for a running Strands Decider server.

Wire shape matches the official example client in
https://github.com/strands-labs/strands-decider/blob/main/examples/strands/_client.py

- POST {url}/v1/systemone with {state, model, questions}
- GET {url}/health
- Question helpers: noul / choice / score
- STRANDS_DECIDER_URL overrides the endpoint (default http://127.0.0.1:8099)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

NAME = "strands-decider"
ENV_URL = "STRANDS_DECIDER_URL"
SERVE_HINT = "strands-decider serve --port 8099"
# Official example sends this field; the server ignores it and answers as the
# loaded checkpoint. Kept so the request body matches the documented wire shape.
MODEL_ID = "hobson-latest"
DEFAULT_PORT = 8099
DEFAULT_URL = os.environ.get(ENV_URL, f"http://127.0.0.1:{DEFAULT_PORT}")


class ServerUnavailable(RuntimeError):
    """The Decider server is not answering."""


class Decider:
    """One state, many typed questions, one round trip to /v1/systemone."""

    def __init__(self, url: str | None = None, timeout: float = 120.0) -> None:
        target_url = url or os.environ.get(ENV_URL, f"http://127.0.0.1:{DEFAULT_PORT}")
        self.url = target_url.rstrip("/")
        self.timeout = timeout
        self.calls = 0
        self.input_tokens = 0
        self.last_latency_ms: float | None = None

    @staticmethod
    def noul(instructions: str, criteria: Mapping[str, str] | None = None) -> dict[str, Any]:
        question: dict[str, Any] = {"type": "noul", "instructions": instructions}
        if criteria:
            question["criteria"] = dict(criteria)
        return question

    @staticmethod
    def choice(instructions: str, criteria: Mapping[str, str]) -> dict[str, Any]:
        return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}

    @staticmethod
    def score(instructions: str, criteria: list[str]) -> dict[str, Any]:
        return {"type": "score", "instructions": instructions, "criteria": list(criteria)}

    def _unavailable(self, exc: Exception) -> ServerUnavailable:
        return ServerUnavailable(
            f"no {NAME} at {self.url} ({exc}). Start one with:\n  {SERVE_HINT}"
        )

    def ask(self, state: Any, questions: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps(
            {"state": state, "model": MODEL_ID, "questions": dict(questions)}
        ).encode()
        request = urllib.request.Request(
            f"{self.url}/v1/systemone",
            data=body,
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise self._unavailable(exc) from exc
        self.calls += 1
        self.input_tokens += payload.get("usage", {}).get("input_tokens", 0)
        self.last_latency_ms = payload.get("latency_ms")
        return payload["answers"]

    def health(self) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(f"{self.url}/health", timeout=10) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise self._unavailable(exc) from exc
