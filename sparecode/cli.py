"""Terminal interface. Model actions never select or execute shell commands."""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile

from . import __version__
from .agent import run_agent
from .provider import DEFAULT_MODEL, HarnessError, Price, Provider, catalog, money
from .repo import Repository, bounded, load_session, private_write, save_session


def display(text):
    # Provider/repository output must not emit terminal escape/control sequences.
    print("".join(c if c in "\n\t" or (ord(c) >= 32 and not 127 <= ord(c) <= 159)
                  else f"\\x{ord(c):02x}" for c in str(text)))


def positive(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def state_home():
    base = os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
    return str(Path(base) / "sparecode")


def provider_args(parser):
    parser.add_argument("--provider", choices=["openrouter", "local", "compatible"], default="openrouter")
    parser.add_argument("--model", help=f"default hosted model: {DEFAULT_MODEL}")
    parser.add_argument("--base-url", help="OpenAI-compatible API base, including /v1")
    parser.add_argument("--key-env", help="environment variable containing API key")
    parser.add_argument("--input-price", help="compatible endpoint USD per million input tokens")
    parser.add_argument("--output-price", help="compatible endpoint USD per million output tokens")


def make_provider(args):
    return Provider(args.provider, args.model, args.base_url, args.key_env,
                    args.input_price, args.output_price)


def verify(repo, command, timeout, folder):
    args = shlex.split(command)
    if not args:
        raise HarnessError("Empty verification command")
    display("Running operator-supplied verification: " + shlex.join(args))
    # Intentionally inherit the operator's environment: real project tests need it.
    # The model never chooses this command. This executes project code, not a sandbox.
    with tempfile.TemporaryFile() as output:
        child = subprocess.Popen(args, cwd=repo.root, stdout=output, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        try:
            code = child.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            code = 124
        size = output.tell()
        output.seek(max(0, size - 16000))
        tail = output.read(16000).decode("utf-8", errors="replace")
    private_write(folder / "verification.txt", tail)
    display(tail)
    return {"command": args, "exit_code": code, "output_tail": "verification.txt"}


def apply_and_verify(repo, metadata, folder, check=None, timeout=120):
    metadata["status"] = "applying"
    save_session(folder, repo, metadata)
    try:
        names = repo.apply()
        metadata.update(status="applied", applied_files=names)
        save_session(folder, repo, metadata)
        display(f"Applied {len(names)} files. Saved originals remain in {folder / 'session.json'}")
        if check:
            metadata["verification"] = verify(repo, check, timeout, folder)
            if metadata["verification"]["exit_code"]:
                metadata["status"] = "applied_check_failed"
                display("Verification failed. Edits remain applied; inspect the output before continuing.")
                return 1
            display("Verification passed (exit 0).")
        else:
            display("Verification: not run.")
        return 0
    except (HarnessError, OSError) as exc:
        metadata.update(status="apply_or_check_failed", error=str(exc))
        raise
    finally:
        save_session(folder, repo, metadata)


def build_parser():
    parser = argparse.ArgumentParser(prog="sparecode", description="Small coding tasks, small model bills.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="propose a change in an existing Git repository")
    run.add_argument("task")
    run.add_argument("--repo", default=".")
    run.add_argument("--file", action="append", default=[], help="read a relevant file before the first request")
    provider_args(run)
    run.add_argument("--budget", default="0.25", help="per-run USD request allowance (default: 0.25)")
    run.add_argument("--max-turns", type=positive, default=12)
    run.add_argument("--max-tokens", type=positive, default=120000, help="cumulative conservative token allowance")
    run.add_argument("--max-output", type=positive, default=1800)
    run.add_argument("--context-bytes", type=positive, default=24000, help="serialized prompt cap in UTF-8 bytes")
    run.add_argument("--state-dir", default=state_home())
    run.add_argument("--dry-run", action="store_true", help="inspect context without any model request or key")
    run.add_argument("--apply", action="store_true", help="apply after the model finishes; otherwise only save proposal")
    run.add_argument("--check", help="operator-supplied verification command after --apply; no shell expansion")
    run.add_argument("--check-timeout", type=positive, default=120)
    models = commands.add_parser("models", help="fetch current OpenRouter model prices; no key needed")
    models.add_argument("--filter", default="coder", help="case-insensitive model ID filter")
    for command in ("diff", "apply", "inspect"):
        sub = commands.add_parser(command, help={"diff": "show a saved proposal", "apply": "apply a saved proposal",
                                                  "inspect": "show session status and cost"}[command])
        sub.add_argument("session", help="session directory printed by run")
        if command == "apply":
            sub.add_argument("--check")
            sub.add_argument("--check-timeout", type=positive, default=120)
    doctor = commands.add_parser("doctor", help="check credentials/provider setup without generating tokens")
    provider_args(doctor)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "models":
            display("Model                                           Input $/M   Output $/M")
            for model in sorted(catalog(), key=lambda x: x.get("id", "")):
                if args.filter.lower() in model.get("id", "").lower():
                    try:
                        price = Price.from_model(model)
                    except HarnessError:
                        continue
                    display(f"{model['id']:48} {price.input * 1_000_000:>9.4f} {price.output * 1_000_000:>11.4f}")
            display("Live catalog prices; routing/privacy constraints can reduce availability.")
            return 0
        if args.command == "doctor":
            provider = make_provider(args)
            display(f"Provider: {provider.kind}\nModel: {provider.model}\nEndpoint: {provider.base_url}")
            if provider.kind == "local":
                from .provider import request_json
                info = request_json(provider.base_url + "/models")
                available = [m.get("id") for m in info.get("data", [])]
                if provider.model not in available:
                    raise HarnessError("Local server is reachable but the chosen model is not installed/loaded")
                display("Local model is available; generation was not tested.")
            else:
                display(f"{provider.key_env} is present. Authentication/generation has not been tested.")
            return 0
        if args.command in ("diff", "apply", "inspect"):
            folder = Path(args.session).expanduser().resolve()
            repo, metadata = load_session(folder)
            if args.command == "diff":
                display(repo.diff() or "No proposed changes.")
                return 0
            if args.command == "inspect":
                display(json.dumps({k: v for k, v in metadata.items() if k not in ("originals", "edits")}, indent=2))
                return 0
            if metadata.get("status") != "proposal_ready":
                raise HarnessError("Only finished, unapplied proposals can be applied. Review partial changes in changes.diff")
            return apply_and_verify(repo, metadata, folder, args.check, args.check_timeout)
        if args.check and not args.apply:
            raise HarnessError("--check requires --apply; it runs against the actual changed repository")
        money(args.budget)
        repo = Repository(args.repo)
        if args.dry_run:
            display(f"Repository: {repo.root}\nCandidate context:\n{repo.list_files(args.task)}")
            for name in args.file:
                display(f"\n{name}:\n{repo.read(name)}")
            display("No model request or repository edit performed.")
            return 0
        provider = make_provider(args)
        display(f"{provider.model} · per-run allowance ${args.budget} · {args.max_turns} turns maximum")
        folder, metadata = run_agent(repo, provider, args.task, args.state_dir, args.file,
                                     args.budget, args.max_turns, args.max_tokens,
                                     args.max_output, args.context_bytes, display)
        display("\nModel summary (verify independently):\n" + metadata["summary"])
        display("\n" + (repo.diff() or "No proposed changes."))
        display(f"Accounted cost: ${metadata['usage']['accounted_usd']} · {len(metadata['usage']['requests'])} requests")
        if args.apply:
            return apply_and_verify(repo, metadata, folder, args.check, args.check_timeout)
        display(f"Proposal saved; source repository unchanged.\nApply: sparecode apply {shlex.quote(str(folder))}")
        return 0
    except (HarnessError, OSError, ValueError, subprocess.SubprocessError) as exc:
        display("sparecode: " + str(exc))
        return 2
