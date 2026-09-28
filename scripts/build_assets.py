#!/usr/bin/env python3
"""
KCN_LAB :: static asset builder  (LIGHT THEME · futuristic "photon lab")
=======================================================================

Writes every hand-drawn SVG used by README.md into assets/ :

  hero.svg      banner with the atom sigil + KCN_LAB wordmark
  avatar.svg    identity sigil (also exported as avatar.png — upload it as
                your GitHub profile picture, Settings -> Profile)
  divider.svg   holographic hairline divider
  terminal.svg  boot-sequence terminal + system monitor
  status.svg    system status / focus-index dashboard
  focus.svg     current-focus chips
  journey.svg   learning journey loop
  registry.svg  PROJECT DATABASE + RESEARCH CORE (sealed / ongoing, no names)
  footer.svg    end-of-transmission footer
  avatar.png    512x512 raster of the identity sigil (pure-python PNG writer)

Standard library only.  Usage:  python3 scripts/build_assets.py
"""
from __future__ import annotations

import json
import math
import os
import random
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")

# ───────────────────────────── palette (light) ─────────────────────────────
PAPER = "#F4F8FE"
PANEL = "#FFFFFF"
PANEL2 = "#EDF3FB"
INK = "#0B1220"
INK2 = "#3D4B63"
MUTED = "#7C8CA6"
LINE = "#D8E4F4"
GRID = "#E4ECF7"

CY, BL, VI, MG, GR, AM = "#0E7490", "#2563EB", "#7C3AED", "#DB2777", "#047857", "#B45309"
CY_L, BL_L, VI_L, MG_L, GR_L, AM_L = "#22D3EE", "#60A5FA", "#A78BFA", "#F472B6", "#34D399", "#FBBF24"

FONT = ("'JetBrains Mono','Fira Code','SF Mono',SFMono-Regular,ui-monospace,"
        "Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace")

DEFS = f"""<defs>
  <linearGradient id="holo" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{CY_L}"/><stop offset=".38" stop-color="{BL_L}"/>
    <stop offset=".68" stop-color="{VI_L}"/><stop offset="1" stop-color="{MG_L}"/></linearGradient>
  <linearGradient id="holoV" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{VI_L}"/><stop offset=".55" stop-color="{BL_L}"/>
    <stop offset="1" stop-color="{CY_L}"/></linearGradient>
  <linearGradient id="paper" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="{PAPER}"/></linearGradient>
  <linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>
    <stop offset=".5" stop-color="#FFFFFF" stop-opacity=".85"/>
    <stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
  <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
    <path d="M32 0H0V32" fill="none" stroke="{CY}" stroke-opacity=".07"/></pattern>
  <radialGradient id="gc"><stop offset="0" stop-color="{CY_L}" stop-opacity=".22"/>
    <stop offset="1" stop-color="{CY_L}" stop-opacity="0"/></radialGradient>
  <radialGradient id="gv"><stop offset="0" stop-color="{VI_L}" stop-opacity=".20"/>
    <stop offset="1" stop-color="{VI_L}" stop-opacity="0"/></radialGradient>
  <radialGradient id="gm"><stop offset="0" stop-color="{MG_L}" stop-opacity=".18"/>
    <stop offset="1" stop-color="{MG_L}" stop-opacity="0"/></radialGradient>
  <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="2.2" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="7"/></filter>
</defs>"""

BASE_CSS = f"""
  text {{ font-family: {FONT}; }}
  .spin {{ animation: spin 18s linear infinite; transform-box: fill-box; transform-origin: center; }}
  .spin-s {{ animation: spin 9s linear infinite reverse; transform-box: fill-box; transform-origin: center; }}
  @keyframes spin {{ to {{ transform: rotate(360deg) }} }}
  .blink {{ animation: blink 1.05s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0 }} }}
  .pulse {{ animation: pulse 2s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity: .35 }} 50% {{ opacity: 1 }} }}
  .rise {{ animation: rise .8s cubic-bezier(.2,.8,.2,1) both; }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(12px) }} to {{ opacity: 1; transform: none }} }}
  .sweep {{ animation: sweep 5s cubic-bezier(.4,0,.6,1) infinite; }}
  @keyframes sweep {{ 0% {{ transform: translateX(-260px) }} 55%,100% {{ transform: translateX(1100px) }} }}
"""


def frame(W: int, H: int, radius: int = 18, top_strip: bool = True) -> str:
    s = f'<rect x="0" y="0" width="{W}" height="{H}" rx="{radius}" fill="url(#paper)"/>'
    if top_strip:
        s += f'<rect x="0" y="0" width="{W}" height="4" rx="2" fill="url(#holo)"/>'
    s += (f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="{radius - 1}" '
          f'fill="none" stroke="{LINE}" stroke-width="1.5"/>')
    return s


def brackets(W: int, H: int, inset: int = 14, arm: int = 26, color: str = CY, op: float = .55) -> str:
    out = []
    for (x, y, sx, sy) in [(inset, inset, 1, 1), (W - inset, inset, -1, 1),
                           (inset, H - inset, 1, -1), (W - inset, H - inset, -1, -1)]:
        out.append(f'<path d="M{x},{y + sy * arm} L{x},{y} L{x + sx * arm},{y}" fill="none" '
                   f'stroke="{color}" stroke-opacity="{op}" stroke-width="1.6" stroke-linecap="round"/>')
    return "".join(out)


def sparkles(seed: int, n: int, x0: int, x1: int, y0: int, y1: int, colors=None, rmax: float = 1.4) -> str:
    rnd = random.Random(seed)
    colors = colors or ["#93C5FD", "#C4B5FD", "#F9A8D4", "#A5F3FC"]
    out = []
    for _ in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rnd.choice([.6, .8, 1.0, rmax])
        c = rnd.choice(colors)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{c}" class="tw" '
                   f'style="animation-delay:-{rnd.uniform(0, 5):.2f}s;'
                   f'animation-duration:{rnd.uniform(2.6, 5.4):.2f}s"/>')
    return "".join(out)


def chip(x: float, y: float, w: float, h: float, label: str, color: str, fs: float = 12,
         fill_op: float = .07) -> str:
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2:.1f}" '
            f'fill="{color}" fill-opacity="{fill_op}" stroke="{color}" stroke-opacity=".5"/>'
            f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + fs * .36:.1f}" font-size="{fs}" fill="{color}" '
            f'text-anchor="middle" letter-spacing="1.4" font-weight="600">{label}</text>')


GLYPHS = {
    # 24x24 stroke glyphs drawn inside the focus chips
    "net": "M12 5v5M5 19h14M7 10h10M12 14v5M7 10l5 4 5-4",
    "eye": "M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
    "wave": "M2 15l4-7 4 10 4-13 4 9 4-4",
    "atom": "M12 12a2 2 0 1 0 0-4 2 0 0 0 0 4zM4 6c4 3 12 6 16 10M20 6c-4 3-12 6-16 10",
    "layers": "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5",
    "search": "M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15zM21 21l-6-6",
}


