import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "ci_scope", Path(__file__).parents[1] / "ci_scope.py"
)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class ScopeTests(unittest.TestCase):
    def test_inputs_and_fallbacks(self):
        self.assertFalse(ci.needs_checks(["docs/format.md", "docs/conformance.md"]))
        for path in [
            "README.md",
            "pyproject.toml",
            "sparecode/cli.py",
            "examples/a.json",
            "tests/test_cli.py",
            ".github/workflows/test.yml",
            "unknown",
            "docs/tool.py",
            "AGENTS.md",
        ]:
            self.assertTrue(ci.needs_checks(["docs/a.md", path]))
        self.assertTrue(ci.needs_checks([]))
        for event in ["push", "workflow_dispatch", "merge_group", "unknown"]:
            self.assertTrue(ci.full_checks(event, {}))
        self.assertTrue(ci.full_checks("pull_request", {}))
        event = {"pull_request": {"base": {"sha": "a" * 40}, "head": {"sha": "b" * 40}}}

        def fail(args):
            raise subprocess.CalledProcessError(1, args)

        self.assertTrue(ci.full_checks("pull_request", event, fail))
        self.assertTrue(ci.full_checks("pull_request", event, lambda _: b"docs/a.md"))
        self.assertTrue(ci.full_checks("pull_request", event, lambda _: b""))
        self.assertTrue(ci.full_checks("pull_request", {"pull_request": {"base": {"sha": "bad"}, "head": {"sha": "b" * 40}}}))

    def test_git_renames_deletions_and_multiple_areas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def git(args):
                return subprocess.check_output(
                    ["git", *args], cwd=root, stderr=subprocess.DEVNULL
                )

            def commit():
                git(["add", "."])
                git(
                    [
                        "-c",
                        "user.name=Test",
                        "-c",
                        "user.email=test@example.invalid",
                        "commit",
                        "-qm",
                        "fixture",
                    ]
                )
                return git(["rev-parse", "HEAD"]).decode().strip()

            git(["init", "-q"])
            (root / "src").mkdir()
            (root / "docs").mkdir()
            (root / "src/a").write_text("shared")
            (root / "docs/a.md").write_text("docs")
            base = commit()

            def check(head):
                def run(args):
                    return git(args[1:])

                return ci.full_checks(
                    "pull_request",
                    {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}},
                    run,
                )

            (root / "src/a").rename(root / "docs/moved.md")
            self.assertTrue(check(commit()))
            git(["reset", "--hard", base])
            (root / "docs/a.md").rename(root / "src/from-doc.md")
            self.assertTrue(check(commit()))
            git(["reset", "--hard", base])
            (root / "src/a").unlink()
            self.assertTrue(check(commit()))
            git(["reset", "--hard", base])
            (root / "docs/a.md").unlink()
            self.assertFalse(check(commit()))
            (root / "src/b").write_text("shared")
            self.assertTrue(check(commit()))
