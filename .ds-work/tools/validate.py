#!/usr/bin/env python3
"""Validate one design-system folder against SPEC.md. Read-only.

Checks the tokens.json grammar the Design System page reads, the required
files, the preview contract, and (with --root) that each `path:line`
citation in a token's usage points at a line that holds the token's value.

Usage: validate.py <system-dir> [--root <project-root>] [--retailaer] [--json]
Exit 0 = pass, 1 = errors.
"""
import argparse
import json
import os
import re
import sys

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
COLOR_OK = re.compile(r"^(#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})|(rgba?|hsla?|oklch|oklab|lab|lch)\([^()]*\)|\{[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\})$")
LEN_OK = re.compile(r"^-?\d*\.?\d+(px|rem|em|%)?$")
CITE = re.compile(r"([A-Za-z0-9_./@+~-]*[A-Za-z_][A-Za-z0-9_./@+~-]*\.[A-Za-z][A-Za-z0-9]*):(\d+)")
PROPOSAL_WORDS = re.compile(r"\b(should|recommend\w*|propos\w*|suggest\w*|we could|consider)\b", re.I)
ALLOWED_URL = re.compile(r"https://fonts\.(googleapis|gstatic)\.com")


def hex_forms(v):
    v = v.lower()
    out = {v}
    m = re.fullmatch(r"#([0-9a-f]{6})", v)
    if m and all(m.group(1)[i] == m.group(1)[i + 1] for i in (0, 2, 4)):
        out.add("#" + m.group(1)[0] + m.group(1)[2] + m.group(1)[4])
    m = re.fullmatch(r"#([0-9a-f]{3})", v)
    if m:
        out.add("#" + "".join(c * 2 for c in m.group(1)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--root")
    ap.add_argument("--retailaer", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = a.dir
    errors, warnings = [], []
    stats = {"tokens": 0, "citations": 0, "citations_ok": 0}

    for req in ("README.md", "tokens.json", "SOURCES.md"):
        if not os.path.isfile(os.path.join(d, req)):
            errors.append(f"missing {req}")
    if not a.retailaer and not os.path.isfile(os.path.join(d, "components/Cover/preview.html")):
        errors.append("missing components/Cover/preview.html")

    seen = set()
    tok = None
    try:
        tok = json.load(open(os.path.join(d, "tokens.json")))
    except FileNotFoundError:
        pass
    except Exception as e:
        errors.append(f"tokens.json does not parse: {e}")

    def check_citations(name, value, usage):
        if not a.root or not isinstance(usage, str):
            return
        for path, line in CITE.findall(usage):
            stats["citations"] += 1
            fp = os.path.join(a.root, path)
            if not os.path.isfile(fp):
                errors.append(f"{name}: cited file not found {path}")
                continue
            try:
                lines = open(fp, encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                continue
            n = int(line)
            if n < 1 or n > len(lines):
                errors.append(f"{name}: {path}:{line} is past end of file ({len(lines)} lines)")
                continue
            window = " ".join(lines[max(0, n - 2):n + 1]).lower().replace(" ", "")
            vals = []
            if isinstance(value, dict):
                vals = [str(v) for v in value.values()]
            else:
                vals = [str(value)]
            hit = False
            for v in vals:
                v2 = v.lower().replace(" ", "")
                forms = hex_forms(v2) if v2.startswith("#") else {v2}
                if any(f in window for f in forms):
                    hit = True
            if hit:
                stats["citations_ok"] += 1
            else:
                warnings.append(f"{name}: value {vals} not seen near {path}:{line}")

    if isinstance(tok, dict):
        for fam, body in tok.items():
            if fam in ("name", "version", "meta", "description"):
                continue
            if fam == "type":
                if not isinstance(body, dict):
                    errors.append("type must be an object")
                    continue
                for k in ("fonts", "families", "groups"):
                    if k not in body:
                        errors.append(f"type.{k} missing")
                fams = body.get("families", {})
                if not isinstance(fams, dict):
                    errors.append("type.families must be a map key -> stack")
                    fams = {}
                for g in body.get("groups", []) or []:
                    if g.get("family") not in fams:
                        errors.append(f"type group {g.get('name')} uses family {g.get('family')!r} not in families")
                    for s in g.get("styles", []) or []:
                        if s.get("usage") and "fontSize" in s:
                            check_citations(f"type.{s.get('name')}", {"size": s["fontSize"]}, s.get("usage"))
                        if "fontSize" not in s:
                            errors.append(f"type style {s.get('name')} lacks fontSize")
                        elif not LEN_OK.match(str(s["fontSize"]).strip()):
                            errors.append(f"type style {s.get('name')} fontSize {s['fontSize']!r} not a plain length")
                for f in body.get("fonts", []) or []:
                    fp = f.get("file")
                    if fp and not os.path.isfile(os.path.join(d, fp)):
                        errors.append(f"font file listed but missing: {fp}")
                continue
            if not isinstance(body, dict) or not isinstance(body.get("tokens"), list):
                errors.append(f"family {fam} must be {{'tokens': [...]}} (a list)")
                continue
            themes = [t.get("id") for t in body.get("themes", [])] if fam == "color" else []
            if fam == "color" and not themes:
                errors.append("color.themes missing")
            for t in body["tokens"]:
                stats["tokens"] += 1
                n = t.get("name", "")
                if not NAME.match(n):
                    errors.append(f"{fam}: bad token name {n!r}")
                if n in seen:
                    errors.append(f"duplicate token name {n!r}")
                seen.add(n)
                if not t.get("usage"):
                    warnings.append(f"{fam}.{n}: no usage note")
                v = t.get("value")
                if fam == "color":
                    vals = v.values() if isinstance(v, dict) else [v]
                    if isinstance(v, dict):
                        for k in v:
                            if k not in themes:
                                errors.append(f"color.{n}: theme {k!r} not declared")
                    for x in vals:
                        x = str(x).strip()
                        if not COLOR_OK.match(x):
                            errors.append(f"color.{n}: value {x!r} the page cannot read")
                        elif x.startswith("{") and x[1:-1] not in {tt.get('name') for tt in body['tokens']}:
                            errors.append(f"color.{n}: alias {x} to a missing token")
                elif fam in ("spacing", "radius"):
                    if not LEN_OK.match(str(v).strip()):
                        warnings.append(f"{fam}.{n}: value {v!r} is not a plain length")
                check_citations(f"{fam}.{n}", v, t.get("usage"))

    readme = os.path.join(d, "README.md")
    if os.path.isfile(readme):
        text = open(readme, encoding="utf-8", errors="ignore").read()
        if not text.lstrip().startswith("#"):
            errors.append("README.md must start with a # heading")
        if "## Status" not in text:
            errors.append("README.md lacks ## Status")
        if a.retailaer:
            if "## Drift from canonical" not in text and "Parent" not in text and "canonical" not in d:
                warnings.append("README.md lacks ## Drift from canonical")
            for m in PROPOSAL_WORDS.finditer(text):
                ctx = text[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
                errors.append(f"proposal wording in a Retailaer extraction: ...{ctx}...")

    comp = os.path.join(d, "components")
    if os.path.isdir(comp):
        for c in sorted(os.listdir(comp)):
            p = os.path.join(comp, c, "preview.html")
            if not os.path.isfile(p):
                continue
            html = open(p, encoding="utf-8", errors="ignore").read()
            first = html.splitlines()[0] if html else ""
            if not first.startswith("<!-- @dsCard"):
                errors.append(f"components/{c}/preview.html line 1 lacks @dsCard marker")
            if re.search(r"<script\b", html, re.I):
                errors.append(f"components/{c}/preview.html contains a script")
            for u in re.findall(r"https?://[^\s\"')]+", html):
                if not ALLOWED_URL.match(u):
                    errors.append(f"components/{c}/preview.html loads {u}")
            if "background" not in html:
                warnings.append(f"components/{c}/preview.html sets no background")

    res = {"dir": d, "pass": not errors, "errors": errors, "warnings": warnings[:60], **stats}
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"{'PASS' if not errors else 'FAIL'} {d}: {stats['tokens']} tokens, "
              f"citations {stats['citations_ok']}/{stats['citations']} matched, "
              f"{len(errors)} errors, {len(warnings)} warnings")
        for e in errors[:40]:
            print("  ERROR", e)
        for w in warnings[:25]:
            print("  warn ", w)
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