def glyph(name: str, cx: float, cy: float, color: str, size: float = 18, sw: float = 1.6) -> str:
    k = size / 24
    return (f'<path d="{GLYPHS[name]}" transform="translate({cx - size / 2:.1f} {cy - size / 2:.1f}) '
            f'scale({k:.4f})" fill="none" stroke="{color}" stroke-width="{sw / k:.2f}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


# ───────────────────────────────── HERO ────────────────────────────────────
def hero() -> str:
    W, H = 1000, 300
    o = []
    o.append(f'<rect width="{W}" height="{H}" rx="18" fill="url(#paper)"/>')
    o.append(f'<rect width="{W}" height="{H}" rx="18" fill="url(#grid)" opacity=".55"/>')
    o.append(f'<circle cx="150" cy="150" r="200" fill="url(#gc)"/>')
    o.append(f'<circle cx="860" cy="120" r="230" fill="url(#gv)"/>')
    o.append(f'<circle cx="520" cy="300" r="190" fill="url(#gm)"/>')
    o.append(sparkles(11, 26, 20, 980, 20, 280))
    o.append(brackets(W, H))
    o.append(f'<rect x="0" y="0" width="{W}" height="4" rx="2" fill="url(#holo)"/>')
    o.append(f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="17.5" fill="none" '
             f'stroke="{LINE}" stroke-width="1.5"/>')

    # ---- atom sigil ----
    cx, cy = 158, 150
    o.append(f'<circle cx="{cx}" cy="{cy}" r="86" fill="none" stroke="{LINE}" stroke-width="1"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="86" fill="none" stroke="{CY}" stroke-opacity=".35" '
             f'stroke-width="1.4" stroke-dasharray="3 9" class="spin"/>')
    for rot, col in ((0, CY), (60, VI), (120, MG)):
        o.append(f'<g transform="rotate({rot} {cx} {cy})">'
                 f'<ellipse cx="{cx}" cy="{cy}" rx="86" ry="32" fill="none" stroke="{col}" '
                 f'stroke-opacity=".45" stroke-width="1.6"/></g>')
    o.append(f'<g class="spin" style="animation-duration:26s">'
             f'<circle cx="{cx + 86}" cy="{cy}" r="4.6" fill="{CY}" filter="url(#glow)"/></g>')
    o.append(f'<g class="spin" style="animation-duration:34s;animation-direction:reverse">'
             f'<circle cx="{cx - 43}" cy="{cy + 74}" r="4" fill="{MG}" filter="url(#glow)"/></g>')
    o.append(f'<g class="spin" style="animation-duration:20s">'
             f'<circle cx="{cx + 74}" cy="{cy - 43}" r="3.4" fill="{VI}" filter="url(#glow)"/></g>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="26" fill="url(#gv)"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="17" fill="url(#holo)"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="17" fill="none" stroke="#FFFFFF" stroke-opacity=".7"/>')
    o.append(f'<text x="{cx}" y="{cy + 4.5}" font-size="12" font-weight="800" fill="#FFFFFF" '
             f'text-anchor="middle" letter-spacing="1">KCN</text>')

    # ---- wordmark ----
    o.append(f'<text x="288" y="66" font-size="11" fill="{MUTED}" letter-spacing="3.4">'
             f'// PROFILE_v2 · LIGHT PROTOCOL · SYNC OK</text>')
    o.append(f'<text x="286" y="126" font-size="58" font-weight="800" letter-spacing="1" fill="url(#holo)">'
             f'KCN_LAB</text>')
    o.append(f'<text x="290" y="154" font-size="17" fill="{INK2}" letter-spacing="7.5">KANHU NAYAK</text>')
    o.append(f'<line x1="290" y1="170" x2="958" y2="170" stroke="{LINE}"/>')
    labels = [("PHYSICS", CY), ("AI / ML", VI), ("QUANTUM COMPUTING", MG), ("OPEN SOURCE", GR)]
    x = 290
    for label, col in labels:
        w = 26 + len(label) * 8.6
        o.append(chip(x, 188, w, 26, label, col, 11.5))
        x += w + 10
    o.append(f'<circle cx="296" cy="240" r="5" fill="{GR}" class="pulse"/>')
    o.append(f'<text x="310" y="244" font-size="12.5" fill="{INK2}" letter-spacing="1.6">'
             f'SYSTEM ONLINE</text>')
    o.append(f'<text x="440" y="244" font-size="12.5" fill="{MUTED}" letter-spacing="1.6">'
             f'MODE <tspan fill="{VI}" font-weight="700">EXPLORATION</tspan></text>')
    o.append(f'<text x="640" y="244" font-size="12.5" fill="{MUTED}" letter-spacing="1.6">'
             f'CURIOSITY <tspan fill="{MG}" font-weight="700">MAX</tspan></text>')
    o.append(f'<text x="958" y="244" font-size="11" fill="{MUTED}" text-anchor="end" '
             f'letter-spacing="1.6">kcn@lab:~/profile ▸<tspan class="blink" fill="{CY}">█</tspan></text>')
    o.append(f'<rect x="286" y="262" width="672" height="3" rx="1.5" fill="{GRID}"/>'
             f'<rect x="286" y="262" width="230" height="3" rx="1.5" fill="url(#holo)" class="load"/>')

    css = BASE_CSS + f"""
  .tw {{ animation: tw 4.2s ease-in-out infinite; }}
  @keyframes tw {{ 0%,100% {{ opacity: .12 }} 50% {{ opacity: 1 }} }}
  .load {{ animation: load 6s cubic-bezier(.4,0,.6,1) infinite; }}
  @keyframes load {{ 0% {{ width: 40px }} 55%,90% {{ width: 672px }} 100% {{ width: 40px }} }}
"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="KCN_LAB — Kanhu Nayak · Physics × AI/ML × Quantum Computing × '
            f'Open Source">\n<title>KCN_LAB :: HERO</title>\n<style>{css}</style>\n{DEFS}\n'
            + "\n".join(o) + "\n</svg>\n")


# ──────────────────────────────── AVATAR ──────────────────────────────────
def avatar_svg() -> str:
    S = 440
    c = S / 2
    o = []
    o.append(f'<rect width="{S}" height="{S}" rx="34" fill="url(#paper)"/>')
    o.append(f'<rect width="{S}" height="{S}" rx="34" fill="url(#grid)" opacity=".5"/>')
    o.append(f'<circle cx="{c}" cy="{c}" r="190" fill="url(#gv)"/>')
    o.append(f'<circle cx="{c}" cy="{c}" r="150" fill="url(#gc)"/>')
    o.append(sparkles(7, 18, 24, S - 24, 24, S - 24))
    # hexagon frame
    pts = " ".join(f"{c + 168 * math.cos(math.radians(60 * i + 30)):.1f},"
                   f"{c + 168 * math.sin(math.radians(60 * i + 30)):.1f}" for i in range(6))
    o.append(f'<polygon points="{pts}" fill="#FFFFFF" fill-opacity=".82" stroke="url(#holo)" '
             f'stroke-width="3"/>')
    pts2 = " ".join(f"{c + 150 * math.cos(math.radians(60 * i + 30)):.1f},"
                    f"{c + 150 * math.sin(math.radians(60 * i + 30)):.1f}" for i in range(6))
    o.append(f'<polygon points="{pts2}" fill="none" stroke="{VI}" stroke-opacity=".35" '
             f'stroke-width="1" stroke-dasharray="4 7" class="spin" style="animation-duration:40s"/>')
    # orbits
    for rot, col in ((0, CY), (60, VI), (120, MG)):
        o.append(f'<g transform="rotate({rot} {c} {c})"><ellipse cx="{c}" cy="{c}" rx="132" ry="48" '
                 f'fill="none" stroke="{col}" stroke-opacity=".4" stroke-width="1.5"/></g>')
    o.append(f'<g class="spin" style="animation-duration:22s"><circle cx="{c + 132}" cy="{c}" r="5" '
             f'fill="{CY}" filter="url(#glow)"/></g>')
    o.append(f'<g class="spin" style="animation-duration:30s;animation-direction:reverse">'
             f'<circle cx="{c - 66}" cy="{c + 114}" r="4.2" fill="{MG}" filter="url(#glow)"/></g>')
    # core + monogram
    o.append(f'<circle cx="{c}" cy="{c}" r="72" fill="#FFFFFF" stroke="{LINE}" stroke-width="1.5"/>')
    o.append(f'<circle cx="{c}" cy="{c}" r="72" fill="none" stroke="url(#holo)" stroke-width="2.4" '
             f'stroke-dasharray="120 332" class="spin" style="animation-duration:12s"/>')
    o.append(f'<text x="{c}" y="{c + 22}" font-size="62" font-weight="800" fill="{INK}" '
             f'text-anchor="middle" letter-spacing="2">KCN</text>')
    o.append(f'<text x="{c}" y="{c + 48}" font-size="12.5" fill="{MUTED}" text-anchor="middle" '
             f'letter-spacing="6">N A Y A K</text>')
    o.append(f'<line x1="{c - 52}" y1="{c - 30}" x2="{c + 52}" y2="{c - 30}" stroke="{LINE}"/>')
    o.append(f'<text x="{c}" y="{c - 40}" font-size="11" fill="{VI}" text-anchor="middle" '
             f'letter-spacing="3.4" font-weight="700">KCN_LAB</text>')
    # badges
    o.append(chip(c - 92, S - 74, 184, 26, "UG · RESEARCHER", VI, 11))
    o.append(f'<text x="{c}" y="{S - 26}" font-size="10.5" fill="{MUTED}" text-anchor="middle" '
             f'letter-spacing="2.6">PHYSICS × AI/ML × QUANTUM</text>')

    css = BASE_CSS + f"""
  .tw {{ animation: tw 4s ease-in-out infinite; }}
  @keyframes tw {{ 0%,100% {{ opacity: .12 }} 50% {{ opacity: 1 }} }}
"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}" '
            f'role="img" aria-label="KCN_LAB identity sigil — Kanhu Nayak, undergraduate researcher">\n'
            f'<title>KCN_LAB :: IDENTITY SIGIL</title>\n<style>{css}</style>\n{DEFS}\n'
            + "\n".join(o) + "\n</svg>\n")


