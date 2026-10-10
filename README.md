# SpareCode

A small, MIT-licensed coding harness for when you want to keep working without
using more Codex or Claude subscription quota. Bring a low-cost model API key,
point it at a Git repository, and give it one bounded coding task.

**Hosted models first. Zero Python runtime dependencies. No subscription required
by the harness.** Python 3.11+ and Git are required. macOS and Linux are supported.

This is an early, intentionally narrow coding assistant. It can inspect source,
search, propose exact replacements and new files, and produce a reviewable diff.
You can apply a proposal and run your own verification command. It does not offer
Codex's full agent environment or promise equivalent coding quality.

## Start in two minutes

From this checkout:

```sh
# No installation needed:
./bin/sparecode --help

# Or install the CLI in an isolated environment:
python3 -m venv .venv
.venv/bin/python -m pip install .
# Then use .venv/bin/sparecode instead of ./bin/sparecode.
```

Create an API key in your [OpenRouter account](https://openrouter.ai/settings/keys)
and give it a small spending limit. Enter it without putting it in shell history:

```sh
# macOS zsh:
read -rs 'OPENROUTER_API_KEY?OpenRouter API key: '; echo
export OPENROUTER_API_KEY

# Bash alternative:
# read -rs -p 'OpenRouter API key: ' OPENROUTER_API_KEY; echo
# export OPENROUTER_API_KEY
```

The key stays in your shell environment. SpareCode does not read `.env` files or
save credentials. API billing is separate from Codex/Claude subscriptions.

```sh
./bin/sparecode doctor
./bin/sparecode models --filter coder

# Preview eligible context with no model call or key required:
./bin/sparecode run 'Fix the pagination off-by-one error' \
  --repo /path/to/project --file src/pagination.py --dry-run

# Generate a proposal. The source repository is unchanged.
./bin/sparecode run 'Fix the pagination off-by-one error and add a regression test' \
  --repo /path/to/project --file src/pagination.py --budget 0.10

# Use the actual session directory printed by run:
./bin/sparecode diff /path/to/session
./bin/sparecode apply /path/to/session --check 'python3 -m unittest discover -s tests'
```

You can also authorize application and verification in one invocation:

```sh
./bin/sparecode run 'Handle empty input in the CSV parser and add a regression test' \
  --repo /path/to/project --file src/parser.py --budget 0.15 \
  --apply --check 'python3 -m unittest discover -s tests'
```

Use an absolute path to `bin/sparecode` to launch it from any repository, or use
the installed command. No project configuration file is required. Existing dirty
work is preserved; apply refuses files whose contents changed after being read.

## Model choices and cost

The default is **`qwen/qwen3-coder-next` through OpenRouter**. These are examples
of open-weight models, not a claim that every model has the same license.
Check the selected model's license for your use. The harness itself uses MIT.

Live catalog observed on October 9, 2026 (America/New_York):

| Model ID | Input / million tokens | Output / million tokens | Suggested use |
| --- | ---: | ---: | --- |
| `qwen/qwen3-coder-next` | $0.12 | $0.80 | Default coding option |
| `qwen/qwen3-coder-30b-a3b-instruct` | $0.07 | $0.28 | Smaller, cheaper tasks |
| `deepseek/deepseek-v3.2` | $0.259 | $0.42 | Alternative to evaluate |

At the listed Qwen3-Coder-Next rates, **20,000 input + 5,000 output tokens cost
$0.0064 in token charges**. This is arithmetic from the catalog, not a measured
task result or a quality comparison. Request counts, repeated context, provider
availability, pricing tiers, and account fees affect the actual bill. Prices can
change; `models` and every hosted run fetch the
[current catalog](https://openrouter.ai/api/v1/models).

```sh
./bin/sparecode run 'Add null handling to this function' --repo /path/to/project \
  --model qwen/qwen3-coder-30b-a3b-instruct --budget 0.05
```

SpareCode does not automatically switch models or fall back to a paid premium
model. Free models can be selected explicitly if available, but their quotas and
availability vary. The default does not depend on a free-tier promotion.

## How token use stays bounded

- **Relevant context:** a filename shortlist, literal search, and small read ranges;
  the entire repository is not inserted into the prompt.
- **Bounded history:** older action/result pairs are dropped when the prompt reaches
  24,000 serialized UTF-8 bytes. The task, discovered `AGENTS.md` guidance, and edit
  state remain. There is no extra model call for summarization or embeddings.
- **Short changes:** unique text replacements instead of whole-file rewrites.
- **Finite loop:** 12 model requests, 1,800 output tokens per request, and a cumulative
  120,000-token conservative allowance by default. Three consecutive invalid actions
  stop the run. All model requests, including mistakes, count.
- **Spend gate:** before each request, reserve its UTF-8 byte count plus framing
  allowance as estimated input tokens, plus the full output limit. Refuse the request
  if it would exceed the remaining default $0.25 per-run allowance.
- **Provider limits:** OpenRouter requests set maximum token prices, zero per-request
  fees, price sorting, no fallback, and `data_collection: deny`. Unavailable routes
  fail visibly. There are no silent HTTP retries.

The token bound is deliberately conservative; it is not an exact tokenizer. Usage
returned by the provider replaces reservations. Missing usage or uncertain network
results retain the reservation. `inspect` shows provider token counts, reported cost
when supplied, and the conservative accounted amount separately.

**The local allowance is a request gate, not a guaranteed invoice cap.** A provider
can report unexpected usage or charges after responding. Use an account/API-key
spending limit as the billing backstop. Allowances reset for each run; simultaneous
runs do not share a daily budget.

## Other hosted endpoints and local models

For a compatible hosted Chat Completions endpoint, specify the base URL, exact
model ID, credential environment variable, and current prices in USD per million.
It must support `response_format: {"type":"json_object"}` and `max_tokens`.

```sh
export SPARECODE_API_KEY='your-key' # Prefer hidden input as above.
./bin/sparecode run 'Fix the failing parser case' --repo /path/to/project \
  --provider compatible --base-url https://your-provider.example/v1 \
  --model your-model-id --input-price 0.20 --output-price 0.60 --budget 0.10
```

The example hostname/model/prices are placeholders, not a provider recommendation.
Compatible endpoints use your supplied rates for accounting and do not implement
OpenRouter's provider-level price filter.

For an already-running local server, no key is required:

```sh
# Separately install Ollama and download a model that fits your machine:
ollama pull qwen2.5-coder:3b
./bin/sparecode doctor --provider local --model qwen2.5-coder:3b
./bin/sparecode run 'Add a docstring to the parser' --repo /path/to/project \
  --provider local --model qwen2.5-coder:3b --budget 0
```

Local mode only permits loopback URLs and rejects known cloud-style model names.
You are responsible for running a genuinely local backend: a loopback proxy can
still forward requests. Model download, RAM, speed, and coding quality are separate
concerns. A small local model is best evaluated on narrow tasks before trusting it.

## Repository and execution boundaries

- Git-tracked and nonignored untracked files are eligible, including your working
  changes. Ignored paths (even tracked ones), symlinks, binary text, files over
  200 KB, common credential files, dependency directories, and VCS internals are excluded.
- Add a `.sparecodeignore` with one glob or directory prefix per line to exclude
  additional material. Blank lines and `#` comments are supported; negation is not.
  Example entries: `private/`, `*.csv`, `customer-export.json`.
- Filename rules are **not a complete secret scanner**. With a hosted model, the
  selected source and instruction text leave your machine. Scope tasks accordingly.
- Root and relevant nested `AGENTS.md` instructions are loaded and retained. Guidance
  outside the selected Git root is not loaded. Excessively large guidance stops the
  run rather than silently dropping it.
- The model has no shell, install, network, commit, push, delete, or rename tool.
  `--check` executes exactly your supplied command using argument parsing, not shell
  interpolation. It runs project code with your account permissions and environment;
  **it is not a sandbox**. It is only available after explicit application.
- Apply checks all touched originals before writing and preserves file modes. Each
  replacement is atomic; the whole multi-file apply is not a filesystem transaction.
  An I/O failure or concurrent edit can leave partial application, which is reported.
- Failed verification leaves edits applied and reports a nonzero exit status.
  There is no automatic rollback or model-driven repair/test loop in this version.

Sessions are private local files under `~/.local/state/sparecode/` (or
`$XDG_STATE_HOME/sparecode`). Override with `--state-dir` outside the target repo.
They contain original source, proposals, task text, metadata, and a usage ledger;
keep them private. Review with `diff` and `inspect`. Stopped/interrupted sessions
retain their partial diff but cannot be applied automatically or resumed. Start a
new narrowly scoped run after reviewing the reason for stopping.

## Development and verification

```sh
python3 -m unittest discover -s tests -v
python3 examples/offline_demo.py
git diff --check
```

The offline demo uses the actual HTTP adapter and CLI to read a tiny repository,
propose an addition fix, apply it, and run a passing check. Its model responses are
scripted. It proves harness plumbing, not model intelligence. Tests cover cost gates,
unknown usage, retry avoidance, context trimming, protected paths, conflicting edits,
proposal persistence, and application/verification.

GitHub Actions is configured for Python 3.11/3.13 on Linux/macOS. A checked-in workflow
does not mean it has run. Real hosted-model generation requires a configured key.

Sources: [OpenRouter API](https://openrouter.ai/docs/api/reference/overview),
[provider price and privacy filters](https://openrouter.ai/docs/guides/routing/provider-selection),
[Ollama compatibility](https://docs.ollama.com/api/openai-compatibility), and
[Qwen2.5-Coder model sizes](https://ollama.com/library/qwen2.5-coder).
