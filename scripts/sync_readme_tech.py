#!/usr/bin/env python3
"""Splice the animated per-tech tile grid into README.md (replaces the old
skillicons.dev / shields.io rows).  Idempotent."""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
ICONS = os.path.join(ROOT, "scripts", "icon_data.json")

# key -> (category header, human name, docs URL)
GROUPS = [
    ("LANGUAGES", [("python", "Python"), ("c", "C"), ("javascript", "JavaScript"),
                   ("typescript", "TypeScript"), ("html5", "HTML"), ("css3", "CSS")]),
    ("MACHINE LEARNING", [("pytorch", "PyTorch"), ("tensorflow", "TensorFlow"),
                          ("scikit-learn", "scikit-learn"), ("opencv", "OpenCV"),
                          ("hugging-face", "Hugging Face")]),
    ("DATA · SCIENTIFIC COMPUTING", [("numpy", "NumPy"), ("pandas", "pandas"),
                                     ("matplotlib", "Matplotlib"), ("scipy", "SciPy"),
                                     ("jupyter", "Jupyter"), ("anaconda", "Anaconda")]),
    ("QUANTUM · RESEARCH", [("qiskit", "Qiskit"), ("latex", "LaTeX"), ("arxiv", "arXiv")]),
    ("TOOLS · ENVIRONMENT", [("git", "Git"), ("linux", "Linux"), ("bash", "Bash"),
                             ("docker", "Docker"), ("vs-code", "VS Code")]),
    ("WEB · VERSION HOST", [("react", "React"), ("next-js", "Next.js"), ("github", "GitHub")]),
]

import json
icons = json.load(open(ICONS, encoding="utf-8"))

out = ['<h2 align="center">◈ TECH STACK · EVERY TILE OPENS ITS OFFICIAL DOCS ↗</h2>', '',
       '<div align="center">', '',
       '<sub>28 modules indexed · hover a tile to engage its interface · click to open the '
       'official documentation</sub>', '',
       '<br/>', '']
for gi, (cat, items) in enumerate(GROUPS):
    if gi:
        out += ['<br/><br/>']
    out += ['<sub><code>%s</code></sub><br/><br/>' % cat, '']
    for key, human in items:
        docs = icons[key]["docs"]
        out.append('<a href="%s" title="%s — official documentation">'
                   '<img src="./assets/tech/%s.svg" width="132" height="132" alt="%s"/></a>'
                   % (docs, human, key, human))
    out += ['']
out += ['</div>']
block = "\n".join(out)

src = open(README, encoding="utf-8").read()
start = src.index('<h2 align="center">◈ TECH STACK')
end = src.index('</div>', start) + len('</div>')
src = src[:start] + block + src[end:]
open(README, "w", encoding="utf-8").write(src)
print("README tech-stack block replaced (%d tiles)" % sum(len(i) for _, i in GROUPS))
