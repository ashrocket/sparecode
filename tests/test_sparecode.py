import contextlib
from decimal import Decimal
import io
import json
import os
import shlex
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

from sparecode.agent import messages_for, parse_action, run_agent
from sparecode.cli import main
from sparecode.provider import HarnessError, Ledger, Price, Provider, request_json
from sparecode.repo import Repository, load_session


class RepoFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write("calc.py", "def add(a, b):\n    return a - b\n")
        self.write("keep.txt", "user work\n")
        self.write(".gitignore", "ignored/\n.env\n")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

class RepositoryCase(RepoFixture):
    def test_proposal_does_not_mutate_and_apply_preserves_unrelated_dirty_work(self):
        self.write("keep.txt", "new unrelated dirty work\n")
        repo = Repository(self.root)
        repo.read("calc.py")
        repo.replace("calc.py", "a - b", "a + b")
        self.assertIn("a - b", (self.root / "calc.py").read_text())
        self.assertIn("+    return a + b", repo.diff())
        self.assertEqual(repo.apply(), ["calc.py"])
        self.assertIn("a + b", (self.root / "calc.py").read_text())
        self.assertEqual((self.root / "keep.txt").read_text(), "new unrelated dirty work\n")

    def test_entire_conflict_preflight_prevents_partial_apply(self):
        repo = Repository(self.root)
        for file in ("calc.py", "keep.txt"):
            repo.read(file)
        repo.replace("calc.py", "a - b", "a + b")
        repo.replace("keep.txt", "user work", "agent work")
        self.write("keep.txt", "concurrent work")
        with self.assertRaisesRegex(HarnessError, "Conflict"):
            repo.apply()
        self.assertIn("a - b", (self.root / "calc.py").read_text())
        self.assertEqual((self.root / "keep.txt").read_text(), "concurrent work")

    def test_requires_read_and_unique_match(self):
        repo = Repository(self.root)
        with self.assertRaisesRegex(HarnessError, "Read"):
            repo.replace("calc.py", "a - b", "a + b")
        repo.read("calc.py")
        with self.assertRaisesRegex(HarnessError, "exactly once"):
            repo.replace("calc.py", "a", "b")

    def test_ignored_tracked_and_secret_files_are_excluded(self):
        for name in (".env", "secret.pem", "ignored/private.txt", ".npmrc", ".ssh/config"):
            self.write(name, "not model context")
            subprocess.run(["git", "-C", str(self.root), "add", "-f", name], check=True)
        repo = Repository(self.root)
        for name in (".env", "secret.pem", "ignored/private.txt", ".npmrc", ".ssh/config"):
            self.assertNotIn(name, repo.files)
            with self.assertRaises(HarnessError):
                repo.read(name)
        self.assertNotIn("not model context", repo.search("model"))

    def test_custom_ignore_patterns(self):
        self.write(".sparecodeignore", "private/\n*.cert\n")
        self.write("private/x.py", "secret")
        self.write("x.cert", "secret")
        repo = Repository(self.root)
        self.assertNotIn("private/x.py", repo.files)
        self.assertNotIn("x.cert", repo.files)

    def test_escape_and_symlink_paths(self):
        outside = self.base / "outside.txt"
        outside.write_text("private")
        (self.root / "link").symlink_to(outside)
        (self.root / "dirlink").symlink_to(self.base, target_is_directory=True)
        repo = Repository(self.root)
        for name in ("../outside.txt", "/tmp/outside", "link", "dirlink/outside.txt", ".git/config", "./calc.py"):
            with self.subTest(name=name), self.assertRaises(HarnessError):
                repo.path(name)

    def test_symlink_added_after_proposal_is_refused(self):
        repo = Repository(self.root)
        repo.read("calc.py")
        repo.replace("calc.py", "a - b", "a + b")
        (self.root / "calc.py").unlink()
        (self.root / "calc.py").symlink_to(self.root / "keep.txt")
        with self.assertRaisesRegex(HarnessError, "Symlinks"):
            repo.apply()
        self.assertEqual((self.root / "keep.txt").read_text(), "user work\n")

    def test_create_and_executable_mode(self):
        (self.root / "calc.py").chmod(0o755)
        repo = Repository(self.root)
        repo.read("calc.py")
        repo.replace("calc.py", "a - b", "a + b")
        repo.create("new/test.py", "assert 1 + 1 == 2\n")
        repo.apply()
        self.assertEqual(stat.S_IMODE((self.root / "calc.py").stat().st_mode), 0o755)
        self.assertTrue((self.root / "new/test.py").exists())

    def test_new_file_conflict(self):
        repo = Repository(self.root)
        repo.create("new.py", "agent")
        self.write("new.py", "user")
        with self.assertRaises(HarnessError):
            repo.apply()
        self.assertEqual((self.root / "new.py").read_text(), "user")

    def test_new_file_now_ignored(self):
        repo = Repository(self.root)
        repo.create("new.py", "agent")
        self.write(".gitignore", "new.py\n")
        with self.assertRaisesRegex(HarnessError, "ignored"):
            repo.apply()

    def test_nested_guidance_is_pinned_and_create_reconsiders(self):
        self.write("AGENTS.md", "Root rules")
        self.write("src/AGENTS.md", "Nested rules")
        self.write("src/code.py", "x = 1")
        repo = Repository(self.root)
        with self.assertRaisesRegex(HarnessError, "guidance loaded"):
            repo.create("src/new.py", "x = 2")
        repo.create("src/new.py", "x = 2")
        repo.read("src/code.py")
        messages = messages_for(repo, "fix", "files", [], [], 24000)
        self.assertIn("Root rules", messages[1]["content"])
        self.assertIn("Nested rules", messages[1]["content"])

    def test_bounded_read_and_binary_exclusion(self):
        self.write("huge.py", "x" * 12000)
        self.write("binary.bin", "\x00private")
        repo = Repository(self.root)
        self.assertLessEqual(len(repo.read("huge.py").encode()), 6000)
        with self.assertRaises(HarnessError):
            repo.read("binary.bin")

    def test_no_newline_diff_is_valid(self):
        self.write("keep.txt", "before")
        repo = Repository(self.root)
        repo.read("keep.txt")
        repo.replace("keep.txt", "before", "after")
        result = subprocess.run(["git", "-C", str(self.root), "apply", "--check", "-"],
                                input=repo.diff(), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_compaction_keeps_task_guidance_and_whole_pair(self):
        self.write("AGENTS.md", "Never discard these rules")
        repo = Repository(self.root)
        history = [[{"role": "assistant", "content": "old " * 3000},
                    {"role": "user", "content": "old result"}],
                   [{"role": "assistant", "content": "latest"},
                    {"role": "user", "content": "latest result"}]]
        messages = messages_for(repo, "original task", "", history, ["read calc.py"], 4000)
        text = json.dumps(messages)
        self.assertNotIn("old result", text)
        self.assertIn("latest result", text)
        self.assertIn("original task", text)
        self.assertIn("Never discard these rules", text)
        self.assertEqual(len(messages), 4)

    def test_dry_run_needs_no_credentials(self):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["run", "fix add", "--repo", str(self.root), "--dry-run"]), 0)


