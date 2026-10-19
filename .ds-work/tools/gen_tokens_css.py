#!/usr/bin/env python3
"""Compile a system's tokens.json into tokens.css, in the layout the Design
System page compiles ("tokens.css as compiled" in the type's format.md).

Usage: gen_tokens_css.py <system-dir> [--title NAME]
Writes <system-dir>/tokens.css. Line 1 is the marker the page takes over.
"""
import argparse
import json
import os
import re


def css_name(n):
    return "--" + n.lstrip("-.").replace(".", "\\.")


def ref(v):
    m = re.fullmatch(r"\{([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\}", str(v).strip())
    return f"var({css_name(m.group(1))})" if m else str(v).strip()


def length(v):
    v = str(v).strip()
    return v + "px" if re.fullmatch(r"-?\d*\.?\d+", v) and v not in ("0",) else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--title")
    a = ap.parse_args()
    tok = json.load(open(os.path.join(a.dir, "tokens.json")))
    title = a.title or tok.get("name", "Design system")
    out = [f"/* {title} — generated from tokens.json */"]

    color = tok.get("color", {})
    themes = [t["id"] for t in color.get("themes", [])] or ["light"]
    first = themes[0]
    themed = tok.get("shadow", {}).get("tokens", [])

    def val(t, theme):
        v = t.get("value")
        if isinstance(v, dict):
            return v.get(theme, v.get(first))
        return v

    for i, th in enumerate(themes):
        sel = f':root, [data-theme="{th}"]' if i == 0 else f'[data-theme="{th}"]'
        lines = []
        for t in color.get("tokens", []):
            v = val(t, th)
            if i > 0 and not (isinstance(t.get("value"), dict) and th in t["value"]) and not str(v).startswith("{"):
                continue
            if v is not None:
                lines.append(f"  {css_name(t['name'])}: {ref(v)};")
        for t in themed:
            v = val(t, th)
            if i > 0 and not (isinstance(t.get("value"), dict) and th in t["value"]):
                continue
            if v is not None:
                lines.append(f"  {css_name(t['name'])}: {v};")
        if lines:
            out.append(sel + " {")
            out.extend(lines)
            out.append("}")

    root = []
    for fam, body in tok.items():
        if fam in ("name", "version", "meta", "description", "color", "type", "shadow"):
            continue
        if isinstance(body, dict) and isinstance(body.get("tokens"), list):
            for t in body["tokens"]:
                v = t.get("value")
                root.append(f"  {css_name(t['name'])}: {length(v) if fam in ('spacing', 'radius') else v};")
    ty = tok.get("type", {})
    for k, stack in (ty.get("families") or {}).items():
        root.append(f"  --font-{k.lower()}: {stack};")
    if root:
        out.append(":root {")
        out.extend(root)
        out.append("}")

    for g in ty.get("groups", []) or []:
        for s in g.get("styles", []) or []:
            fam = s.get("family", g.get("family"))
            decl = [f"font-family: var(--font-{str(fam).lower()})"] if fam else []
            for k, prop in (("fontSize", "font-size"), ("lineHeight", "line-height"), ("fontWeight", "font-weight"),
                            ("letterSpacing", "letter-spacing"), ("fontStyle", "font-style")):
                if k in s:
                    v = s[k]
                    decl.append(f"{prop}: {length(v) if k in ('fontSize', 'letterSpacing') else v}")
            if s.get("textTransform"):
                decl.append(f"text-transform: {s['textTransform']}")
            out.append(f".{s['name'].replace('.', '-')} {{ {'; '.join(decl)}; }}")

    for f in ty.get("fonts", []) or []:
        fp = f.get("file", "")
        if "/" not in fp:
            fp = "fonts/" + fp
        fmt = {"woff2": "woff2", "woff": "woff", "ttf": "truetype", "otf": "opentype"}.get(fp.rsplit(".", 1)[-1], "woff2")
        out.append("@font-face { font-family: \"%s\"; src: url(\"%s\") format(\"%s\"); font-weight: %s; font-style: %s; font-display: swap; }"
                   % (f["family"], fp, fmt, f.get("weight", "400"), f.get("style", "normal")))

    with open(os.path.join(a.dir, "tokens.css"), "w") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"wrote {os.path.join(a.dir, 'tokens.css')} ({len(out)} lines)")


if __name__ == "__main__":
    main()