# ──────────────────────────────── DIVIDER ─────────────────────────────────
def divider() -> str:
    W, H = 1000, 34
    o = []
    o.append(f'<line x1="0" y1="{H / 2}" x2="{W}" y2="{H / 2}" stroke="url(#holo)" stroke-width="2" '
             f'stroke-opacity=".55"/>')
    o.append(f'<line x1="0" y1="{H / 2}" x2="{W}" y2="{H / 2}" stroke="#FFFFFF" stroke-width="4" '
             f'stroke-dasharray="60 900" class="sweep" opacity=".9"/>')
    for x in (140, 860):
        o.append(f'<path d="M{x},{H / 2 - 9} L{x + 12},{H / 2} L{x},{H / 2 + 9} Z" fill="{VI}" '
                 f'fill-opacity=".55"/>')
    o.append(f'<rect x="{W / 2 - 46}" y="{H / 2 - 11}" width="92" height="22" rx="11" fill="#FFFFFF" '
             f'stroke="{LINE}"/>')
    o.append(f'<circle cx="{W / 2 - 30}" cy="{H / 2}" r="3.4" fill="{CY}"/>')
    o.append(f'<circle cx="{W / 2}" cy="{H / 2}" r="3.4" fill="{VI}"/>')
    o.append(f'<circle cx="{W / 2 + 30}" cy="{H / 2}" r="3.4" fill="{MG}"/>')
    css = BASE_CSS + """
  .sweep { animation: sweep 6s cubic-bezier(.4,0,.6,1) infinite; }
  @keyframes sweep { 0% { transform: translateX(-160px) } 60%,100% { transform: translateX(1060px) } }
"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="decorative divider">\n<title>KCN_LAB :: DIVIDER</title>\n'
            f'<style>{css}</style>\n{DEFS}\n' + "\n".join(o) + "\n</svg>\n")


# ──────────────────────────────── TERMINAL ────────────────────────────────
def terminal() -> str:
    W, H = 1000, 392
    o = []
    o.append(frame(W, H))
    o.append(sparkles(3, 14, 20, 980, 20, 370, rmax=1.1))
    # left: terminal window
    o.append(f'<rect x="16" y="16" width="640" height="360" rx="12" fill="{PANEL}" stroke="{LINE}"/>')
    o.append(f'<rect x="16" y="16" width="640" height="30" rx="12" fill="{PANEL2}"/>')
    o.append(f'<rect x="16" y="38" width="640" height="8" fill="{PANEL2}"/>')
    for i, col in enumerate((MG, AM, GR)):
        o.append(f'<circle cx="{36 + i * 18}" cy="31" r="5" fill="{col}" fill-opacity=".75"/>')
    o.append(f'<text x="336" y="35" font-size="11" fill="{MUTED}" text-anchor="middle" '
             f'letter-spacing="1.6">kcn@lab — zsh — 80×24</text>')

    lines = [
        ("kcn@lab:~$ ./boot --profile KCN-369", INK, 0),
        ("[ OK ] core.physics ............... ACTIVE", GR, .35),
        ("[ OK ] module.ai_ml ............... LEARNING", BL, .6),
        ("[ OK ] module.deep_learning ....... LEARNING", BL, .85),
        ("[ OK ] module.quantum ............. EXPLORING", AM, 1.1),
        ("[ OK ] engine.curiosity ........... ONLINE", MG, 1.35),
        ("kcn@lab:~$ cat identity.bin", INK, 1.6),
        ("# curiosity defined in binary terms (0/1) ::", MUTED, 1.85),
        ("  0  ≈  stay simple, accept weakness, give up", "#B91C1C", 2.1),
        ("  1  ≈  do whatever it takes to satisfy curiosity !!", CY, 2.35),
        ("kcn@lab:~$ echo $CHOICE", INK, 2.6),
        (">> 1    // curiosity.mode = MAX", GR, 2.85),
    ]
    y = 76
    for text, col, delay in lines:
        o.append(f'<g class="rise" style="animation-delay:{delay:.2f}s">'
                 f'<text x="34" y="{y}" font-size="13.5" fill="{col}" xml:space="preserve">{text}</text></g>')
        y += 24
    o.append(f'<g class="rise" style="animation-delay:3.1s"><text x="34" y="{y}" font-size="13.5" '
             f'fill="{GR}">kcn@lab:~$ </text>'
             f'<rect x="128" y="{y - 13}" width="9" height="16" fill="{CY}" class="blink"/></g>')

    # right: system monitor
    o.append(f'<rect x="672" y="16" width="312" height="360" rx="12" fill="{PANEL2}" stroke="{LINE}"/>')
    o.append(f'<text x="690" y="46" font-size="12" fill="{VI}" letter-spacing="2.4">SYS.MONITOR</text>')
    o.append(f'<circle cx="962" cy="42" r="4.4" fill="{GR}" class="pulse"/>')
    o.append(f'<text x="952" y="46" font-size="10.5" fill="{GR}" text-anchor="end" letter-spacing="1.4">LIVE</text>')
    rows = [("USER", "KANHU_NAYAK", INK), ("HOST", "KCN_LAB", INK), ("ROLE", "UG · RESEARCHER", INK),
            ("MODE", "EXPLORATION", AM), ("CORE", "PHYSICS × COMPUTE", CY),
            ("LOOP", "LEARN→BUILD→EXPERIMENT", VI)]
    y = 78
    for k, v, col in rows:
        o.append(f'<text x="690" y="{y}" font-size="12" fill="{MUTED}" letter-spacing="1.2">{k}</text>')
        o.append(f'<text x="760" y="{y}" font-size="12" fill="{col}" font-weight="600">{v}</text>')
        y += 24
    # oscilloscope
    o.append(f'<rect x="686" y="232" width="284" height="126" rx="8" fill="{PANEL}" stroke="{LINE}"/>')
    pts = []
    for i in range(0, 289, 4):
        t = i / 4
        pts.append(f"{686 + i},{310 + 26 * math.sin(t * .55) * math.exp(-((t - 22) ** 2) / 90) + 10 * math.sin(t * 1.7)}")
    o.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{CY}" stroke-width="1.8" '
             f'stroke-opacity=".85" class="scope"/>')
    pts2 = [f"{686 + i},{318 + 16 * math.sin(i / 4 * .8 + 1.2)}" for i in range(0, 289, 4)]
    o.append(f'<polyline points="{" ".join(pts2)}" fill="none" stroke="{MG}" stroke-width="1.2" '
             f'stroke-opacity=".7"/>')
    for i in range(1, 6):
        o.append(f'<line x1="{686 + i * 47}" y1="232" x2="{686 + i * 47}" y2="358" stroke="{GRID}"/>')
    o.append(f'<line x1="686" y1="295" x2="970" y2="295" stroke="{GRID}"/>')
    o.append(f'<text x="694" y="252" font-size="10" fill="{MUTED}" letter-spacing="1.2">'
             f'ψ(x,t) :: curiosity.signal</text>')
    css = BASE_CSS
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="Boot terminal: physics active, AI/ML and deep learning learning, '
            f'quantum computing exploring, curiosity online — curiosity defined in binary terms">\n'
            f'<title>KCN_LAB :: TERMINAL</title>\n<style>{css}</style>\n{DEFS}\n'
            + "\n".join(o) + "\n</svg>\n")


# ──────────────────────────────── STATUS ──────────────────────────────────
def status() -> str:
    W, H = 1000, 340
    o = []
    o.append(frame(W, H))
    o.append(sparkles(5, 12, 20, 980, 20, 320, rmax=1.1))
    # left panel: module states
    o.append(f'<rect x="16" y="16" width="486" height="308" rx="14" fill="{PANEL}" stroke="{LINE}"/>')
    o.append(f'<text x="40" y="50" font-size="14.5" font-weight="700" fill="{INK}" letter-spacing="2">'
             f'<tspan fill="{CY}">◆</tspan> SYSTEM STATUS</text>')
    o.append(f'<text x="478" y="50" font-size="10.5" fill="{MUTED}" text-anchor="end" letter-spacing="1.4">'
             f'CORE MODULES · 08</text>')
    o.append(f'<line x1="40" y1="62" x2="478" y2="62" stroke="{LINE}"/>')
    mods = [("PHYSICS", "ACTIVE", GR), ("AI / ML", "LEARNING", BL), ("DEEP LEARNING", "LEARNING", BL),
            ("COMPUTER VISION", "EXPLORING", AM), ("QUANTUM COMPUTING", "EXPLORING", AM),
            ("SCIENTIFIC COMPUTING", "LEARNING", BL), ("OPEN SOURCE", "BUILDING", "#EA580C"),
            ("RESEARCH", "ONGOING", VI)]
    y = 84
    for i, (name, state, col) in enumerate(mods):
        o.append(f'<g class="rise" style="animation-delay:{i * .09:.2f}s">')
        o.append(f'<rect x="28" y="{y - 16}" width="462" height="30" rx="8" fill="{col}" '
                 f'fill-opacity=".05"/>')
        o.append(f'<rect x="28" y="{y - 16}" width="3" height="30" rx="1.5" fill="{col}"/>')
        o.append(f'<text x="44" y="{y + 4}" font-size="13" fill="{INK2}" letter-spacing=".6">{name}</text>')
        o.append(f'<rect x="330" y="{y - 11}" width="146" height="22" rx="11" fill="{col}" '
                 f'fill-opacity=".1" stroke="{col}" stroke-opacity=".5"/>')
        o.append(f'<circle cx="346" cy="{y}" r="6" fill="{col}" fill-opacity=".3" class="ring"/>')
        o.append(f'<circle cx="346" cy="{y}" r="3.2" fill="{col}"/>')
        o.append(f'<text x="404" y="{y + 4}" font-size="11" fill="{col}" text-anchor="middle" '
                 f'letter-spacing="1.5">{state}</text>')
        o.append('</g>')
        y += 30

    # right panel: focus index
    o.append(f'<rect x="514" y="16" width="470" height="308" rx="14" fill="{PANEL}" stroke="{LINE}"/>')
    o.append(f'<text x="538" y="50" font-size="14.5" font-weight="700" fill="{INK}" letter-spacing="2">'
             f'<tspan fill="{MG}">◆</tspan> FOCUS INDEX</text>')
    o.append(f'<text x="960" y="50" font-size="10.5" fill="{MUTED}" text-anchor="end" letter-spacing="1.4">'
             f'SELF-REPORTED · Q3</text>')
    o.append(f'<line x1="538" y1="62" x2="960" y2="62" stroke="{LINE}"/>')
    bars = [("PHYSICS", 92, CY), ("AI / ML", 78, BL), ("DEEP LEARNING", 70, VI),
            ("SCIENTIFIC COMPUTING", 64, GR), ("QUANTUM COMPUTING", 52, AM),
            ("OPEN SOURCE", 60, "#EA580C")]
    y = 96
    for i, (name, pct, col) in enumerate(bars):
        o.append(f'<g class="rise" style="animation-delay:{.3 + i * .1:.2f}s">')
        o.append(f'<text x="538" y="{y + 4}" font-size="12.5" fill="{INK2}">{name}</text>')
        o.append(f'<text x="960" y="{y + 4}" font-size="12" fill="{col}" text-anchor="end" '
                 f'font-weight="700">{pct}%</text>')
        o.append(f'<rect x="538" y="{y + 14}" width="422" height="10" rx="5" fill="{PANEL2}"/>')
        o.append(f'<g class="bar" style="animation-delay:{.4 + i * .1:.2f}s">'
                 f'<rect x="538" y="{y + 14}" width="{422 * pct / 100:.1f}" height="10" rx="5" '
                 f'fill="{col}" fill-opacity=".85"/></g>')
        o.append('</g>')
        y += 34
    o.append(f'<text x="538" y="{y + 6}" font-size="10.5" fill="{MUTED}" letter-spacing="1.2">'
             f'EXPLORATION VECTOR :: PHYSICS → MATHEMATICS → PROGRAMMING → AI/ML → RESEARCH</text>')
    css = BASE_CSS + f"""
  .ring {{ animation: ring 2s ease-out infinite; transform-box: fill-box; transform-origin: center; }}
  @keyframes ring {{ 0% {{ transform: scale(.6); opacity: .9 }} 100% {{ transform: scale(2.2); opacity: 0 }} }}
  .bar {{ animation: bar 1.6s cubic-bezier(.3,.9,.3,1) both; transform-box: fill-box; transform-origin: left center; }}
  @keyframes bar {{ from {{ transform: scaleX(0) }} }}
