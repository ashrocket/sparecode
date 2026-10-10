#!/usr/bin/env python3
"""Exercise real HTTP + CLI + edit + verification with a scripted model fixture.

This is not a real model or a coding-quality benchmark. No account/key is needed.
Everything happens in a disposable temporary repository.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def demo():
    actions = [
        {"action": "read", "path": "calc.py"},
        {"action": "replace", "path": "calc.py", "old": "a - b", "new": "a + b"},
        {"action": "finish", "summary": "Changed subtraction to addition. Run verify.py."},
    ]
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            if self.path != "/v1/chat/completions" or not actions:
                self.send_error(400)
                return
            reply = {"choices": [{"message": {"role": "assistant", "content": json.dumps(actions.pop(0))},
                                  "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": 650, "completion_tokens": 80}}
            data = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix="sparecode-demo-") as directory:
            base = Path(directory)
            repo = base / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
            (repo / "verify.py").write_text("from calc import add\nassert add(2, 3) == 5\nprint('addition check passed')\n")
            env = dict(os.environ, SPARECODE_DEMO_KEY="offline-fixture-only")
            cli = Path(__file__).resolve().parents[1] / "bin" / "sparecode"
            print("Offline integration demo: scripted provider, no paid model calls.", flush=True)
            result = subprocess.run([
                sys.executable, str(cli), "run", "Fix addition in calc.py", "--repo", str(repo),
                "--provider", "compatible", "--model", "fixture-model",
                "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--key-env", "SPARECODE_DEMO_KEY",
                "--input-price", "0.12", "--output-price", "0.80", "--budget", "0.05",
                "--state-dir", str(base / "sessions"), "--apply",
                "--check", shlex.join([sys.executable, "verify.py"]),
            ], env=env, timeout=30)
            assert result.returncode == 0, f"CLI exit {result.returncode}"
            assert (repo / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
            session = json.loads(next((base / "sessions").glob("*/session.json")).read_text())
            assert session["status"] == "applied"
            assert session["verification"]["exit_code"] == 0
            assert len(requests) == 3
            assert all(r["max_tokens"] == 1800 for r in requests)
            print("PASS: HTTP adapter → three model actions → proposal → apply → verification.")
            return 0
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == "__main__":
    raise SystemExit(demo())
