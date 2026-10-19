# Design-system spec for every project (2026-10-18)

Goal (owner, 2026-10-18): every project has a design system in place, at least for
its landing page and branding. Retailaer repos: EXTRACT only, never propose.
Other projects: improve existing systems; a v2 is allowed.

Owner constraints that apply to every worker:

- Additive only. Do not edit existing landing pages, CSS, app code or assets.
  Do not commit, push, stage or delete anything. Do not run builds or installs.
- Never invent a logo. Copy a real logo file, or state "no logo: wordmark is
  plain type" and specify that type.
- Exact values only. Every extracted value cites `path:line` (relative to the
  project root). The evidence JSON in `~/ashcode/design-systems/evidence/` has
  locations already; verify a value in the file before you rely on it.
- Write in plain, short sentences (ASD-STE100 style): active voice, one idea a
  sentence, no marketing words.
- No secrets: never copy `.env`, credentials, tokens, personal or legal data.

## Where a system lives

| Project kind | Folder |
|---|---|
| ashcode project (git repo or project folder) | `<repo>/design-system/` (if that folder already holds code or other files, see the project's row in MATRIX.md) |
| Retailaer repo | `~/retailaer/design-system-extractions/<repo>/` (never inside the client repo) |

## Files in a system (Claude "Design System" artifact layout)

```
README.md                      brand book (required)
tokens.json                    tokens, exact grammar below (required)
components/Cover/preview.html  cover card (required for ashcode systems)
components/Hero/preview.html   the landing-page hero pattern (required if the project has or needs a landing page)
components/Hero/README.md      guideline: first sentence = summary
components/<Comp>/...          further real components (Button, Nav, Footer, Card...) only if the source has them
assets/Logos/<file>            copied logo files (svg/png), plus assets/Logos/README.md
SOURCES.md                     every source file read, and what came from it
```

### README.md sections (brand book)

1. `# <Name> design system` and one paragraph: what the product is, for whom,
   and the job of its landing page.
2. `## Voice` – 3 to 5 rules, each with a real example line from the product.
3. `## Colour` – table: token, value, role. Name contrast ratios for text pairs.
4. `## Type` – families (with real source: Google Fonts URL, font file, or
   system stack), the scale, and where each style is used.
5. `## Layout and spacing` – grid, max width, spacing steps, radius.
6. `## Logo and wordmark` – the real files, clear space, minimum size, what not to do.
7. `## Landing page anatomy` – the sections of the landing page in order, and
   which tokens/components each uses.
8. `## Status` – one of: `extracted` (values come from code), `formalized`
   (code values organized into a system, no new choices), `v2` (new choices:
   list each change and why), `new` (no prior identity existed).

### tokens.json grammar (the page cannot read any other shape)

```json
{"name": "Acme", "version": 1,
 "meta": {"source": "code", "status": "formalized"},
 "color": {"themes": [{"id": "light", "name": "Light"}, {"id": "dark", "name": "Dark"}],
   "tokens": [{"name": "surface", "value": {"light": "#fbf7f1", "dark": "#1d1a17"}, "usage": "Page background. styles.css:12"}]},
 "type": {"fonts": [],
   "families": {"sans": "\"Inter\", system-ui, sans-serif"},
   "groups": [{"name": "Text", "family": "sans",
     "styles": [{"name": "body", "fontSize": "16px", "lineHeight": "24px", "fontWeight": 400}]}]},
 "spacing": {"tokens": [{"name": "space-4", "value": "16px", "usage": "Card padding."}]},
 "radius": {"tokens": [{"name": "radius-md", "value": "8px", "usage": "Buttons, cards."}]},
 "shadow": {"tokens": [{"name": "shadow-card", "value": "0 1px 2px rgba(0,0,0,.08)", "usage": "Cards."}]}}
```

Rules: every family except `type` is `{"tokens": [{"name","value","usage"}]}` (a list,
never a name-to-value map). Token names match `[A-Za-z0-9][A-Za-z0-9_.-]{0,63}`, no
spaces or `/`, each name used once across all families. Colour values: hex, `rgb()`,
`rgba()`, `hsl()`, `oklch()` with no nested function, or `"{other-token}"`. Never
`var()`, `color-mix()`, named colours, `transparent` or `currentColor`. One theme only
is fine: then `themes` has one entry and values may be plain strings. Lengths in
`px`, `rem`, `em` or `%`. Put the `path:line` citation in `usage`.
A hosted Google font has no file: name it in `type.families` only, with `fonts: []`.

### preview.html contract

Line 1: `<!-- @dsCard group="Brand" height=360 -->` (Cover) or `group="Landing"` (Hero).
Then a small self-contained HTML document: inline `<style>`, real copy from the
product, colours/fonts from tokens.json written as CSS custom properties at the top.
Google Fonts `<link>` is allowed; no other network, no scripts. Body background set
explicitly. Text contrast 4.5:1 (3:1 at 24px and up). Width-fluid, no horizontal scroll.

## Retailaer extraction rules (extra)

- Status is always `extracted`. Never write "should", "recommend", "propose".
- Canonical Retailaer sources: `~/retailaer/code/design-system` (repo),
  `~/retailaer/brandkit`, `~/retailaer/code/retailaer-runway/design/retailaer.tokens.json`.
- Each per-repo extraction adds `## Drift from canonical`: a table of values this
  repo uses that the canonical system does not define, or defines differently,
  each with `path:line`. A fact, not a recommendation.
- A clone or branch checkout of another repo gets a short README that names its
  parent and lists only the differences from the parent's extraction.
- A client sub-brand (Air Europa, Wizz Air, Airline Atlas) is extracted only from
  what the code holds. Never fill in a real company's brand from memory.
- No Cover/Hero preview required; `tokens.json` + `README.md` + `SOURCES.md` are.

## ashcode build rules (extra, for systems that are not Retailaer)

- `tokens.css`: generate it, never hand-write it:
  `python3 -I ~/ashcode/design-systems/extract/gen_tokens_css.py <system-dir> --title "<Name>"`.
  Re-run after every tokens.json change. Previews link it with
  `<link rel="stylesheet" href="../../tokens.css">` and use `var(--<token-name>)`;
  fonts as `var(--font-<family-key>)`. Do not redeclare token values in a preview.
- A preview may also carry `components/bundle.css` rules only if the system writes one.
- **Cover** (`components/Cover/preview.html`, folder holds ONLY preview.html):
  line 1 `<!-- @dsCard height=288 -->` (240–360). Fixed 960px-wide layout, no media
  queries, no vw units. One inline SVG + the name + one tagline line, nothing else:
  3–5 big solid colour blocks in the identity colours (a quarter to a half of the
  cover, never a row of equal squares), ONE pattern chosen from what the README says
  about the brand (discs/pills for soft brands, dot grid for technical, 3–6 hairlines
  for editorial, stripes for loud, a motif silhouette from radii), all fills bound to
  token classes. The name bottom-left in the display face at 64–120px (longest line
  ≤ 440px), tagline 13–14px muted under it; blocks and pattern only right of x=480.
  A 4-line derivation comment at the top of the SVG (blocks × tokens, arrangement,
  pattern + why, steps/radii used). No gradients, shadows, images, emoji or words on blocks.
- **Hero** (`components/Hero/preview.html` + `README.md`): the landing page's first
  screen recreated as one component (`<!-- @dsCard group="Landing" height=520 -->`),
  real headline, sub-line, primary action and any brand mark from the real page. Width-fluid
  (it is not the cover). A Hero for a project with no landing page shows the landing
  page this system implies: real product name, a plain one-sentence promise drawn from
  the README, one action ("Install", "Open the app", "Read the docs").
- Further components only if the real landing page has them (Nav, Button, Feature
  list, Footer, Pricing...). Each gets preview.html + README.md (first sentence = summary,
  then: when to use, what the consumer supplies, do/don't).
- Logos: copy the real file into `assets/Logos/` with `cp` (never redraw), and write
  `assets/Logos/README.md` (each file: what it is, its ink colour, minimum size).
  No logo exists: write that in README.md "Logo and wordmark" and specify the
  wordmark type (family, weight, case, tracking).
- Contrast: every text token's usage names its ground and ratio; ≥4.5:1 (3:1 at 24px+).
  Check with: `python3 -I ~/ashcode/design-systems/extract/contrast.py <system-dir>`.
- Render and look: `~/ashcode/design-systems/extract/shot.sh <preview.html> <out.png> 960 320`
  (Cover) or `... 1280 800` (Hero), then open the PNG with the Read tool and fix what
  is broken (overflow, overlap, unreadable text, missing font).
- Avoid generic tells: no tracked-out ALL-CAPS eyebrow labels, no `→` on buttons,
  no `A · B · C` meta strings, no blue-purple gradients, no emoji decoration, no
  rounded cards with a coloured left border, no Inter/Roboto as a *new* choice.
- In-repo folder: `<repo>/design-system/` unless MATRIX.md gives another path.

## Overseer rulings after the first build (2026-10-19) — these override earlier text

1. **Cover vs preview width.** The "width-fluid" preview rule applies to Hero and
   component previews. The Cover is a fixed 960px layout (px units only: no vw,
   cqw, clamp() on vw, or media queries). A fixed Cover width is correct.
2. **Real source styles and copy win in formalize and v2.** The "generic tells"
   list applies only to choices the system makes itself (new mode, Cover,
   additions). A real product label that is tracked ALL-CAPS, a real meta string,
   or a real "→" stays exactly as the source has it, cited. Hero copy is
   verbatim from the source (case, punctuation, emoji included), never rewritten.
3. **The Cover and Hero layout are presentation, not tokens.** Their geometry
   (block sizes, positions, the pattern) is not a "new visual choice" under
   formalize. It must use token colours and the brand's real fonts. Its tagline
   may be one sentence in the system's voice.
4. **Mode labels must be honest.** A system that changed any source value or
   copy is `v2`, and README Status lists EVERY change: old value, file:line, new
   value, reason. The owner allows v2 for every non-Retailaer project.
5. **Text tokens.** Every colour used for text names its ground(s) and ratio in
   its usage. A pair under 4.5:1 says "large text only (24px+ or 19px bold)" or
   "source pair kept exact, fails" — and previews never use it for small text.
6. **A value reached through var().** Record the literal value; cite the line
   that uses the variable and the line that defines it.
7. **Swift colours.** `Color(red: 0.12, green: …)` lines are valid sources: cite
   the line and give the hex conversion in the usage.
8. **Paths.** Never absolute. Use paths relative to the project root, or `~/`.
9. **Mirror.** Files copied from a published system stay byte-identical. Every
   addition goes in a NEW file (SOURCES.md, DRIFT.md, a new component folder).
   Repo values that differ from the published system go to DRIFT.md, never into
   the mirrored README or tokens.json.
