# Cloud task: finish this repo's design system (fix and verify)

You work on branch `claude/design-system-2026-10-19` of this repo. The branch
holds two things: the repo's design system (folder named in
`.ds-work/project.json` → `target`) and this work folder `.ds-work/`.

Owner goal (2026-10-18): every project has a design system in place, at least
for its landing page and branding; improvements and a v2 are allowed. An overseer
already made the design decisions. You finish the fixes and verify them.

## Read first

1. `.ds-work/project.json` — `n` (project), `target` (system folder), `mode`
   (formalize | v2 | new | mirror), `brief` (owner-approved decisions), `ruling`
   (what the overseer wants fixed now; empty = verify only), `defects` (the last
   open defects; the ruling says which to fix and which a ruling waives).
2. `.ds-work/SPEC.md` — the full spec. Its LAST section, "Overseer rulings after
   the first build (2026-10-19)", overrides earlier text and earlier findings.

## Rules

- Write only inside the target folder and `.ds-work/RESULT.json`. Never edit,
  delete or reformat any other file in the repo. Never touch other branches.
- Never copy secrets, credentials, addresses, account numbers, case facts, real
  email addresses or real people's names into the system. Paths are never absolute.
- Mode `mirror`: the published Design System artifact cannot be read from the
  cloud. Do NOT re-mirror. Fix only what does not need the artifact, and record
  "mirror re-sync needs a local session" in RESULT.json.
- Work like a HaiKrew crew to save tokens: you (the lead) decide and review;
  hand mechanical edits and the adversarial check to Haiku subagents
  (Agent tool with `model: "haiku"`), each with a tight spec and a report of
  120 words or fewer. Escalate a fix to `model: "sonnet"` after two failures.

## Steps

1. `git fetch origin claude/design-system-2026-10-19 && git checkout claude/design-system-2026-10-19`
   (skip if already on it).
2. Apply the ruling (if any). Then run, from the repo root:
   - `python3 -I .ds-work/tools/gen_tokens_css.py <target> --title "<system name>"` if tokens.json changed
   - `python3 -I .ds-work/tools/validate.py <target> --root .` (mode `new`: omit `--root .`)
   - `python3 -I .ds-work/tools/contrast.py <target>`
   - `sh .ds-work/tools/shot.sh <target>/components/Cover/preview.html /tmp/cover.png 960 320`,
     `... Hero/preview.html /tmp/hero.png 1280 800` and `... /tmp/hero-phone.png 390 844`.
     If no browser exists, try `pip install playwright && python3 -m playwright install --with-deps chromium`;
     if that fails, review the HTML by reading it and say "visual review: static" in RESULT.json.
     Open each PNG with Read.
3. Adversarial check (Haiku subagent, read-only): validator ERRORs; LOW contrast
   pairs not covered by ruling 5; invented values (grep the repo for each colour not
   marked "v2:"; Swift float forms count, ruling 7); logos byte-identical to repo
   files; README sections and an honest `## Status` (ruling 4); Cover folder holds
   only preview.html; no absolute paths; privacy; generic tells only in the
   system's own choices (ruling 2).
4. Visual review (you): Cover per the Cover contract (fixed 960px, 3–5 solid
   identity blocks, one pattern, name bottom-left, one tagline line); Hero with
   source-true copy, readable at 1280 and 390, no horizontal scroll, no clipping.
5. Fix what steps 3–4 find (max 2 rounds), re-running step 2's checks.
6. Write `.ds-work/RESULT.json`:
   `{"project": n, "verdict": "PASS"|"OPEN", "validator": "<PASS/FAIL line>", "contrast": "ok|<pairs>", "visual_review": "rendered|static", "fixed": [...], "waived": [...], "open": [...]}`.
7. Commit only the target folder and `.ds-work/RESULT.json`:
   `git add <target> .ds-work/RESULT.json && git commit -m "design-system: fix and verify (<n>)"`
   and `git push origin claude/design-system-2026-10-19`. Do not open a pull request.
   Do not merge. Do not delete `.ds-work/` (the owner removes it before merging).
