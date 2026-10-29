from __future__ import annotations

from typing import Any


class FakeDecider:
    def __init__(self, noul: dict[str, float]) -> None:
        self.noul = noul
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def ask(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        self.calls.append((state, dict(questions)))
        missing = set(questions) - set(self.noul)
        if missing:
            raise AssertionError(f"FakeDecider missing scores for {missing}")
        return {key: {"type": "noul", "noul": self.noul[key]} for key in questions}


SAFE_SCORES = {
    "args_grounded": 0.92,
    "premature": 0.08,
    "diagnostic_appropriate": 0.88,
}