class LedgerCase(unittest.TestCase):
    def test_reservation_stops_before_over_budget_request(self):
        ledger = Ledger(Price(Decimal("0.001"), Decimal("0.001")), "0.01")
        with self.assertRaisesRegex(HarnessError, "Budget stop"):
            ledger.reserve([{"role": "user", "content": "fix"}], 50)
        self.assertEqual(ledger.requests, [])

    def test_missing_usage_retains_reservation(self):
        ledger = Ledger(Price(Decimal("0.000001"), Decimal("0.000002")))
        entry = ledger.reserve([], 100)
        reserved = ledger.accounted
        ledger.settle(entry, {})
        self.assertEqual(ledger.accounted, reserved)
        self.assertIn("missing", entry["status"])

    def test_actual_usage_and_reported_cost_accounting(self):
        ledger = Ledger(Price(Decimal("0.000001"), Decimal("0.000002")))
        entry = ledger.reserve([], 100)
        ledger.settle(entry, {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.00009})
        self.assertEqual(ledger.accounted, Decimal("0.00009"))
        self.assertEqual(ledger.charged_tokens, 30)

    def test_reported_cost_is_respected_when_token_usage_missing(self):
        ledger = Ledger(Price(Decimal("0.000001"), Decimal("0.000002")))
        entry = ledger.reserve([], 100)
        with self.assertRaisesRegex(HarnessError, "Reported cost"):
            ledger.settle(entry, {"cost": "0.50"})
        self.assertEqual(ledger.accounted, Decimal("0.50"))

    def test_unexpected_token_overrun_stops(self):
        ledger = Ledger(Price(Decimal(0), Decimal(0)))
        entry = ledger.reserve([], 100)
        with self.assertRaisesRegex(HarnessError, "exceeded"):
            ledger.settle(entry, {"prompt_tokens": 10, "completion_tokens": 101})

    def test_total_token_limit(self):
        ledger = Ledger(Price(Decimal(0), Decimal(0)), max_tokens=10)
        with self.assertRaisesRegex(HarnessError, "Token stop"):
            ledger.reserve([], 20)

    def test_nonfinite_and_negative_prices_rejected(self):
        for value in ("NaN", "Infinity", "-1"):
            with self.subTest(value=value), self.assertRaises(HarnessError):
                Ledger(Price(Decimal(0), Decimal(0)), value)

    def test_catalog_uses_highest_tier_and_refuses_request_pricing(self):
        price = Price.from_model({"pricing": {"prompt": ".1", "completion": ".2", "overrides": [
            {"prompt": ".3", "completion": ".4"}]}})
        self.assertEqual(price.input, Decimal(".3"))
        with self.assertRaises(HarnessError):
            Price.from_model({"pricing": {"request": "1", "prompt": "0", "completion": "0"}})


