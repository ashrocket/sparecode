# SpareCode design system

SpareCode is spare change kept in coin-roll wrappers. It keeps a developer coding on low-cost models when subscription quota runs out, so the identity uses the coin roll: a warm paper ground, coin-roll bands at a fixed pitch, and plain ink type with no decoration. SpareCode is a terminal tool, so its landing page is one plain page that shows the name, one sentence and the install command.

## Voice

1. Say what is hosted and what is not. Example: "Hosted models first. Zero Python runtime dependencies. No subscription required by the harness." (README.md:15)
2. Say what stays unchanged. Example: "The source repository is unchanged." (README.md:61)
3. Show the command before the explanation. Example: "Preview eligible context with no model call or key required:" (README.md:57)
4. Name the safety rule in one line. Example: "Existing dirty work is preserved; apply refuses files whose contents changed after being read." (README.md:79-80)

## Colour

Single light theme. Every value is a token in `tokens.json` and in `tokens.css`.

| Token | Value | Role | Contrast on paper |
|---|---|---|---|
| `paper` | #fbf9f4 | Page ground | n/a |
| `ink` | #1e1e1c | Body text, wordmark, primary button fill | 15.87:1 (passes 4.5:1) |
| `penny-copper` | #9a4e28 | Text-safe accent: links, command labels | 5.71:1 (passes 4.5:1) |
| `nickel-blue` | #2f5d8a | Cover block; text accent | 6.54:1 (passes 4.5:1) |
| `dime-green` | #2e6b3f | Cover block; success accent | 6.06:1 (passes 4.5:1) |
| `quarter-orange` | #d9822b | Non-text only: cover stripes and rules | 2.78:1 (fails 3:1 and 4.5:1) |
| `muted` | #5e5b55 | Taglines, captions, notes | 6.43:1 (passes 4.5:1) |

`quarter-orange` is not text on paper. Use it only for graphics. The brief sets this value.

## Type

Families come from Google Fonts. No font file is shipped, so `type.fonts` is empty.

- Display and body: Chivo (https://fonts.google.com/specimen/Chivo). Weight 800 for display and headings, weight 400 for body. Token: `--font-sans`.
- Commands: Chivo Mono (https://fonts.google.com/specimen/Chivo+Mono). Weight 400. Token: `--font-mono`.

| Style | Size / line | Weight | Used for |
|---|---|---|---|
| `display` | 72px / 72px | 800 | Wordmark and page name |
| `heading` | 28px / 34px | 800 | Section heading |
| `lead` | 20px / 30px | 400 | One-sentence summary |
| `body` | 16px / 26px | 400 | Running text |
| `small` | 14px / 22px | 400 | Captions, taglines, notes |
| `command` | 15px / 24px | 400 (mono) | Shell commands |

## Layout and spacing

Spacing steps: `space-1` 8px, `space-2` 16px, `space-3` 24px, `space-4` 48px. Side gutter 16px on phones. Text column maximum 680px. Radii: `radius-sm` 2px (command blocks), `radius-md` 6px (buttons), `radius-lg` 16px (large cards). No shadows.

## Logo and wordmark

No logo file exists in the repository. Nothing was copied into `assets/Logos/`; see `assets/Logos/README.md`. The wordmark is plain type: "SpareCode" in Chivo 800 (`display` style), ink on paper, with no tracking change and no case change. Clear space: one x-height of the wordmark on every side. Minimum size: 20px cap height. Do not redraw the letters, add a coin icon or set the name in any other face.

## Landing page anatomy

1. Wordmark: "SpareCode" in `display`, ink on paper.
2. Summary: one sentence from the README in `lead`, ink.
3. Action: the install command in a `command` block (`radius-sm`, ink text on paper with a 1px `penny-copper` edge), above a primary button labelled "Install" (ink fill, paper text, `radius-md`).
4. Cover (cover only): four solid blocks on the right half, with quarter-orange bands at a 24px pitch across the nickel-blue block. The name and tagline sit left.

## Status

new
