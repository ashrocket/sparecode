"""Git-aware context access and conflict-checked edit proposals."""
import difflib
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile

from .provider import HarnessError


MAX_FILE = 200_000
BLOCKED_DIRS = {".git", ".hg", ".svn", ".ssh", ".aws", ".kube", ".gnupg",
                ".venv", "venv", "node_modules", "__pycache__", ".sparecode"}


def private_write(path, text):
    """Atomic replacement for a private session file."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".sparecode-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def bounded(text, limit=6000):
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text
    marker = "\n[truncated; request a smaller range]"
    return data[:max(0, limit - len(marker))].decode("utf-8", errors="ignore") + marker


class Repository:
    def __init__(self, root):
        requested = Path(root).expanduser().resolve()
        result = subprocess.run(["git", "-C", str(requested), "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise HarnessError("Select an existing Git repository with --repo")
        self.root = Path(result.stdout.strip()).resolve()
        self.patterns = []
        ignore = self.root / ".sparecodeignore"
        if ignore.is_file() and not ignore.is_symlink():
            if ignore.stat().st_size > 16000:
                raise HarnessError(".sparecodeignore is too large")
            self.patterns = [x.strip() for x in ignore.read_text().splitlines()
                             if x.strip() and not x.lstrip().startswith("#")]
        result = subprocess.run(["git", "-C", str(self.root), "ls-files", "-z", "--cached",
                                 "--others", "--exclude-standard"], capture_output=True, timeout=15)
        if result.returncode:
            raise HarnessError("Could not enumerate repository files")
        names = set(result.stdout.decode("utf-8", errors="strict").split("\0")) - {""}
        # --no-index also excludes accidentally tracked ignored files from model context.
        ignored = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--no-index",
                                  "-z", "--stdin"], input="\0".join(names).encode() + b"\0",
                                 capture_output=True, timeout=15)
        if ignored.returncode not in (0, 1):
            raise HarnessError("Could not evaluate repository ignore rules")
        names -= set(ignored.stdout.decode().split("\0"))
        self.files = set()
        for name in names:
            try:
                path = self.path(name)
                if path.is_file() and path.stat().st_size <= MAX_FILE:
                    self.files.add(name)
            except (HarnessError, OSError):
                continue
        self.originals = {}
        self.edits = {}
        self.instructions = {}
        self.load_instructions("placeholder")

    def path(self, name):
        if not isinstance(name, str) or not name or "\\" in name:
            raise HarnessError("Path must be a relative POSIX file path")
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or str(pure) != name:
            raise HarnessError("Path escapes the repository or is not canonical")
        if any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise HarnessError("Control characters are not allowed in paths")
        parts = [part.lower() for part in pure.parts]
        base = parts[-1]
        if (any(p in BLOCKED_DIRS for p in parts)
                or base.startswith((".env", "id_rsa", "id_ed25519", "id_ecdsa"))
                or base in {".npmrc", ".pypirc", ".netrc", "credentials", "credentials.json",
                            "secrets.json", "secrets.yaml", "secrets.yml", "token.json"}
                or base.endswith((".pem", ".key", ".p12", ".pfx", ".keystore"))
                or any(fnmatch.fnmatchcase(name, p) or fnmatch.fnmatchcase(base, p)
                       or name.startswith(p.rstrip("/") + "/") for p in self.patterns)):
            raise HarnessError("Protected or excluded path")
        cursor = self.root
        for part in pure.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise HarnessError("Symlinks are excluded")
        return cursor

    def disk_text(self, name):
        path = self.path(name)
        if not path.is_file() or path.stat().st_size > MAX_FILE:
            raise HarnessError("File is absent, not regular, or exceeds 200 KB")
        try:
            data = path.read_bytes()
            if b"\0" in data:
                raise HarnessError("Binary files are excluded")
            return data.decode("utf-8")
        except UnicodeError:
            raise HarnessError("Only UTF-8 text files are supported") from None

    def load_instructions(self, name):
        parent = PurePosixPath(name).parent
        dirs = [PurePosixPath(".")] + list(reversed(parent.parents)) + [parent]
        for directory in dict.fromkeys(dirs):
            candidate = str(directory / "AGENTS.md")
            if candidate in self.files and candidate not in self.instructions:
                text = self.disk_text(candidate)
                if len(text.encode()) > 10000:
                    raise HarnessError(f"{candidate} exceeds the instruction allowance; narrow this task")
                self.instructions[candidate] = text

    def text(self, name):
        self.path(name)
        if name not in self.files and name not in self.edits:
            raise HarnessError("File is not eligible repository context")
        self.load_instructions(name)
        if name in self.edits:
            return self.edits[name]
        text = self.disk_text(name)
        # Capture exactly the working-tree contents read, including user's dirty changes.
        if name not in self.originals:
            self.originals[name] = text
        return text

    def read(self, name, start=1, end=160):
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            raise HarnessError("Line range must have 1 <= start <= end")
        lines = self.text(name).splitlines()
        end = min(end, start + 159, len(lines))
        return bounded("\n".join(f"{i + 1}: {lines[i]}" for i in range(start - 1, end)))

    def list_files(self, task="", query=""):
        words = set(re.findall(r"[a-zA-Z_][a-zA-Z_0-9]{2,}", task.lower()))
        files = [f for f in self.files | self.edits.keys() if query.lower() in f.lower()]
        files.sort(key=lambda f: (-sum(w in f.lower() for w in words), len(f), f))
        return bounded("\n".join(files[:100]) + f"\n[{len(files)} matching files]", 4000)

    def search(self, query):
        if not isinstance(query, str) or not query or len(query) > 200:
            raise HarnessError("Search needs 1-200 characters of literal text")
        hits = []
        scanned = 0
        for name in sorted(self.files | self.edits.keys()):
            if scanned > 20_000_000:
                hits.append("[search stopped at 20 MB; use files/read to narrow]")
                break
            try:
                content = self.edits[name] if name in self.edits else self.disk_text(name)
            except HarnessError:
                continue
            scanned += len(content.encode())
            for line, text in enumerate(content.splitlines(), 1):
                if query.lower() in text.lower():
                    hits.append(f"{name}:{line}: {text[:300]}")
                    if len(hits) >= 30:
                        return bounded("\n".join(hits) + "\n[30-hit limit]")
        return bounded("\n".join(hits) or "No matches")

    def replace(self, name, old, new):
        self.path(name)
        if name not in self.originals and name not in self.edits:
            raise HarnessError("Read the file before editing it")
        if not isinstance(old, str) or not old or not isinstance(new, str):
            raise HarnessError("Replacement needs nonempty old text and string new text")
        content = self.text(name)
        if content.count(old) != 1:
            raise HarnessError("Old text must match exactly once; read a narrower range")
        proposed = content.replace(old, new, 1)
        if len(proposed.encode()) > MAX_FILE or "\0" in proposed:
            raise HarnessError("Edited file exceeds text limits")
        self.edits[name] = proposed
        return f"Proposed replacement in {name}; source repository unchanged"

    def create(self, name, content):
        path = self.path(name)
        if path.exists() or name in self.edits:
            raise HarnessError("Create refuses to overwrite an existing path")
        ignored = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--no-index", "--", name],
                                 capture_output=True, timeout=10)
        if ignored.returncode != 1:
            raise HarnessError("Create refuses ignored paths")
        if not isinstance(content, str) or len(content.encode()) > MAX_FILE or "\0" in content:
            raise HarnessError("New file exceeds text limits")
        before = set(self.instructions)
        self.load_instructions(name)
        if set(self.instructions) != before:
            raise HarnessError("Additional AGENTS.md guidance loaded; review it before resubmitting create")
        self.originals[name] = None
        self.edits[name] = content
        return f"Proposed new file {name}; source repository unchanged"

    def diff(self):
        parts = []
        for name, new in sorted(self.edits.items()):
            old = self.originals[name]
            if old == new:
                continue
            lines = difflib.unified_diff((old or "").splitlines(keepends=True),
                                        new.splitlines(keepends=True),
                                        fromfile="/dev/null" if old is None else "a/" + name,
                                        tofile="b/" + name)
            for line in lines:
                parts.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
        return "".join(parts)

    def apply(self):
        # Preflight the entire proposal before changing any file.
        pending = {n: t for n, t in self.edits.items() if self.originals[n] != t}
        for name in pending:
            path = self.path(name)
            old = self.originals[name]
            if old is None:
                if path.exists():
                    raise HarnessError(f"Conflict: new path already exists: {name}")
                ignored = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--no-index", "--", name],
                                         capture_output=True, timeout=10)
                if ignored.returncode != 1:
                    raise HarnessError(f"New path is now ignored: {name}")
            elif name not in self.files or self.disk_text(name) != old:
                raise HarnessError(f"Conflict: file changed since it was read: {name}")
        applied = []
        try:
            for name, new in pending.items():
                path = self.path(name)
                path.parent.mkdir(parents=True, exist_ok=True)
                mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
                fd, temporary = tempfile.mkstemp(prefix=".sparecode-", dir=path.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(new.encode())
                        os.fchmod(stream.fileno(), mode)
                    # Recheck just before replacement; do not erase an editor's new content.
                    self.path(name)
                    if self.originals[name] is None:
                        os.link(temporary, path)  # exclusive creation
                    else:
                        if self.disk_text(name) != self.originals[name]:
                            raise HarnessError(f"Concurrent edit detected: {name}")
                        os.replace(temporary, path)
                    applied.append(name)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
        except (OSError, HarnessError) as exc:
            raise HarnessError(f"Apply stopped after {len(applied)} files; review the diff and saved originals. "
                               f"Cause: {type(exc).__name__}") from None
        return applied


def save_session(folder, repo, metadata):
    document = dict(metadata, repo=str(repo.root), originals=repo.originals, edits=repo.edits)
    private_write(folder / "session.json", json.dumps(document, indent=2))
    private_write(folder / "changes.diff", repo.diff())


def load_session(folder):
    path = Path(folder).expanduser().resolve() / "session.json"
    if path.stat().st_size > 10_000_000:
        raise HarnessError("Session is too large")
    data = json.loads(path.read_text())
    repo = Repository(data["repo"])
    if not isinstance(data.get("edits"), dict) or not isinstance(data.get("originals"), dict):
        raise HarnessError("Invalid session")
    for name, content in data["edits"].items():
        repo.path(name)
        if name not in data["originals"] or not isinstance(content, str):
            raise HarnessError("Invalid session edit")
        if len(content.encode()) > MAX_FILE or "\0" in content:
            raise HarnessError("Invalid session text")
        old = data["originals"][name]
        if old is not None and not isinstance(old, str):
            raise HarnessError("Invalid saved original")
    repo.originals, repo.edits = data["originals"], data["edits"]
    return repo, data
