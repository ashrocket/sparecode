# SpareCode

SpareCode is a small MIT-licensed fallback coding harness. Keep runtime dependencies
at zero (Python 3.11+ standard library). Default to inexpensive hosted open-weight
models; support local OpenAI-compatible endpoints without requiring a subscription.

Before editing, inspect the relevant modules and tests. Preserve these invariants:
- No model-selected shell commands, installation, commits, pushes, or publication.
- Edits are proposals until the operator requests apply. Recheck original contents.
- Never follow repository symlinks or read ignored/credential files as context.
- Reserve each request's conservative cost before sending. No automatic HTTP retry.
- Report measured usage separately from estimates and never promise a billing cap.
- Keep the task, discovered AGENTS.md instructions, and edit state across compaction.
- No repository-controlled provider settings or automatic credential-file loading.

Run `python3 -m unittest discover -s tests -v`, `python3 -m sparecode --help`, and
`git diff --check`. Tests must not require credentials or paid model requests.
Keep README examples runnable and document limits honestly. A mocked provider test
does not prove live model quality. CLI work does not require browser QA.
