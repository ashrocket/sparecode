#!/usr/bin/env python3
"""Print a compact digest of one evidence JSON from extract.py.

Usage: digest.py <evidence.json> [--vars N] [--colors N] [--grep TEXT]
--grep limits custom properties to names containing TEXT (e.g. color, font).
"""
import argparse
import json


def at(locs, n=2):
    return ", ".join(locs[:n])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--vars", type=int, default=45)
    ap.add_argument("--colors", type=int, default=25)
    ap.add_argument("--grep", default="")
    a = ap.parse_args()
    d = json.load(open(a.file))
    print(f"# {d['project']}  root={d['root']}  scanned={d['scanned_text_files']}")
    print("titles:", "; ".join(f"{t['value']} ({at(t['at'],1)})" for t in d["titles"][:6]))
    if d["theme_color_meta"]:
        print("theme-color:", "; ".join(f"{t['value']} ({at(t['at'],1)})" for t in d["theme_color_meta"][:4]))
    print("design-system files:", ", ".join(d["design_system_files"][:20]) or "none")
    print("landing candidates:", ", ".join(d["landing_candidates"][:12]) or "none")
    print("tailwind:", ", ".join(d["tailwind_configs"]) or "none")
    print("\n## custom properties (name: most common definitions @ first location)")
    shown = 0
    for v in d["custom_properties"]:
        if a.grep and a.grep not in v["name"]:
            continue
        defs = " | ".join(f"{x['value']} x{x['count']} @{x['at'][0]}" for x in v["defs"][:3])
        print(f"{v['name']}: {defs}")
        shown += 1
        if shown >= a.vars:
            break
    print(f"\n## colours (top {a.colors} by count)")
    for c in d["colors"][:a.colors]:
        print(f"{c['value']} x{c['count']} @{at(c['at'])}")
    for key in ("font_families", "font_face_families", "google_fonts", "swift_fonts"):
        if d[key]:
            print(f"\n## {key}")
            for f in d[key][:12]:
                print(f"{f['value']} x{f['count']} @{at(f['at'],1)}")
    if d["font_files"]:
        print("\nfont files:", ", ".join(d["font_files"][:15]))
    for key in ("font_sizes", "font_weights", "line_heights", "letter_spacing", "radii", "shadows"):
        if d[key]:
            print(f"\n## {key}: " + "; ".join(f"{x['value']} x{x['count']}" for x in d[key][:14]))
    if d["colorsets"]:
        print("\n## Xcode colorsets")
        for c in d["colorsets"][:30]:
            vals = []
            for v in c["values"]:
                comp = v["components"]
                vals.append(f"{'/'.join(v['appearance'])}:" + ",".join(f"{k}={comp[k]}" for k in ("red", "green", "blue", "alpha") if k in comp))
            print(f"{c['name']} ({c['path']}): {' ; '.join(vals)}")
    if d["logo_candidates"]:
        print("\n## logo/icon files")
        for l in d["logo_candidates"][:30]:
            print(f"{l['path']} ({l['bytes']} B)")


if __name__ == "__main__":
    main()