"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="System status: physics active; AI/ML, deep learning and scientific '
            f'computing learning; computer vision and quantum computing exploring; open source building; '
            f'research ongoing">\n<title>KCN_LAB :: SYSTEM STATUS</title>\n<style>{css}</style>\n{DEFS}\n'
            + "\n".join(o) + "\n</svg>\n")


# ──────────────────────────────── FOCUS ───────────────────────────────────
def focus() -> str:
    W, H = 1000, 210
    o = []
    o.append(frame(W, H))
    o.append(sparkles(9, 16, 20, 980, 16, 190, rmax=1.2))
    o.append(f'<text x="30" y="44" font-size="14.5" font-weight="700" fill="{INK}" letter-spacing="2">'
             f'<tspan fill="{BL}">◆</tspan> CURRENT FOCUS</text>')
    o.append(f'<text x="970" y="44" font-size="10.5" fill="{MUTED}" text-anchor="end" letter-spacing="1.4">'
             f'ACTIVE PROTOCOLS · 06</text>')
    o.append(f'<line x1="30" y1="56" x2="970" y2="56" stroke="{LINE}"/>')
    items = [("DEEP LEARNING", "neural nets · training loops", VI, "net"),
             ("COMPUTER VISION", "detection · segmentation", CY, "eye"),
             ("SCIENTIFIC COMPUTING", "numerical · simulation", BL, "wave"),
             ("QUANTUM COMPUTING", "qubits · circuits", MG, "atom"),
             ("FULL STACK", "interfaces · APIs", GR, "layers"),
             ("RESEARCH", "reading · experimenting", AM, "search")]
    x, y = 30, 78
    for i, (name, sub, col, ic) in enumerate(items):
        cx0 = x + (i % 3) * 320
        cy0 = y + (i // 3) * 62
        o.append(f'<g class="rise" style="animation-delay:{i * .1:.2f}s">')
        o.append(f'<rect x="{cx0}" y="{cy0}" width="300" height="52" rx="12" fill="{PANEL}" '
                 f'stroke="{col}" stroke-opacity=".45"/>')
        o.append(f'<circle cx="{cx0 + 30}" cy="{cy0 + 26}" r="17" fill="{col}" fill-opacity=".1"/>')
        o.append(f'<circle cx="{cx0 + 30}" cy="{cy0 + 26}" r="17" fill="none" stroke="{col}" '
                 f'stroke-opacity=".5" stroke-width="1.2" stroke-dasharray="4 5" class="spin"/>')
        o.append(glyph(ic, cx0 + 30, cy0 + 26, col, 19, 1.7))
        o.append(f'<text x="{cx0 + 58}" y="{cy0 + 22}" font-size="12.5" font-weight="700" fill="{INK}" '
                 f'letter-spacing=".8">{name}</text>')
        o.append(f'<text x="{cx0 + 58}" y="{cy0 + 40}" font-size="10.5" fill="{MUTED}" '
                 f'letter-spacing=".8">{sub}</text>')
        o.append('</g>')
    css = BASE_CSS
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="Current focus: deep learning, computer vision, scientific computing, '
            f'quantum computing, full stack, research">\n<title>KCN_LAB :: CURRENT FOCUS</title>\n'
            f'<style>{css}</style>\n{DEFS}\n' + "\n".join(o) + "\n</svg>\n")


