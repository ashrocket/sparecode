"""Skip enforcement checks only for documentation-only PRs; fail open to full CI."""

import json
import os
import re
import subprocess
from pathlib import Path


def needs_checks(paths):
    return not paths or any(not (path.startswith("docs/") and path.endswith(".md")) for path in paths)


def full_checks(event_name, event, run=subprocess.check_output):
    if event_name != "pull_request":
        return True
    try:
        base = event["pull_request"]["base"]["sha"]
        head = event["pull_request"]["head"]["sha"]
        if not all(re.fullmatch(r"[a-f0-9]{40}", sha) for sha in (base, head)):
            return True
        output = run(
            ["git", "diff", "--no-renames", "--name-only", "-z", f"{base}...{head}"]
        )
        paths = output.decode("utf-8").split("\0")
        if paths.pop() != "":
            return True
        return needs_checks(paths)
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return True


if __name__ == "__main__":
    full = True
    try:
        full = full_checks(
            os.environ.get("GITHUB_EVENT_NAME"),
            json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()),
        )
    except (KeyError, ValueError, OSError):
        pass
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"full={str(full).lower()}\n")
    print(
        "Full CI required."
        if full
        else "Documentation-only PR; enforcement checks skipped."
    )
