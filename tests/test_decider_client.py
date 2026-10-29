from __future__ import annotations

import json
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from safeops.decider_client import Decider, ServerUnavailable


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/v1/systemone":
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            self.server.last_body = body  # type: ignore[attr-defined]
            payload = {
                "model": "strands-decider-2B-qwen3.5-v1-2610",
                "answers": {
                    key: {"type": "noul", "noul": 0.7} for key in body["questions"]
                },
                "usage": {"input_tokens": 10, "output_tokens": 1},
                "latency_ms": 1.0,
            }
            raw = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            payload = {"status": "ok", "model": "strands-decider-2B-qwen3.5-v1-2610"}
            raw = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class DeciderClientTests(unittest.TestCase):
    def test_ask_posts_official_systemone_shape(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            client = Decider(url=f"http://{host}:{port}", timeout=5)
            questions = {
                "args_grounded": Decider.noul(
                    "Are the tool's argument values grounded in facts the user actually provided?",
                    {"true": "grounded", "false": "guessed"},
                )
            }
            answers = client.ask("state text", questions)
            self.assertEqual(answers["args_grounded"]["noul"], 0.7)
            body = server.last_body  # type: ignore[attr-defined]
            self.assertEqual(body["state"], "state text")
            self.assertEqual(body["model"], "hobson-latest")
            self.assertEqual(body["questions"]["args_grounded"]["type"], "noul")
            self.assertEqual(client.calls, 1)
            self.assertEqual(client.input_tokens, 10)
        finally:
            server.shutdown()
            server.server_close()

    def test_health_check_succeeds(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            client = Decider(url=f"http://{host}:{port}", timeout=5)
            health = client.health()
            self.assertEqual(health["status"], "ok")
        finally:
            server.shutdown()
            server.server_close()

    def test_server_unavailable_raises_cleanly(self) -> None:
        # Port 1 is rarely/never bound to an HTTP server
        client = Decider(url="http://127.0.0.1:1", timeout=0.5)
        with self.assertRaises(ServerUnavailable) as ctx:
            client.health()
        self.assertIn("strands-decider", str(ctx.exception))

    def test_question_builders(self) -> None:
        choice_q = Decider.choice("Pick one", {"a": "option a", "b": "option b"})
        self.assertEqual(choice_q["type"], "choice")
        self.assertEqual(choice_q["criteria"]["a"], "option a")

        score_q = Decider.score("Rate severity", ["low", "medium", "high"])
        self.assertEqual(score_q["type"], "score")
        self.assertEqual(len(score_q["criteria"]), 3)


if __name__ == "__main__":
    unittest.main()