# ──────────────────────────────── JOURNEY ─────────────────────────────────
def journey() -> str:
    W, H = 1000, 300
    o = []
    o.append(frame(W, H))
    o.append(sparkles(13, 14, 20, 980, 16, 280, rmax=1.2))
    o.append(f'<text x="30" y="42" font-size="14.5" font-weight="700" fill="{INK}" letter-spacing="2">'
             f'<tspan fill="{GR}">◆</tspan> JOURNEY</text>')
    o.append(f'<text x="970" y="42" font-size="10.5" fill="{MUTED}" text-anchor="end" letter-spacing="1.4">'
             f'LOOP :: ∞</text>')
    o.append(f'<line x1="30" y1="54" x2="970" y2="54" stroke="{LINE}"/>')

    stages = ["PHYSICS", "MATHEMATICS", "PROGRAMMING", "AI / ML", "DEEP LEARNING",
              "SCIENTIFIC COMPUTING", "RESEARCH"]
    cols = [CY, BL, VI, MG, "#EA580C", GR, AM]
    y = 100
    n = len(stages)
    seg = 940 / n
    for i, (name, col) in enumerate(zip(stages, cols)):
        x = 30 + i * seg
        o.append(f'<g class="rise" style="animation-delay:{i * .12:.2f}s">')
        o.append(f'<rect x="{x:.1f}" y="{y - 24}" width="{seg - 12:.1f}" height="48" rx="10" '
                 f'fill="{PANEL}" stroke="{col}" stroke-opacity=".5"/>')
        o.append(f'<text x="{x + (seg - 12) / 2:.1f}" y="{y - 4}" font-size="10" fill="{MUTED}" '
                 f'text-anchor="middle" letter-spacing="1.6">[0{i + 1}]</text>')
        o.append(f'<text x="{x + (seg - 12) / 2:.1f}" y="{y + 16}" font-size="11.5" fill="{INK}" '
                 f'text-anchor="middle" letter-spacing=".8" font-weight="600">{name}</text>')
        o.append('</g>')
        if i < n - 1:
            ax = x + seg - 6
            o.append(f'<path d="M{ax},{y} l7,-5 v10 z" fill="{cols[i + 1]}" fill-opacity=".7"/>')

    # loop band
    o.append(f'<rect x="60" y="168" width="880" height="72" rx="36" fill="{PANEL2}" '
             f'stroke="url(#holo)" stroke-opacity=".6" stroke-width="1.5"/>')
    o.append(f'<rect x="60" y="168" width="880" height="72" rx="36" fill="none" stroke="#FFFFFF" '
             f'stroke-width="2.4" stroke-dasharray="70 1200" class="orbit" filter="url(#glow)"/>')
    for i, (label, col) in enumerate([("EXPLORE", CY), ("BUILD", GR), ("EXPERIMENT", AM), ("REPEAT", MG)]):
        x = 118 + i * 216
        o.append(f'<rect x="{x}" y="191" width="128" height="26" rx="13" fill="{PANEL}" stroke="{col}" '
                 f'stroke-width="1.4" class="rise" style="animation-delay:{.4 + i * .12:.2f}s"/>')
        o.append(f'<text x="{x + 64}" y="{208}" font-size="11.5" fill="{col}" text-anchor="middle" '
                 f'letter-spacing="1.6">{label}</text>')
    o.append(f'<circle r="5" fill="#FFFFFF" filter="url(#glow)">'
             f'<animateMotion dur="9s" repeatCount="indefinite" '
             f'path="M60,204 H940 A36,36 0 0 1 904,240 H96 A36,36 0 0 1 60,204 Z"/></circle>')
    o.append(f'<text x="500" y="276" font-size="19" font-weight="800" fill="url(#holo)" '
             f'text-anchor="middle" letter-spacing="5">KCN_LAB</text>')
    o.append(f'<text x="30" y="276" font-size="10.5" fill="{MUTED}" letter-spacing="1.4">'
             f'STATUS <tspan fill="{GR}">IN PROGRESS</tspan><tspan class="blink" fill="{GR}">_</tspan></text>')
    o.append(f'<text x="970" y="276" font-size="10.5" fill="{MUTED}" text-anchor="end" letter-spacing="1.4">'
             f'THINKING PROTOCOL :: DEEP + SYSTEMATIC</text>')
    css = BASE_CSS + f"""
  .orbit {{ animation: orbit 8s linear infinite; }}
  @keyframes orbit {{ to {{ stroke-dashoffset: -1270 }} }}
"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="Journey: physics, mathematics, programming, AI/ML, deep learning, '
            f'scientific computing, research — looping through explore, build, experiment, repeat">\n'
            f'<title>KCN_LAB :: JOURNEY</title>\n<style>{css}</style>\n{DEFS}\n'
            + "\n".join(o) + "\n</svg>\n")


# ─────────────────────── REGISTRY (projects / research) ───────────────────
def registry() -> str:
    """PROJECT DATABASE + RESEARCH CORE — deliberately sealed / ongoing, no names."""
    W, H = 1000, 250
    o = []
    o.append(frame(W, H))
    o.append(sparkles(21, 10, 20, 980, 16, 230, rmax=1.1))

    def panel(x, title, icon_col, tag, note):
        s = []
        s.append(f'<rect x="{x}" y="16" width="470" height="218" rx="14" fill="{PANEL}" '
                 f'stroke="{LINE}"/>')
        s.append(f'<rect x="{x}" y="16" width="470" height="3" rx="1.5" fill="url(#holo)"/>')
        s.append(f'<text x="{x + 24}" y="50" font-size="14" font-weight="700" fill="{INK}" '
                 f'letter-spacing="2">{title}</text>')
        s.append(f'<text x="{x + 446}" y="50" font-size="10.5" fill="{MUTED}" text-anchor="end" '
                 f'letter-spacing="1.4">{tag}</text>')
        s.append(f'<line x1="{x + 24}" y1="62" x2="{x + 446}" y2="62" stroke="{LINE}"/>')
        # sealed lock
        s.append(f'<rect x="{x + 24}" y="82" width="422" height="58" rx="10" fill="{PANEL2}" '
                 f'stroke="{icon_col}" stroke-opacity=".35" stroke-dasharray="6 5"/>')
        s.append(f'<circle cx="{x + 56}" cy="111" r="15" fill="{icon_col}" fill-opacity=".12"/>')
        s.append(f'<rect x="{x + 48}" y="108" width="16" height="13" rx="3" fill="none" '
                 f'stroke="{icon_col}" stroke-width="1.8"/>')
        s.append(f'<path d="M{x + 51},108 v-6 a5,5 0 0 1 10,0 v6" fill="none" stroke="{icon_col}" '
                 f'stroke-width="1.8"/>')
        s.append(f'<text x="{x + 84}" y="106" font-size="12.5" font-weight="700" fill="{INK}" '
                 f'letter-spacing="1.2">{tag}</text>')
        s.append(f'<text x="{x + 84}" y="124" font-size="10.5" fill="{MUTED}" letter-spacing=".8">'
                 f'{note}</text>')
        # empty placeholder rows
        for i in range(3):
            ry = 158 + i * 22
            s.append(f'<g class="rise" style="animation-delay:{.5 + i * .14:.2f}s">')
            s.append(f'<rect x="{x + 24}" y="{ry}" width="422" height="16" rx="8" fill="{PANEL2}"/>')
            s.append(f'<rect x="{x + 30}" y="{ry + 4}" width="8" height="8" rx="2" fill="{icon_col}" '
                     f'fill-opacity=".45"/>')
            s.append(f'<rect x="{x + 46}" y="{ry + 5}" width="{150 - i * 26}" height="6" rx="3" '
                     f'fill="{LINE}"/>')
            s.append(f'<rect x="{x + 330}" y="{ry + 5}" width="46" height="6" rx="3" fill="{LINE}"/>')
            s.append(f'<text x="{x + 396}" y="{ry + 11}" font-size="9.5" fill="{MUTED}" '
                     f'letter-spacing="1.2">— —</text>')
            s.append('</g>')
        s.append(f'<text x="{x + 24}" y="{16 + 206}" font-size="10" fill="{MUTED}" letter-spacing="1.4">'
                 f'kcn@lab:~/registry ▸ <tspan class="blink" fill="{icon_col}">awaiting entries_</tspan></text>')
        return "".join(s)

    o.append(panel(16, "◈ PROJECT DATABASE", VI, "STATUS · ONGOING",
                   "entries are being prepared — nothing public yet"))
    o.append(panel(514, "◈ RESEARCH CORE", MG, "STATUS · SEALED",
                   "work in progress — released when it is ready"))
    css = BASE_CSS
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="Project database status ongoing and research core status sealed — '
            f'no public entries yet, entries pending">\n<title>KCN_LAB :: PROJECT / RESEARCH REGISTRY</title>\n'
            f'<style>{css}</style>\n{DEFS}\n' + "\n".join(o) + "\n</svg>\n")


# ──────────────────────────────── FOOTER ──────────────────────────────────
def footer() -> str:
    W, H = 1000, 180
    o = []
    o.append(frame(W, H, top_strip=False))
    o.append(sparkles(31, 12, 20, 980, 14, 160, rmax=1.1))
    o.append(f'<text x="500" y="36" font-size="11" fill="{MUTED}" text-anchor="middle" '
             f'letter-spacing="4">// END OF TRANSMISSION · KCN_LAB</text>')
    for i, (label, col) in enumerate([("KEEP LEARNING", CY), ("KEEP BUILDING", VI), ("KEEP EXPLORING", MG)]):
        o.append(f'<text x="{250 + i * 250}" y="76" font-size="19" font-weight="700" fill="{col}" '
                 f'text-anchor="middle" letter-spacing="3" class="w" '
                 f'style="animation-delay:{i * 1.2:.1f}s">{label}</text>')
    o.append(f'<circle cx="375" cy="69" r="3" fill="{LINE}"/>')
    o.append(f'<circle cx="625" cy="69" r="3" fill="{LINE}"/>')
    o.append(f'<text x="500" y="118" font-size="22" font-weight="800" fill="url(#holo)" '
             f'text-anchor="middle" letter-spacing="1.5">Curiosity Today → Innovation Tomorrow</text>')
    # travelling wave
    pts = []
    for i in range(0, 2001, 5):
        x = i / 2
        y = 152 + 9 * math.sin(i / 22.0)
        pts.append(f"{x:.1f},{y:.1f}")
    o.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="url(#holo)" stroke-width="1.6" '
             f'stroke-opacity=".8" class="wave"/>')
    o.append(f'<text x="500" y="172" font-size="10" fill="{MUTED}" text-anchor="middle" '
             f'letter-spacing="2">kcn@lab:~$ exit 0<tspan class="blink" fill="{CY}"> █</tspan></text>')
    css = BASE_CSS + f"""
  .w {{ animation: w 3.6s ease-in-out infinite; }}
  @keyframes w {{ 0%,100% {{ opacity: .35 }} 15% {{ opacity: 1 }} 40% {{ opacity: .35 }} }}
  .tw {{ animation: tw 4s ease-in-out infinite; }}
  @keyframes tw {{ 0%,100% {{ opacity: .12 }} 50% {{ opacity: 1 }} }}
  .wave {{ animation: wave 7s linear infinite; }}
  @keyframes wave {{ to {{ transform: translateX(-40px) }} }}
