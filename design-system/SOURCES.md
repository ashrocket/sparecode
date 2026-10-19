# Sources

Built 2026-10-18 for the sparecode project. Status: new.

| Source | What came from it |
|---|---|
| Owner brief (2026-10-18, in the build task) | Concept, palette, type families, wordmark rule, cover pattern, hero content. These are owner decisions, not extracted values. |
| `design-systems/profiles/sparecode.json` (ashcode workspace profile, outside this project) | Confirmed no existing visual identity: no css, html, svg, font or logo files; `logo_files` empty; `classification` new_needed. |
| `README.md:1-4` (project root) | Product name "SpareCode", one-line description, MIT licence, subscription-quota purpose. Used in the README concept, the hero sub-line and the cover tagline. |
| `README.md:15` | Voice example: "Hosted models first. Zero Python runtime dependencies. No subscription required by the harness." |
| `README.md:32-33` | Real install commands: `python3 -m venv .venv` and `.venv/bin/python -m pip install .`. Used in the hero action. |
| `README.md:57` | Voice example: "Preview eligible context with no model call or key required:" |
| `README.md:61` | Voice example: "The source repository is unchanged." |
| `README.md:79-80` | Voice example: "Existing dirty work is preserved; apply refuses files whose contents changed after being read." |
| `LICENSE:1` | "MIT License" (licence name only). |
| `pyproject.toml:6-7` | Package name `sparecode`, version `0.1.0`. Not shown in the system. |
| `git ls-files` (project root) | Tracked files: 12 Python (`.py`), 8 Markdown (`.md`), 1 YAML (`.yml`), `pyproject.toml`, `LICENSE`, `.gitignore`, `examples/Modelfile.local`, `examples/Modelfile.local-2b`, and four launcher scripts in `bin/` (`sparecode`, `unburden`, `userhappy`, `yycc`). No logo, font or stylesheet is tracked. |

Files read by the build for this system: `design-systems/SPEC.md` (in full), the profile, and the evidence digest (0 text files scanned). Nothing from `.env`, credentials, `.venv`, `build/`, `examples/` or `project-kits/` was read or copied.
