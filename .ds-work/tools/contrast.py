#!/usr/bin/env python3
"""Report WCAG contrast for a system's text/ground colour pairs, per theme.

Pairs come from each colour token's usage note ("on `surface`", "on surface")
and, as a fallback, from names: text-like tokens (ink, text, fg, muted, on-*)
against ground-like tokens (bg, surface, paper, canvas, ground, background).
Usage: contrast.py <system-dir> [--min 4.5]
Exit 0 when every usage-named pair passes; name-based pairs are informative.
"""
import argparse
import json
import os
import re
import sys

TEXT = re.compile(r"(^|[-_.])(ink|text|fg|foreground|muted|on)([-_.]|$)|^on-", re.I)
GROUND = re.compile(r"(bg|surface|paper|canvas|ground|background|page|card|panel|sheet)", re.I)


def parse(v):
    v = v.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return r, g, b, a
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)", v)
    if m:
        a = m.group(4)
        a = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
        return float(m.group(1)), float(m.group(2)), float(m.group(3)), a
    return None


def lum(c):
    def ch(x):
        x /= 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = c[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def blend(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--min", type=float, default=4.5)
    a = ap.parse_args()
    tok = json.load(open(os.path.join(a.dir, "tokens.json")))
    color = tok.get("color", {})
    themes = [t["id"] for t in color.get("themes", [])] or ["light"]
    toks = {t["name"]: t for t in color.get("tokens", [])}

    def resolve(name, theme, depth=0):
        t = toks.get(name)
        if not t or depth > 16:
            return None
        v = t["value"]
        if isinstance(v, dict):
            v = v.get(theme, v.get(themes[0]))
        v = str(v)
        m = re.fullmatch(r"\{(.+)\}", v.strip())
        if m:
            return resolve(m.group(1), theme, depth + 1)
        return parse(v)

    fails = 0
    named_pairs = set()
    for n, t in toks.items():
        for g in re.findall(r"\bon\s+`?([A-Za-z0-9][A-Za-z0-9_.-]{0,63})`?", t.get("usage", "") or ""):
            if g in toks and g != n:
                named_pairs.add((n, g))
    name_pairs = {(n, g) for n in toks for g in toks
                  if n != g and TEXT.search(n) and GROUND.search(g) and not TEXT.search(g)} - named_pairs

    for label, pairs, strict in (("usage-named pairs", named_pairs, True), ("name-inferred pairs", name_pairs, False)):
        if not pairs:
            continue
        print(f"## {label}")
        for th in themes:
            for fg, bg in sorted(pairs):
                f, b = resolve(fg, th), resolve(bg, th)
                if not f or not b:
                    continue
                if b[3] < 1:
                    continue
                r = ratio(blend(f, b), b)
                ok = r >= a.min
                large_ok = r >= 3.0
                mark = "ok " if ok else ("3:1" if large_ok else "LOW")
                if strict and not ok:
                    fails += 1
                print(f"  [{th}] {mark} {r:5.2f}  {fg} on {bg}")
    if fails:
        print(f"{fails} usage-named pair(s) under {a.min}:1 (3:1 passes only for text 24px+ or bold 19px+; say so in the token's usage)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