"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="Keep learning, keep building, keep exploring — curiosity today, '
            f'innovation tomorrow">\n<title>KCN_LAB :: END OF TRANSMISSION</title>\n'
            f'<style>{css}</style>\n{DEFS}\n' + "\n".join(o) + "\n</svg>\n")


# ───────────────────── avatar.png (pure-python PNG writer) ────────────────
def write_avatar_png(size: int = 512, path: str | None = None) -> str:
    """Rasterise the identity sigil (light theme) without any third-party lib."""
    path = path or os.path.join(OUT, "avatar.png")
    SS = 2                                   # supersampling factor
    N = size * SS
    c = N / 2.0

    def holo(t: float):
        stops = [(0.0, (34, 211, 238)), (0.38, (96, 165, 250)), (0.68, (167, 139, 250)), (1.0, (244, 114, 182))]
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if t <= b:
                k = (t - a) / (b - a)
                return tuple(int(x + (y - x) * k) for x, y in zip(ca, cb))
        return stops[-1][1]

    # letter strokes, normalised (0..1) inside the core disc
    def glyph(x: float, y: float) -> bool:
        """True when (x, y) in [0,1]^2 is inside a KCN monogram stroke."""
        w = 0.052                               # stroke half-width
        # K
        if 0.085 <= x <= 0.085 + w and 0.28 <= y <= 0.72:
            return True
        for (ax, ay), (bx, by) in (((0.085, 0.50), (0.30, 0.28)), ((0.085, 0.50), (0.30, 0.72))):
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = max(0.0, min(1.0, (x - ax) * dx + (y - ay) * dy) / L2 if L2 else 0)
            if (x - (ax + t * dx)) ** 2 + (y - (ay + t * dy)) ** 2 < w * w:
                return True
        # C  (arc, centre .46,.50, r .115, opening to the right)
        cx, cy, r = 0.460, 0.500, 0.118
        d = math.hypot(x - cx, y - cy)
        ang = math.degrees(math.atan2(y - cy, x - cx)) % 360
        if abs(d - r) < w and 42 <= ang <= 318:
            return True
        # N
        if 0.600 <= x <= 0.600 + w and 0.28 <= y <= 0.72:
            return True
        if 0.828 <= x <= 0.828 + w and 0.28 <= y <= 0.72:
            return True
        for (ax, ay), (bx, by) in (((0.600, 0.72), (0.828, 0.28)),):
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = max(0.0, min(1.0, (x - ax) * dx + (y - ay) * dy) / L2 if L2 else 0)
            if (x - (ax + t * dx)) ** 2 + (y - (ay + t * dy)) ** 2 < w * w:
                return True
        return False

    px = bytearray()
    acc = [[0.0, 0.0, 0.0] for _ in range(size * size)]
    for j in range(N):
        y = (j + 0.5) / N
        for i in range(N):
            x = (i + 0.5) / N
            dx, dy = x - 0.5, y - 0.5
            dist = math.hypot(dx, dy)
            # background: soft radial paper
            k = min(1.0, dist / 0.72)
            col = [255 - 26 * k, 253 - 22 * k, 255 - 12 * k]
            # holographic sheen band
            if 0.30 < (x * 0.6 + y * 0.8) % 1.0 < 0.40:
                for ch in range(3):
                    col[ch] += 26
            # outer holo ring
            if 0.385 < dist < 0.405:
                ang = (math.degrees(math.atan2(dy, dx)) + 180) / 360.0
                hc = holo(ang)
                for ch in range(3):
                    col[ch] = col[ch] * 0.25 + hc[ch] * 0.75
            # hexagon frame
            if 0.355 < dist < 0.372:
                ax = abs(dx) * 1.1547
                if ax + abs(dy) * 0.999 < 0.372:
                    hc = holo((math.degrees(math.atan2(dy, dx)) + 180) / 360.0)
                    for ch in range(3):
                        col[ch] = col[ch] * 0.35 + hc[ch] * 0.65
            # orbits
            for rot in (0.0, 1.0472, 2.0944):
                ux = dx * math.cos(-rot) - dy * math.sin(-rot)
                uy = dx * math.sin(-rot) + dy * math.cos(-rot)
                if abs((ux / 0.315) ** 2 + (uy / 0.115) ** 2 - 1.0) < 0.020:
                    for ch in range(3):
                        col[ch] = col[ch] * 0.55 + (120, 139, 250)[ch] * 0.45
            # core disc
            if dist < 0.175:
                for ch in range(3):
                    col[ch] = 255
                if dist > 0.168:
                    hc = holo((math.degrees(math.atan2(dy, dx)) + 180) / 360.0)
                    for ch in range(3):
                        col[ch] = col[ch] * 0.3 + hc[ch] * 0.7
                # monogram
                gx = (dx / 0.175) * 0.5 + 0.5
                gy = (dy / 0.175) * 0.5 + 0.5
                if glyph(gx, gy):
                    col = [11, 18, 32]
            idx = (j // SS) * size + (i // SS)
            for ch in range(3):
                acc[idx][ch] += max(0, min(255, col[ch]))

    tot = SS * SS
    for cell in acc:
        px.extend(int(v / tot + 0.5) for v in cell)

    raw = b"".join(b"\x00" + bytes(px[r * size * 3:(r + 1) * size * 3]) for r in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return path


# ───────────────────────────────── MAIN ───────────────────────────────────
# ─────────────────────── TECH-STACK TILES (one per tech) ───────────────────
# One small self-contained animated SVG per technology.  Each tile is a real
# <img> in README.md, so it can be wrapped in an <a href="official docs"> --
# links embedded *inside* an SVG are dead when GitHub serves it through camo,
# but a whole tile inside an <a> is a normal clickable image.
TECH_DIR = os.path.join(OUT, "tech")

# category -> [(icon_data key, label), ...]
TECH_GROUPS = [
    ("LANGUAGES", [("python", "PYTHON"), ("c", "C"), ("javascript", "JAVASCRIPT"),
                   ("typescript", "TYPESCRIPT"), ("html5", "HTML5"), ("css3", "CSS3")]),
    ("MACHINE LEARNING", [("pytorch", "PYTORCH"), ("tensorflow", "TENSORFLOW"),
                          ("scikit-learn", "SCIKIT-LEARN"), ("opencv", "OPENCV"),
                          ("hugging-face", "HUGGING FACE")]),
    ("DATA / SCIENTIFIC", [("numpy", "NUMPY"), ("pandas", "PANDAS"),
                           ("matplotlib", "MATPLOTLIB"), ("scipy", "SCIPY"),
                           ("jupyter", "JUPYTER"), ("anaconda", "ANACONDA")]),
    ("QUANTUM / WRITING", [("qiskit", "QISKIT"), ("latex", "LATEX"), ("arxiv", "ARXIV")]),
    ("TOOLS / ENVIRONMENT", [("git", "GIT"), ("linux", "LINUX"), ("bash", "BASH"),
                             ("docker", "DOCKER"), ("vs-code", "VS CODE")]),
    ("WEB / VERSION HOST", [("react", "REACT"), ("next-js", "NEXT.JS"), ("github", "GITHUB")]),
]


def load_icons() -> dict:
    with open(os.path.join(ROOT, "scripts", "icon_data.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _srgb(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexc: str) -> float:
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def readable(hexc: str, min_ratio: float = 3.6, target: str = "#FFFFFF") -> str:
    """Darken a brand colour until it reads well on a light tile."""
    out = []
    for i in range(1, len(hexc) - 1, 2):
        out.append(int(hexc[i:i + 2], 16))
    bg = [_lum(target)] * 3
    while True:
        fg = [_lum("#%02X%02X%02X" % tuple(out))]
        ratio = (max(fg[0], bg[0]) + .05) / (min(fg[0], bg[0]) + .05)
        if ratio >= min_ratio or all(v == 0 for v in out):
            return "#%02X%02X%02X" % tuple(out)
        out = [max(0, int(round(v * .92))) for v in out]


TILE_CSS = """
  text {{ font-family: {FONT}; }}
  .in {{ animation: rise .75s cubic-bezier(.2,.85,.25,1) both; }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(16px) scale(.94) }}
                    to   {{ opacity: 1; transform: none }} }}
  .fl {{ animation: float 7.5s ease-in-out infinite; }}
  @keyframes float {{ 0%,100% {{ transform: translateY(0) }} 50% {{ transform: translateY(-2.6px) }} }}
  .tile {{ transition: transform .38s cubic-bezier(.2,.85,.25,1); transform-origin: 74px 69px; }}
  .tile:hover {{ transform: translateY(-6px) scale(1.035); }}
  .card {{ stroke: {LINE}; stroke-width: 1.4; transition: stroke .32s ease; }}
  .tile:hover .card {{ stroke: {C}; stroke-width: 1.8; }}
  .bar {{ transform: scaleX(.3); transform-origin: 6px 13.8px;
          transition: transform .5s cubic-bezier(.2,.85,.25,1); }}
  .tile:hover .bar {{ transform: scaleX(1); }}
  .glow {{ opacity: 0; transition: opacity .35s ease; }}
  .tile:hover .glow {{ opacity: .5; }}
  .ring {{ opacity: 0; transition: opacity .35s ease; transform-origin: 74px 58px;
           animation: spin 14s linear infinite; animation-play-state: paused; }}
  .tile:hover .ring {{ opacity: .95; animation-play-state: running; }}
  .icon {{ transition: transform .38s cubic-bezier(.2,.85,.25,1); transform-origin: 74px 58px; }}
  .tile:hover .icon {{ transform: scale(1.12); }}
  .lbl {{ transition: fill .32s ease; }}
  .tile:hover .lbl {{ fill: {C}; }}
  .hint {{ opacity: 0; transition: opacity .35s ease; }}
  .tile:hover .hint {{ opacity: 1; }}
  .sheen {{ opacity: 0; }}
  .tile:hover .sheen {{ animation: sheen .95s linear infinite; }}
  @keyframes sheen {{ 0% {{ transform: translateX(-70px) }} 100% {{ transform: translateX(150px) }} }}
  .tick {{ animation: pulse 2.6s ease-in-out infinite; }}
""".format(FONT=FONT, LINE=LINE, C=CY)


def tech_tile(key: str, label: str, icon: dict, delay: float) -> str:
    """148x132 tile: rounded light card, brand icon, hover-reveal ring + docs hint."""
    c = readable(icon["color"])
    vb = icon["vb"]
    try:
        _, _, vw, vh = [float(v) for v in vb.split()]
    except ValueError:
        vw, vh = 24.0, 24.0
    box, cx, cy = 44.0, 74.0, 58.0
    k = box / max(vw, vh)
    iw, ih = vw * k, vh * k
    inner = icon["inner"]
    if "fill=" not in inner:
        inner = inner.replace("<path ", '<path fill="%s" ' % c, 1)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 148 132" width="148" height="132"
     role="img" aria-label="{label}">
<title>{label}</title>
<style>{TILE_CSS}</style>
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#F4F8FE"/></linearGradient>
  <radialGradient id="gl" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="{c}" stop-opacity=".38"/>
    <stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>
  <linearGradient id="sh" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>
    <stop offset=".5" stop-color="#FFFFFF" stop-opacity=".9"/>
    <stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
</defs>
<g class="in" transform="translate(0 0)" style="animation-delay:{delay:.2f}s">
<g class="fl" transform="translate(0 0)" style="animation-delay:-{delay * 1.9:.2f}s">
<g class="tile">
  <rect class="card" x="6" y="12" width="136" height="114" rx="15" fill="url(#bg)"/>
  <rect class="bar" x="6" y="12" width="136" height="3.6" rx="1.8" fill="{c}"/>
  <circle class="glow" cx="{cx}" cy="{cy}" r="40" fill="url(#gl)"/>
  <circle class="ring" cx="{cx}" cy="{cy}" r="29" fill="none" stroke="{c}" stroke-width="1.2"
          stroke-dasharray="5 6" stroke-opacity=".75"/>
  <g class="icon" transform="translate({cx - iw / 2:.2f} {cy - ih / 2:.2f}) scale({k:.5f})">
    <g transform="translate({-float(vb.split()[0]):.1f} {-float(vb.split()[1]):.1f})">{inner}</g>
  </g>
  <text class="lbl" x="{cx}" y="98" font-size="11" fill="{INK2}" text-anchor="middle"
        letter-spacing=".7" font-weight="600">{label}</text>
  <text class="hint" x="{cx}" y="114" font-size="7" fill="{c}" text-anchor="middle"
        letter-spacing="1.6">OPEN DOCS &#8599;</text>
  <path class="sheen" d="M6 27 L20 12 L34 12 L20 27 Z" fill="url(#sh)"/>
  <circle class="tick" cx="18" cy="22" r="1.7" fill="{c}" style="animation-delay:-{delay:.2f}s"/>
</g></g></g>
</svg>
"""


def techstack() -> int:
    icons = load_icons()
    os.makedirs(TECH_DIR, exist_ok=True)
    manifest = []
    n = 0
    for cat, items in TECH_GROUPS:
        for key, label in items:
            icon = icons[key]
            svg = tech_tile(key, label, icon, delay=(n % 7) * .09 + (n // 7) * .12)
            with open(os.path.join(TECH_DIR, key + ".svg"), "w", encoding="utf-8") as fh:
                fh.write(svg)
            manifest.append({"key": key, "label": label, "category": cat,
                             "docs": icon["docs"], "color": icon["color"],
                             "file": "assets/tech/%s.svg" % key})
            n += 1
    with open(os.path.join(TECH_DIR, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"wrote assets/tech/*.svg ({n} tiles, "
          f"{sum(os.path.getsize(os.path.join(TECH_DIR, k + '.svg')) for k in icons) / 1024:.1f} KB)")
    return n


BUILDERS = {
    "hero.svg": hero,
    "avatar.svg": avatar_svg,
    "divider.svg": divider,
    "terminal.svg": terminal,
    "status.svg": status,
    "focus.svg": focus,
    "journey.svg": journey,
    "registry.svg": registry,
    "footer.svg": footer,
}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    for name, fn in BUILDERS.items():
        svg = fn()
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"wrote assets/{name} ({len(svg) / 1024:.1f} KB)")
    techstack()
    p = write_avatar_png()
    print(f"wrote {os.path.relpath(p, ROOT)} ({os.path.getsize(p) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
