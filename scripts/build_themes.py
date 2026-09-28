#!/usr/bin/env python3
"""Multi-theme builder for the KCN-369 profile README.

Theme 1 = the source design (README.md, assets/, profile/).
Every other theme in themes/palettes.json is generated into themes/<id>/
by remapping colours, and a THEME SWITCHER bar is (re)written into every
README between the <!-- THEME-SWITCHER:START/END --> markers.

Usage:  python scripts/build_themes.py        (standard library only)
"""
import json, re, shutil
from urllib.parse import quote
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/KCN-369/KCN-369"
START, END = "<!-- THEME-SWITCHER:START -->", "<!-- THEME-SWITCHER:END -->"
HEX = re.compile(r"(?<![0-9A-Za-z])([0-9A-Fa-f]{6})(?![0-9A-Za-z])")

cfg = json.loads((ROOT / "themes/palettes.json").read_text(encoding="utf-8"))
base, themes = cfg["base"], cfg["themes"]


def link(t):
    return f"{REPO_URL}#readme" if t["id"] == 1 else f"{REPO_URL}/blob/main/themes/{t['id']}/README.md"


def switcher(active_id):
    badges = []
    for t in themes:
        on = t["id"] == active_id
        pal = {**base, **t["colors"]}
        esc = lambda x: quote(x.replace("-", "--").replace("_", "__"), safe="")
        label = esc(f"THEME {t['id']}")
        msg = esc(("● " if on else "") + t["name"].upper())
        color = pal["primary"] if on else pal["muted"]
        badges.append(
            f'<a href="{link(t)}"><img src="https://img.shields.io/badge/{label}-{msg}-{color}'
            f'?style=for-the-badge&labelColor={pal["bg"]}" alt="Theme {t["id"]}: {t["name"]}"/></a>'
        )
    return (f'{START}\n<div align="center">\n<sub><code>◈ THEME SWITCHER — click a theme</code></sub><br/>\n'
            + "\n".join(badges) + f"\n</div>\n{END}")


def put_switcher(text, active_id):
    block = switcher(active_id)
    if START in text:
        return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    # first run: insert right after the header comment block
    idx = text.find('<div align="center">')
    return text[:idx] + block + "\n\n" + text[idx:]


def recolor(text, mapping):
    def sub(m):
        new = mapping.get(m.group(1).upper())
        if not new:
            return m.group(1)
        return new.lower() if m.group(1).islower() else new
    return HEX.sub(sub, text)


src_readme = (ROOT / "README.md").read_text(encoding="utf-8")
src_readme = put_switcher(src_readme, 1)
(ROOT / "README.md").write_text(src_readme, encoding="utf-8")

for t in themes:
    if t["id"] == 1:
        continue
    mapping = {base[k].upper(): v.upper() for k, v in t["colors"].items() if k in base}
    out = ROOT / "themes" / str(t["id"])
    if out.exists():
        shutil.rmtree(out)
    for folder in ("assets", "profile"):
        (out / folder).mkdir(parents=True)
        for f in sorted((ROOT / folder).glob("*.svg")):
            (out / folder / f.name).write_text(recolor(f.read_text(encoding="utf-8"), mapping), encoding="utf-8")
    readme = recolor(src_readme, mapping)
    readme = put_switcher(readme, t["id"])
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(f"built theme {t['id']}: {t['name']} -> {out.relative_to(ROOT)}")
print("done")
