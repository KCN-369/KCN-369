#!/usr/bin/env python3
"""
Fetch the brand icon geometry used by assets/techstack.svg and store it in
scripts/icon_data.json, so the card can be rebuilt offline (no network) by
scripts/build_assets.py.

Sources (both public, MIT-licensed):
  · simple-icons  -> single-path monochrome logos
  · devicon       -> multi-path coloured logos

Usage:  python3 scripts/fetch_icons.py
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "scripts", "icon_data.json")
UA = {"User-Agent": "kcn-lab-profile-cards", "Accept": "application/vnd.github.raw"}

# name, docs url, icon source, brand colour
TECH = [
    ("Python", "https://docs.python.org/3/", "simple-icons/python", "#3776AB"),
    ("C++", "https://en.cppreference.com/w/", "simple-icons/cplusplus", "#00599C"),
    ("JavaScript", "https://developer.mozilla.org/en-US/docs/Web/JavaScript", "simple-icons/javascript", "#F7DF1E"),
    ("TypeScript", "https://www.typescriptlang.org/docs/", "simple-icons/typescript", "#3178C6"),
    ("HTML5", "https://developer.mozilla.org/en-US/docs/Web/HTML", "simple-icons/html5", "#E34F26"),
    ("CSS3", "https://developer.mozilla.org/en-US/docs/Web/CSS", "simple-icons/css", "#1572B6"),

    ("PyTorch", "https://pytorch.org/docs/stable/", "simple-icons/pytorch", "#EE4C2C"),
    ("TensorFlow", "https://www.tensorflow.org/api_docs", "simple-icons/tensorflow", "#FF6F00"),
    ("scikit-learn", "https://scikit-learn.org/stable/", "simple-icons/scikitlearn", "#F7931E"),
    ("OpenCV", "https://docs.opencv.org/4.x/", "simple-icons/opencv", "#5C3EE8"),
    ("Hugging Face", "https://huggingface.co/docs", "simple-icons/huggingface", "#FFD21E"),
    ("Anaconda", "https://docs.anaconda.com/", "simple-icons/anaconda", "#44A833"),

    ("NumPy", "https://numpy.org/doc/stable/", "simple-icons/numpy", "#013243"),
    ("pandas", "https://pandas.pydata.org/docs/", "simple-icons/pandas", "#150458"),
    ("Matplotlib", "https://matplotlib.org/stable/", "devicon/matplotlib/matplotlib-original", "#11557C"),
    ("SciPy", "https://docs.scipy.org/doc/scipy/", "simple-icons/scipy", "#8CAAE6"),
    ("Jupyter", "https://docs.jupyter.org/", "simple-icons/jupyter", "#F37626"),

    ("Qiskit", "https://docs.quantum.ibm.com/", "simple-icons/qiskit", "#6929C4"),
    ("LaTeX", "https://www.latex-project.org/help/documentation/", "simple-icons/latex", "#008080"),
    ("arXiv", "https://info.arxiv.org/help/index.html", "simple-icons/arxiv", "#B31B1B"),

    ("Git", "https://git-scm.com/doc", "simple-icons/git", "#F05032"),
    ("Linux", "https://www.kernel.org/doc/html/latest/", "simple-icons/linux", "#FCC624"),
    ("Bash", "https://www.gnu.org/software/bash/manual/bash.html", "simple-icons/gnubash", "#4EAA25"),
    ("Docker", "https://docs.docker.com/", "simple-icons/docker", "#2496ED"),
    ("VS Code", "https://code.visualstudio.com/docs", "devicon/vscode/vscode-original", "#007ACC"),
    ("React", "https://react.dev/learn", "simple-icons/react", "#61DAFB"),
    ("Next.js", "https://nextjs.org/docs", "simple-icons/nextdotjs", "#000000"),
    ("GitHub", "https://docs.github.com/", "simple-icons/github", "#181717"),
]


def raw(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def parse(svg: str) -> dict:
    """Strip the root <svg> tag, keep inner geometry + viewBox."""
    vb = re.search(r'viewBox="([^"]+)"', svg)
    inner = re.sub(r"^.*?<svg[^>]*>", "", svg, flags=re.S)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.S).strip()
    inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)
    return {"vb": vb.group(1) if vb else "0 0 24 24", "inner": inner}


def main() -> int:
    data = {}
    for name, docs, src, color in TECH:
        kind, path = src.split("/", 1)
        if kind == "simple-icons":
            url = ("https://api.github.com/repos/simple-icons/simple-icons"
                   f"/contents/icons/{path}.svg")
        else:
            url = f"https://api.github.com/repos/devicons/devicon/contents/icons/{path}.svg"
        svg = raw(url)
        parsed = parse(svg)
        key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        data[key] = {"name": name, "docs": docs, "color": color, **parsed}
        print(f"{name:14s} <- {src:42s} {len(parsed['inner']):6d} chars  vb={parsed['vb']}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    print(f"\nwrote {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT) / 1024:.1f} KB, {len(data)} icons)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