class FakeProvider:
    kind = "fixture"
    model = "fixture-model"
    context_length = 100000
    price = Price(Decimal("0.00000012"), Decimal("0.0000008"))

    def __init__(self, actions, fail=False):
        self.actions = iter(actions)
        self.calls = 0
        self.fail = fail

    def complete(self, messages, max_output):
        self.calls += 1
        if self.fail:
            raise HarnessError("Connection uncertain")
        return {"choices": [{"message": {"content": json.dumps(next(self.actions))}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50}}


class AgentCase(RepoFixture):
    def test_full_proposal_apply_and_verify(self):
        provider = FakeProvider([
            {"action": "read", "path": "calc.py"},
            {"action": "replace", "path": "calc.py", "old": "a - b", "new": "a + b"},
            {"action": "finish", "summary": "Fixed addition; tests not run."}])
        folder, metadata = run_agent(Repository(self.root), provider, "Fix addition", self.base / "state", progress=lambda _: None)
        self.assertEqual(metadata["status"], "proposal_ready")
        self.assertEqual(provider.calls, 3)
        self.assertIn("a - b", (self.root / "calc.py").read_text())
        self.write("verify.py", "from calc import add\nassert add(2, 3) == 5\n")
        with contextlib.redirect_stdout(io.StringIO()):
            result = main(["apply", str(folder), "--check", shlex.join([sys.executable, "verify.py"])])
        self.assertEqual(result, 0)
        _, saved = load_session(folder)
        self.assertEqual(saved["verification"]["exit_code"], 0)
        self.assertEqual(stat.S_IMODE((folder / "session.json").stat().st_mode), 0o600)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["apply", str(folder)]), 2)

    def test_network_failure_reserved_and_not_retried(self):
        provider = FakeProvider([], fail=True)
        with self.assertRaisesRegex(HarnessError, "Connection uncertain"):
            run_agent(Repository(self.root), provider, "fix", self.base / "state", progress=lambda _: None)
        session = next((self.base / "state").glob("*/session.json"))
        data = json.loads(session.read_text())
        self.assertEqual(data["status"], "stopped")
        self.assertEqual(data["usage"]["requests"][0]["status"], "reserved")
        self.assertGreater(Decimal(data["usage"]["accounted_usd"]), 0)
        self.assertEqual(provider.calls, 1)

    def test_malformed_actions_stop_after_three(self):
        provider = FakeProvider([{"action": "execute", "command": "bad"}] * 3)
        with self.assertRaisesRegex(HarnessError, "Three consecutive"):
            run_agent(Repository(self.root), provider, "fix", self.base / "state", progress=lambda _: None)
        self.assertEqual(provider.calls, 3)

    def test_budget_stop_makes_zero_calls(self):
        provider = FakeProvider([])
        with self.assertRaisesRegex(HarnessError, "Budget stop"):
            run_agent(Repository(self.root), provider, "fix", self.base / "state", budget="0", progress=lambda _: None)
        self.assertEqual(provider.calls, 0)

    def test_turn_limit_preserves_partial_proposal(self):
        provider = FakeProvider([{"action": "create", "path": "new.txt", "content": "hello"}])
        with self.assertRaisesRegex(HarnessError, "Turn limit"):
            run_agent(Repository(self.root), provider, "fix", self.base / "state", max_turns=1, progress=lambda _: None)
        folder = next((self.base / "state").iterdir())
        _, data = load_session(folder)
        self.assertEqual(data["edits"]["new.txt"], "hello")
        self.assertFalse((self.root / "new.txt").exists())


    def test_failed_check_leaves_changes_and_records_failure(self):
        provider = FakeProvider([
            {"action": "create", "path": "new.txt", "content": "hello"},
            {"action": "finish", "summary": "Created new.txt"}])
        folder, _ = run_agent(Repository(self.root), provider, "create", self.base / "state", progress=lambda _: None)
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["apply", str(folder), "--check", shlex.join([sys.executable, "-c", "raise SystemExit(7)"])])
        self.assertEqual(code, 1)
        _, data = load_session(folder)
        self.assertEqual(data["status"], "applied_check_failed")
        self.assertEqual(data["verification"]["exit_code"], 7)
        self.assertEqual((self.root / "new.txt").read_text(), "hello")

    def test_truncated_model_reply_is_not_applied(self):
        provider = FakeProvider([])
        with patch.object(provider, "complete", return_value={
            "choices": [{"finish_reason": "length", "message": {"content": '{"action":"create"'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100}}):
            with self.assertRaisesRegex(HarnessError, "Output limit"):
                run_agent(Repository(self.root), provider, "create", self.base / "state", progress=lambda _: None)
        data = json.loads(next((self.base / "state").glob("*/session.json")).read_text())
        self.assertEqual(data["edits"], {})

    def test_session_cannot_be_saved_into_source_context(self):
        provider = FakeProvider([])
        with self.assertRaisesRegex(HarnessError, "outside"):
            run_agent(Repository(self.root), provider, "fix", self.root / "state", progress=lambda _: None)
        self.assertEqual(provider.calls, 0)

    def test_null_content_is_bounded_and_saved_as_stopped(self):
        provider = FakeProvider([])
        with patch.object(provider, "complete", return_value={
            "choices": [{"finish_reason": "stop", "message": {"content": None}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100}}):
            with self.assertRaisesRegex(HarnessError, "Three consecutive"):
                run_agent(Repository(self.root), provider, "fix", self.base / "state", progress=lambda _: None)
        data = json.loads(next((self.base / "state").glob("*/session.json")).read_text())
        self.assertEqual(data["status"], "stopped")
        self.assertEqual(len(data["usage"]["requests"]), 3)


class HTTPCase(unittest.TestCase):
    def test_openrouter_body_pins_price_and_privacy(self):
        info = {"id": "test", "context_length": 32000, "supported_parameters": ["response_format"],
                "pricing": {"prompt": "0.00000012", "completion": "0.0000008"}}
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"}), \
                patch("sparecode.provider.catalog", return_value=[info]), \
                patch("sparecode.provider.request_json", return_value={}) as request:
            provider = Provider(model="test")
            provider.complete([], 100)
            body = request.call_args.args[1]
            self.assertEqual(body["provider"]["max_price"], {"prompt": .12, "completion": .8, "request": 0})
            self.assertEqual(body["provider"]["data_collection"], "deny")
            self.assertFalse(body["provider"]["allow_fallbacks"])
            self.assertNotIn("models", body)

    def test_local_mode_refuses_remote_and_cloud_and_sends_no_key(self):
        for base, model in (("https://example.com/v1", "test"), (None, "test-cloud")):
            with self.assertRaises(HarnessError):
                Provider("local", model=model, base_url=base)
        with patch.dict(os.environ, {"SPARECODE_API_KEY": "never-send"}):
            self.assertIsNone(Provider("local").key)

    def test_insecure_host_and_embedded_key_refused(self):
        for base in ("http://example.com/v1", "https://key@example.com/v1", "https://example.com/v1?key=x"):
            with self.assertRaises(HarnessError):
                Provider("compatible", base_url=base)

    def test_http_redirect_is_never_followed(self):
        class Handler(BaseHTTPRequestHandler):
            count = 0
            def do_GET(self):
                Handler.count += 1
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.end_headers()
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaisesRegex(HarnessError, "redirect"):
                request_json(f"http://127.0.0.1:{server.server_port}/", key="test-only")
            self.assertEqual(Handler.count, 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_json_protocol(self):
        self.assertEqual(parse_action('```json\n{"action":"files"}\n```')["action"], "files")
        for value in ("", "not JSON", "[]", '{"action":42}'):
            with self.assertRaises(HarnessError):
                parse_action(value)


if __name__ == "__main__":
    unittest.main()
