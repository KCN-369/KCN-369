#!/usr/bin/env python3
"""
KCN_LAB :: profile card generator  (LIGHT THEME · futuristic)
=============================================================

Builds the live SVG cards used in README.md from real GitHub data:

  profile/stats.svg      GitHub telemetry  (tiles + LEVEL ring + XP + stats)
  profile/top-langs.svg  Top languages card (animated share bars)
  profile/contrib3d.svg  3D isometric contribution graph
                         · multi-colour pillars, one cube per day
                         · hover the angle chips at the bottom to ROTATE the scene
  profile/flow.svg       Animated "aurora flow" contribution graph
                         · weekly waveform + 53x7 day heat grid + streak telemetry
  docs/data/contrib.json payload for the interactive 3D viewer (GitHub Pages)

Standard library only — no pip install needed.

Usage
-----
  GITHUB_TOKEN=... python3 scripts/profile_cards.py --user KCN-369 --out profile
  python3 scripts/profile_cards.py --user KCN-369 --out profile --demo   # offline preview

Tweak the look in the CONFIG section below (palette, XP weights, rank names).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import sys
import urllib.request

# ───────────────────────────────── CONFIG ─────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT = ("'JetBrains Mono','Fira Code','SF Mono',SFMono-Regular,ui-monospace,"
        "Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace")
SANS = "'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif"

# ---- light "photon lab" palette -------------------------------------------
PAPER = "#F4F8FE"   # card background
PANEL = "#FFFFFF"   # inner panel
PANEL2 = "#EDF3FB"  # inner panel (secondary)
INK = "#0B1220"     # primary text
INK2 = "#3D4B63"    # secondary text
MUTED = "#7C8CA6"   # labels
LINE = "#D8E4F4"    # hairlines
GRID = "#E4ECF7"

CY, BL, VI, MG, GR, AM = "#0E7490", "#2563EB", "#7C3AED", "#DB2777", "#047857", "#B45309"
# bright variants — used for shapes / gradients where contrast is not an issue
CY_L, BL_L, VI_L, MG_L, GR_L, AM_L = "#22D3EE", "#60A5FA", "#A78BFA", "#F472B6", "#34D399", "#FBBF24"

# XP awarded per unit of activity
XP_WEIGHTS = {
    "contributions": 1, "commits": 2, "prs": 8, "issues": 4,
    "stars": 10, "repos": 15, "followers": 5,
}
XP_CURVE = 25  # total XP needed for level L is XP_CURVE * L^2

RANKS = [  # (min level, title, colour)
    (0, "INITIATE", MUTED),
    (5, "APPRENTICE", BL),
    (10, "BUILDER", CY),
    (20, "RESEARCHER", VI),
    (35, "ARCHITECT", MG),
    (50, "QUANTUM SAGE", AM),
]

# holographic ramp for the 3D pillars / waveform (cyan → indigo → violet → pink → rose)
RAMP = [(0.00, (34, 211, 238)), (0.22, (56, 189, 248)), (0.45, (129, 140, 248)),
        (0.65, (167, 139, 250)), (0.82, (232, 121, 249)), (1.00, (251, 113, 133))]
# heat-grid ramp (level 1..4)
LEVEL_COLORS = ["#BAE6FD", "#7DD3FC", "#818CF8", "#C084FC", "#F472B6"]
EMPTY_CELL = "#E7EEF8"

LANG_FALLBACK = [CY_L, VI_L, MG_L, GR_L, AM_L, BL_L, "#F97316", "#14B8A6"]

GH_MARK = ("M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04"
           "-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838"
           " 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93"
           " 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02"
           ".006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0"
           " 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565"
           " 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12")

# ───────────────────────────────── DATA ───────────────────────────────────
API = "https://api.github.com/graphql"

Q_MAIN = """
query($login: String!) {
  user(login: $login) {
    login name createdAt avatarUrl
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes { stargazerCount forkCount
        languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } } } }
    }
    contributionsCollection {
      contributionYears
      contributionCalendar { totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } } }
    }
  }
}
"""

LEVEL_ENUM = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
              "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def gql(token: str, query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "kcn-lab-profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]


def fetch(login: str, token: str) -> dict:
    u = gql(token, Q_MAIN, {"login": login})["user"]
    if u is None:
        raise RuntimeError(f"user {login!r} not found")

    years = sorted(u["contributionsCollection"]["contributionYears"])
    per_year, calendars = {}, {}
    if years:
        parts = [f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", '
                 f'to: "{y}-12-31T23:59:59Z") {{ totalCommitContributions '
                 f'restrictedContributionsCount contributionCalendar {{ totalContributions '
                 f'weeks {{ contributionDays {{ date contributionCount contributionLevel weekday }} }} }} }}'
                 for y in years]
        q = "query($login: String!) { user(login: $login) { " + " ".join(parts) + " } }"
        yd = gql(token, q, {"login": login})["user"]
        for y in years:
            c = yd[f"y{y}"]
            per_year[y] = {"total": c["contributionCalendar"]["totalContributions"],
                           "commits": c["totalCommitContributions"]}
            calendars[y] = [[{"date": d["date"], "count": d["contributionCount"],
                              "level": LEVEL_ENUM.get(d["contributionLevel"], 0),
                              "weekday": d["weekday"]} for d in w["contributionDays"]]
                             for w in c["contributionCalendar"]["weeks"]]

    langs: dict[str, list] = {}
    stars = forks = 0
    for n in u["repositories"]["nodes"]:
        stars += n["stargazerCount"]
        forks += n["forkCount"]
        for e in n["languages"]["edges"]:
            name, color = e["node"]["name"], e["node"]["color"]
            langs.setdefault(name, [color, 0])[1] += e["size"]

    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = [[{"date": d["date"], "count": d["contributionCount"],
               "level": LEVEL_ENUM.get(d["contributionLevel"], 0), "weekday": d["weekday"]}
              for d in w["contributionDays"]] for w in cal["weeks"]]

    this_year = dt.date.today().year
    return {
        "login": u["login"], "name": u["name"] or u["login"], "avatar": u.get("avatarUrl"),
        "created_at": u["createdAt"][:10],
        "repos": u["repositories"]["totalCount"], "stars": stars, "forks": forks,
        "followers": u["followers"]["totalCount"],
        "prs": u["pullRequests"]["totalCount"], "issues": u["issues"]["totalCount"],
        "years": per_year, "year": this_year,
        "commits_year": per_year.get(this_year, {}).get("commits", 0),
        "commits_all": sum(v["commits"] for v in per_year.values()),
        "contrib_all": sum(v["total"] for v in per_year.values()),
        "calendar": weeks, "total_last_year": cal["totalContributions"],
        "languages": sorted(((k, v[0], v[1]) for k, v in langs.items()), key=lambda t: -t[2]),
        "calendars": calendars,
        "demo": False,
    }


def demo(login: str) -> dict:
    """Plausible offline data — only for local previews (clearly tagged on the cards)."""
    rnd = random.Random(369)
    today = dt.date.today()
    start = today - dt.timedelta(days=today.isoweekday() % 7 + 52 * 7)
    weeks, day, total = [], start, 0
    while day <= today:
        wk = []
        for _ in range(7):
            if day > today:
                break
            ramp = 0.35 + 0.65 * ((day - start).days / 371)
            burst = 1.0 + 1.6 * math.sin((day - start).days / 23.0) ** 2
            c = 0 if rnd.random() > 0.9 * ramp else 1 + int(rnd.expovariate(0.32) * burst)
            wk.append({"date": day.isoformat(), "count": c, "weekday": (day.isoweekday() % 7)})
            total += c
            day += dt.timedelta(days=1)
        weeks.append(wk)
    nz = sorted(d["count"] for w in weeks for d in w if d["count"])
    q = [nz[int(len(nz) * f)] for f in (.25, .5, .75)] if nz else [1, 2, 3]
    for w in weeks:  # quartile levels, like GitHub
        for d in w:
            c = d["count"]
            d["level"] = 0 if c == 0 else 1 + sum(c > t for t in q)
    prev_year = today.year - 1
    # build a second (previous) year of calendar data for the interactive viewer
    rnd2 = random.Random(3691)
    start2 = dt.date(prev_year, 1, 1)
    start2 -= dt.timedelta(days=start2.isoweekday() % 7)
    weeks2, day2, total2 = [], start2, 0
    while day2.year <= prev_year:
        wk = []
        for _ in range(7):
            if day2.year > prev_year:
                break
            ramp = 0.3 + 0.7 * ((day2 - start2).days / 365)
            c = 0 if rnd2.random() > 0.82 * ramp else 1 + int(rnd2.expovariate(0.4))
            wk.append({"date": day2.isoformat(), "count": c, "weekday": (day2.isoweekday() % 7)})
            total2 += c
            day2 += dt.timedelta(days=1)
        weeks2.append(wk)
    nz2 = sorted(d["count"] for w in weeks2 for d in w if d["count"])
    q2 = [nz2[int(len(nz2) * f)] for f in (.25, .5, .75)] if nz2 else [1, 2, 3]
    for w in weeks2:
        for d in w:
            c = d["count"]
            d["level"] = 0 if c == 0 else 1 + sum(c > t for t in q2)
    return {
        "login": login, "name": login, "avatar": None, "created_at": "2025-05-19",
        "repos": 14, "stars": 37, "forks": 6, "followers": 6, "prs": 23, "issues": 11,
        "years": {prev_year: {"total": total2, "commits": int(total2 * .7)},
                  today.year: {"total": total, "commits": int(total * .72)}},
        "year": today.year, "commits_year": int(total * .72),
        "commits_all": int(total2 * .7) + int(total * .72), "contrib_all": total2 + total,
        "calendar": weeks, "total_last_year": total,
        "languages": [("Python", "#3572A5", 61000), ("Jupyter Notebook", "#DA5B0B", 30000),
                      ("C++", "#f34b7d", 14000), ("TypeScript", "#3178c6", 9000),
                      ("HTML", "#e34c26", 5000), ("CSS", "#563d7c", 3000)],
        "calendars": {prev_year: weeks2, today.year: weeks},
        "demo": True,
    }


# ─────────────────────────────── HELPERS ──────────────────────────────────
def esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def kfmt(n) -> str:
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def shade(hex_color: str, f: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if f <= 1:
        r, g, b = (int(c * f) for c in (r, g, b))
    else:
        r, g, b = (int(c + (255 - c) * (f - 1)) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def ramp_color(t: float) -> str:
    t = max(0.0, min(1.0, t))
    for (a, ca), (b, cb) in zip(RAMP, RAMP[1:]):
        if t <= b:
            k = (t - a) / (b - a)
            return "#%02X%02X%02X" % tuple(int(x + (y - x) * k) for x, y in zip(ca, cb))
    return "#%02X%02X%02X" % RAMP[-1][1]


def level_info(d: dict) -> dict:
    xp = (d["contrib_all"] * XP_WEIGHTS["contributions"] + d["commits_all"] * XP_WEIGHTS["commits"]
          + d["prs"] * XP_WEIGHTS["prs"] + d["issues"] * XP_WEIGHTS["issues"]
          + d["stars"] * XP_WEIGHTS["stars"] + d["repos"] * XP_WEIGHTS["repos"]
          + d["followers"] * XP_WEIGHTS["followers"])
    lv = int(math.sqrt(xp / XP_CURVE))
    cur, nxt = XP_CURVE * lv * lv, XP_CURVE * (lv + 1) ** 2
    rank_i = max(i for i, (m, _, _) in enumerate(RANKS) if lv >= m)
    return {"xp": xp, "level": lv, "cur": cur, "next": nxt,
            "progress": (xp - cur) / max(1, nxt - cur),
            "rank": RANKS[rank_i][1], "rank_color": RANKS[rank_i][2], "rank_i": rank_i}


def days_flat(d: dict) -> list:
    return [x for w in d["calendar"] for x in w]


def streaks(d: dict) -> dict:
    """current streak (today backwards), longest streak inside the 12-month window."""
    days = days_flat(d)
    today = dt.date.today()
    cur = 0
    if days:
        i = len(days) - 1
        # today may still be empty — start from the last day that has contributions
        if dt.date.fromisoformat(days[-1]["date"]) >= today and days[-1]["count"] == 0:
            i -= 1
        while i >= 0 and days[i]["count"] > 0:
            cur += 1
            i -= 1
    best = run = 0
    for day in days:
        run = run + 1 if day["count"] > 0 else 0
        best = max(best, run)
    return {"current": cur, "longest": best}


def summary(d: dict) -> dict:
    days = days_flat(d)
    active = sum(1 for x in days if x["count"] > 0)
    peak = max(days, key=lambda x: x["count"]) if days else None
    st = streaks(d)
    by_wd = [0] * 7
    for x in days:
        by_wd[x["weekday"]] += x["count"]
    return {
        "total": d["total_last_year"], "days": len(days), "active": active,
        "current_streak": st["current"], "longest_streak": st["longest"],
        "peak": {"date": peak["date"], "count": peak["count"]} if peak and peak["count"] else None,
        "avg_active": (d["total_last_year"] / active) if active else 0,
        "busiest_weekday": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][by_wd.index(max(by_wd))],
        "weeks": len(d["calendar"]),
    }


def smooth_path(pts) -> str:
    """Catmull-Rom → cubic bezier through pts [(x, y), ...]."""
    if len(pts) < 2:
        return ""
    n = len(pts)
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(d)


# ───────────────────────────── ICONS (24x24) ──────────────────────────────
ICONS = {
    "repo": "M4 4.5A2.5 2.5 0 0 1 6.5 2H20v16H6.5A2.5 2.5 0 0 0 4 20.5zM4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5M8 7h8M8 11h6",
    "commit": "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM2 12h6M16 12h6",
    "star": "M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5L2.5 9.4l6.6-.9z",
    "users": "M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20M10 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM20 20v-1.5a3.5 3.5 0 0 0-2.5-3.3M15.5 4.2a3.5 3.5 0 0 1 0 6.6",
    "pr": "M6 3a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM6 8v8M6 16a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM18 16a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM18 16V9a3 3 0 0 0-3-3h-4M13 3.5L10.5 6 13 8.5",
    "issue": "M12 2.5a9.5 9.5 0 1 0 0 19 9.5 9.5 0 0 0 0-19zM12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2z",
    "pulse": "M2 12h4l2.5-6 4 12 3-9 2 3H22",
    "flame": "M12 2s5 4.5 5 9a5 5 0 0 1-10 0c0-1.6.7-3 1.5-4C9 9 7 11 7 14a5 5 0 0 0 10 0c0-4.5-5-12-5-12z",
    "calendar": "M4 6h16v14H4zM4 10h16M9 3v4M15 3v4",
    "atom": "M12 12m-2.2 0a2.2 2.2 0 1 0 4.4 0a2.2 2.2 0 1 0-4.4 0M4.5 7.5c4.5 2 10 5 13.5 9M19.5 7.5c-4.5 2-10 5-13.5 9",
    "spark": "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
}


def icon(name: str, x: float, y: float, color: str, size: float = 24, sw: float = 1.7) -> str:
    s = size / 24
    return (f'<path d="{ICONS[name]}" transform="translate({x} {y}) scale({s})" fill="none" stroke="{color}" '
            f'stroke-width="{sw / s:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')


# ───────────────────────── shared SVG scaffolding ──────────────────────────
def svg_open(W: int, H: int, label: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="{esc(label)}">\n<title>{esc(title)}</title>\n')


DEFS_COMMON = f"""
  <linearGradient id="holo" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{CY_L}"/><stop offset=".38" stop-color="{BL_L}"/>
    <stop offset=".68" stop-color="{VI_L}"/><stop offset="1" stop-color="{MG_L}"/>
  </linearGradient>
  <linearGradient id="holoV" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{VI_L}"/><stop offset=".55" stop-color="{BL_L}"/>
    <stop offset="1" stop-color="{CY_L}"/>
  </linearGradient>
  <linearGradient id="paper" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="{PAPER}"/>
  </linearGradient>
  <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="2.2" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="soft" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="6"/></filter>
"""


def demo_tag(d: dict, x: float, y: float, anchor: str = "end") -> str:
    if not d["demo"]:
        return ""
    return (f'<text x="{x}" y="{y}" font-size="9.5" fill="{AM}" text-anchor="{anchor}" '
            f'letter-spacing="1.4" class="pulse">PREVIEW DATA · FIRST SYNC PENDING</text>')


# ───────────────────────────── TELEMETRY CARD ─────────────────────────────
def render_stats(d: dict) -> str:
    W, H = 1000, 470
    L = level_info(d)
    out = []

    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="18" fill="url(#paper)"/>')
    out.append(f'<rect x="0" y="0" width="{W}" height="4" rx="2" fill="url(#holo)"/>')
    out.append(f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="17.5" fill="none" '
               f'stroke="{LINE}" stroke-width="1.5"/>')

    # ---- row 1: stat tiles ----
    tiles = [
        ("repo", kfmt(d["repos"]), "REPOSITORIES", CY),
        ("commit", kfmt(d["commits_year"]), f"COMMITS · {d['year']}", GR),
        ("star", kfmt(d["stars"]), "STARS EARNED", AM),
        ("users", kfmt(d["followers"]), "FOLLOWERS", MG),
    ]
    tw, th, gap = (W - 3 * 16) / 4, 96, 16
    for i, (ic, val, label, c) in enumerate(tiles):
        x = i * (tw + gap)
        out.append(f'<g class="rise" style="animation-delay:{i * .12:.2f}s">')
        out.append(f'<rect x="{x + .75:.1f}" y="{20.75:.1f}" width="{tw - 1.5:.1f}" height="{th - 1.5}" rx="14" '
                   f'fill="{PANEL}" stroke="{LINE}" stroke-width="1.4"/>')
        out.append(f'<rect x="{x + .75:.1f}" y="{20.75:.1f}" width="{tw - 1.5:.1f}" height="3" rx="1.5" fill="{c}"/>')
        out.append(f'<rect x="{x + .75:.1f}" y="{20.75:.1f}" width="{tw - 1.5:.1f}" height="{th - 1.5}" rx="14" '
                   f'fill="none" stroke="{c}" stroke-width="2" stroke-opacity=".55" '
                   f'stroke-dasharray="80 {2 * (tw + th):.0f}" class="trace" style="animation-delay:-{i * 1.3:.1f}s"/>')
        cx, cy = x + 46, 20 + th / 2
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="26" fill="{c}" fill-opacity=".08"/>')
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="26" fill="none" stroke="{c}" stroke-opacity=".5" '
                   f'stroke-width="1.2" stroke-dasharray="5 5" class="spin"/>')
        out.append(icon(ic, cx - 12, cy - 12, c, 24, 1.8))
        out.append(f'<text x="{x + 88:.1f}" y="{cy + 2:.1f}" font-size="30" font-weight="800" fill="{INK}">{esc(val)}</text>')
        out.append(f'<text x="{x + 89:.1f}" y="{cy + 24:.1f}" font-size="10.5" fill="{MUTED}" letter-spacing="1.5">{esc(label)}</text>')
        out.append('</g>')

    # ---- row 2 left: level ring ----
    Y = 132
    LW = 470
    PH = H - Y - 16
    out.append(f'<rect x=".75" y="{Y + .75:.1f}" width="{LW - 1.5:.1f}" height="{PH - 1.5:.1f}" rx="16" '
               f'fill="{PANEL}" stroke="{LINE}" stroke-width="1.4"/>')
    out.append(f'<text x="26" y="{Y + 36:.1f}" font-size="15" font-weight="700" fill="{INK}" letter-spacing="1.8">'
               f'<tspan fill="{VI}">✦</tspan> LEVEL SYSTEM</text>')
    out.append(f'<text x="{LW - 24}" y="{Y + 36:.1f}" font-size="11" fill="{MUTED}" text-anchor="end" letter-spacing="1">'
               f'XP <tspan fill="{INK}" font-weight="700">{L["xp"]:,}</tspan></text>')
    out.append(f'<line x1="26" y1="{Y + 50:.1f}" x2="{LW - 26}" y2="{Y + 50:.1f}" stroke="{LINE}"/>')

    rcx, rcy, R = 128, Y + 176, 74
    circ = 2 * math.pi * R
    prog = max(0.04, min(1.0, L["progress"]))
    out.append(f'<circle cx="{rcx}" cy="{rcy}" r="{R + 22}" fill="url(#halo)"/>')
    out.append(f'<circle cx="{rcx}" cy="{rcy}" r="{R + 15}" fill="none" stroke="{CY}" stroke-opacity=".35" '
               f'stroke-width="1" stroke-dasharray="2 6" class="spin"/>')
    out.append(f'<circle cx="{rcx}" cy="{rcy}" r="{R}" fill="none" stroke="{GRID}" stroke-width="10"/>')
    out.append(f'<circle cx="{rcx}" cy="{rcy}" r="{R}" fill="none" stroke="url(#ring)" stroke-width="10" '
               f'stroke-linecap="round" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ * (1 - prog):.1f}" '
               f'transform="rotate(-90 {rcx} {rcy})" class="fill"/>')
    out.append(f'<circle cx="{rcx}" cy="{rcy}" r="{R - 15}" fill="{PANEL2}" stroke="{LINE}"/>')
    out.append(f'<path d="{GH_MARK}" transform="translate({rcx - 20} {rcy - 40}) scale(1.6667)" fill="{INK2}"/>')
    out.append(f'<text x="{rcx}" y="{rcy + 22:.1f}" font-size="17" font-weight="800" fill="{INK}" '
               f'text-anchor="middle" letter-spacing="1">LEVEL {L["level"]}</text>')
    out.append(f'<text x="{rcx}" y="{rcy + 40:.1f}" font-size="10" fill="{L["rank_color"]}" '
               f'text-anchor="middle" letter-spacing="2">{L["rank"]}</text>')

    stats = [
        ("star", "Total Stars", kfmt(d["stars"]), AM),
        ("commit", "Total Commits", kfmt(d["commits_all"]), GR),
        ("pr", "Pull Requests", kfmt(d["prs"]), VI),
        ("issue", "Issues Opened", kfmt(d["issues"]), MG),
        ("pulse", "Contributions", kfmt(d["contrib_all"]), CY),
    ]
    for i, (ic, label, val, c) in enumerate(stats):
        y = Y + 96 + i * 38
        out.append(f'<g class="slide" style="animation-delay:{.25 + i * .1:.2f}s">')
        out.append(f'<rect x="238" y="{y - 19:.1f}" width="216" height="32" rx="9" fill="{c}" fill-opacity=".05" '
                   f'class="hl" style="animation-delay:{i * 1.1:.1f}s"/>')
        out.append(icon(ic, 248, y - 12, c, 20, 1.8))
        out.append(f'<text x="278" y="{y + 2:.1f}" font-size="13" fill="{INK2}">{esc(label)}</text>')
        out.append(f'<text x="440" y="{y + 2:.1f}" font-size="14" font-weight="700" fill="{INK}" '
                   f'text-anchor="end">{esc(val)}</text>')
        out.append('</g>')

    # ---- row 2 right: XP bar + rank ladder ----
    RX, RW = 486, W - 486
    out.append(f'<rect x="{RX + .75:.1f}" y="{Y + .75:.1f}" width="{RW - 1.5:.1f}" height="{PH - 1.5:.1f}" '
               f'rx="16" fill="{PANEL}" stroke="{LINE}" stroke-width="1.4"/>')
    out.append(f'<text x="{RX + 26}" y="{Y + 36:.1f}" font-size="15" font-weight="700" fill="{INK}" '
               f'letter-spacing="1.8"><tspan fill="{CY}">◆</tspan> PROGRESSION</text>')
    out.append(f'<text x="{RX + RW - 24}" y="{Y + 36:.1f}" font-size="11" fill="{MUTED}" text-anchor="end" '
               f'letter-spacing="1">MEMBER SINCE {d["created_at"][:4]}</text>')
    out.append(f'<line x1="{RX + 26}" y1="{Y + 50:.1f}" x2="{RX + RW - 26}" y2="{Y + 50:.1f}" stroke="{LINE}"/>')

    bx, by, bw = RX + 26, Y + 92, RW - 52
    out.append(f'<text x="{bx}" y="{by - 10:.1f}" font-size="11" fill="{MUTED}" letter-spacing="1">LV {L["level"]}</text>')
    out.append(f'<text x="{bx + bw}" y="{by - 10:.1f}" font-size="11" fill="{MUTED}" text-anchor="end" '
               f'letter-spacing="1">LV {L["level"] + 1} · {max(0, L["next"] - L["xp"]):,} XP TO GO</text>')
    out.append(f'<rect x="{bx}" y="{by:.1f}" width="{bw}" height="14" rx="7" fill="{PANEL2}" stroke="{LINE}"/>')
    fw = max(16, bw * L["progress"])
    out.append(f'<g class="bar"><rect x="{bx}" y="{by:.1f}" width="{fw:.1f}" height="14" rx="7" fill="url(#xpg)"/>'
               f'<rect x="{bx}" y="{by:.1f}" width="{fw:.1f}" height="14" rx="7" fill="url(#xpg)" opacity=".45" '
               f'filter="url(#glow)"/></g>')
    out.append(f'<clipPath id="xpc"><rect x="{bx}" y="{by:.1f}" width="{fw:.1f}" height="14" rx="7"/></clipPath>'
               f'<g clip-path="url(#xpc)"><rect x="{bx - 70}" y="{by:.1f}" width="46" height="14" '
               f'fill="url(#shine)" class="shine"/></g>')
    out.append(f'<text x="{bx + bw / 2:.1f}" y="{by + 34:.1f}" font-size="10.5" fill="{MUTED}" text-anchor="middle" '
               f'letter-spacing="1">{int(L["progress"] * 100)}% OF LEVEL {L["level"] + 1} UNLOCKED</text>')

    ly = Y + 176
    n = len(RANKS)
    seg = (RW - 52) / n
    out.append(f'<text x="{bx}" y="{ly - 20:.1f}" font-size="11" fill="{MUTED}" letter-spacing="1.5">RANK LADDER</text>')
    for i, (mn, title, c) in enumerate(RANKS):
        x = bx + i * seg
        done, cur = i <= L["rank_i"], i == L["rank_i"]
        pts = (f"{x:.1f},{ly} {x + seg - 8:.1f},{ly} {x + seg:.1f},{ly + 13} "
               f"{x + seg - 8:.1f},{ly + 26} {x:.1f},{ly + 26} {x + 8:.1f},{ly + 13}")
        cur_cls = ' class="cur"' if cur else ""
        out.append(f'<polygon points="{pts}" fill="{c if done else PANEL2}" '
                   f'fill-opacity="{.9 if cur else (.28 if done else 1)}" stroke="{c}" '
                   f'stroke-opacity="{1 if done else .4}"{cur_cls}/>')
        out.append(f'<text x="{x + seg / 2 + 2:.1f}" y="{ly + 17:.1f}" font-size="9.5" font-weight="700" '
                   f'fill="{"#FFFFFF" if cur else (INK if done else MUTED)}" text-anchor="middle">LV{mn}</text>')
        if cur:
            out.append(f'<text x="{x + seg / 2 + 2:.1f}" y="{ly + 44:.1f}" font-size="10" fill="{c}" '
                       f'text-anchor="middle" letter-spacing="1">▲ {title}</text>')

    # language share strip
    gy = Y + 258
    langs = d["languages"][:6]
    total = sum(l[2] for l in langs) or 1
    out.append(f'<text x="{bx}" y="{gy - 10:.1f}" font-size="11" fill="{MUTED}" letter-spacing="1.5">CODE SHARE</text>')
    xx, segs = bx, []
    for i, (name, color, size) in enumerate(langs):
        w = bw * size / total
        color = color or LANG_FALLBACK[i % len(LANG_FALLBACK)]
        segs.append(f'<rect x="{xx:.1f}" y="{gy:.1f}" width="{w + .6:.1f}" height="10" fill="{color}"/>')
        xx += w
    out.append(f'<g clip-path="url(#cc)"><rect x="{bx}" y="{gy:.1f}" width="{bw}" height="10" fill="{PANEL2}"/>'
               f'<g class="bar">{"".join(segs)}</g></g>')
    out.append(f'<clipPath id="cc"><rect x="{bx}" y="{gy:.1f}" width="{bw}" height="10" rx="5"/></clipPath>')
    for i, (name, color, size) in enumerate(langs):
        color = color or LANG_FALLBACK[i % len(LANG_FALLBACK)]
        col, row = i % 3, i // 3
        lx, lyy = bx + col * (bw / 3), gy + 32 + row * 21
        nm = name if len(name) <= 13 else name[:12] + "…"
        out.append(f'<circle cx="{lx + 5:.1f}" cy="{lyy - 4:.1f}" r="4.5" fill="{color}"/>')
        out.append(f'<text x="{lx + 15:.1f}" y="{lyy:.1f}" font-size="11" fill="{INK2}">{esc(nm)} '
                   f'<tspan fill="{MUTED}">{100 * size / total:.0f}%</tspan></text>')

    out.append(demo_tag(d, W - 26, H - 8))

    css = f"""
  text {{ font-family: {FONT}; }}
  .rise {{ animation: rise .7s cubic-bezier(.2,.8,.2,1) both; }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(12px) }} to {{ opacity: 1; transform: none }} }}
  .slide {{ animation: slide .6s cubic-bezier(.2,.8,.2,1) both; }}
  @keyframes slide {{ from {{ opacity: 0; transform: translateX(14px) }} to {{ opacity: 1; transform: none }} }}
  .trace {{ animation: trace 8s linear infinite; }}
  @keyframes trace {{ to {{ stroke-dashoffset: -{2 * (tw + th):.0f} }} }}
  .spin {{ animation: spin 16s linear infinite; transform-box: fill-box; transform-origin: center; }}
  @keyframes spin {{ to {{ transform: rotate(360deg) }} }}
  .fill {{ animation: fill 2.2s cubic-bezier(.3,.9,.3,1) both .3s; }}
  @keyframes fill {{ from {{ stroke-dashoffset: {circ:.1f} }} }}
  .bar {{ animation: bar 1.8s cubic-bezier(.3,.9,.3,1) both .4s; transform-box: fill-box; transform-origin: left center; }}
  @keyframes bar {{ from {{ transform: scaleX(0) }} }}
  .shine {{ animation: shine 3.4s ease-in-out infinite 1.6s; }}
  @keyframes shine {{ 0% {{ transform: translateX(0) }} 60%,100% {{ transform: translateX({bw + 90:.0f}px) }} }}
  .hl {{ animation: hl 5.5s ease-in-out infinite; }}
  @keyframes hl {{ 0%,100% {{ fill-opacity: .04 }} 8% {{ fill-opacity: .14 }} 20% {{ fill-opacity: .04 }} }}
  .cur {{ animation: cur 1.8s ease-in-out infinite; }}
  @keyframes cur {{ 0%,100% {{ fill-opacity: .9 }} 50% {{ fill-opacity: .5 }} }}
  .pulse {{ animation: pulse 1.8s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity: .4 }} 50% {{ opacity: 1 }} }}
"""
    defs = DEFS_COMMON + f"""
  <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{CY_L}"/>
    <stop offset=".55" stop-color="{VI_L}"/><stop offset="1" stop-color="{MG_L}"/></linearGradient>
  <linearGradient id="xpg" x1="0" x2="1"><stop offset="0" stop-color="{CY_L}"/>
    <stop offset=".6" stop-color="{VI_L}"/><stop offset="1" stop-color="{MG_L}"/></linearGradient>
  <linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>
    <stop offset=".5" stop-color="#FFFFFF" stop-opacity=".85"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
  <radialGradient id="halo"><stop offset=".55" stop-color="{VI_L}" stop-opacity=".18"/>
    <stop offset="1" stop-color="{VI_L}" stop-opacity="0"/></radialGradient>
"""
    return (svg_open(W, H, f"GitHub telemetry for {d['login']}: level {L['level']} {L['rank']}, "
                           f"{d['stars']} stars, {d['commits_all']} commits, {d['prs']} pull requests, "
                           f"{d['issues']} issues",
                     "KCN_LAB :: GITHUB TELEMETRY")
            + f"<style>{css}</style>\n<defs>{defs}</defs>\n" + "\n".join(o for o in out if o) + "\n</svg>\n")


# ─────────────────────────── TOP LANGUAGES CARD ───────────────────────────
def render_top_langs(d: dict) -> str:
    W, H = 1000, 330
    langs = d["languages"][:7]
    total = sum(l[2] for l in langs) or 1
    out = []
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="18" fill="url(#paper)"/>')
    out.append(f'<rect x="0" y="0" width="{W}" height="4" rx="2" fill="url(#holo)"/>')
    out.append(f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="17.5" fill="none" stroke="{LINE}" stroke-width="1.5"/>')
    out.append(f'<text x="26" y="38" font-size="15" font-weight="700" fill="{INK}" letter-spacing="1.8">'
               f'<tspan fill="{MG}">◆</tspan> TOP LANGUAGES</text>')
    out.append(f'<text x="{W - 26}" y="38" font-size="11" fill="{MUTED}" text-anchor="end" letter-spacing="1">'
               f'BY CODE SIZE</text>')
    out.append(f'<line x1="26" y1="52" x2="{W - 26}" y2="52" stroke="{LINE}"/>')

    if not langs:
        out.append(f'<text x="{W / 2}" y="{H / 2}" font-size="12" fill="{MUTED}" text-anchor="middle">'
                   f'no public code yet — first repository incoming_</text>')
    else:
        y = 82
        bar_w = W - 200
        for i, (name, color, size) in enumerate(langs):
            color = color or LANG_FALLBACK[i % len(LANG_FALLBACK)]
            pct = 100 * size / total
            nm = name if len(name) <= 15 else name[:14] + "…"
            out.append(f'<g class="row" style="animation-delay:{i * .1:.2f}s">')
            out.append(f'<circle cx="34" cy="{y - 4:.1f}" r="5" fill="{color}"/>')
            out.append(f'<text x="48" y="{y:.1f}" font-size="12.5" fill="{INK}" font-weight="600">{esc(nm)}</text>')
            out.append(f'<text x="{W - 26}" y="{y:.1f}" font-size="12" fill="{MUTED}" text-anchor="end">'
                       f'<tspan fill="{INK}" font-weight="700">{pct:.1f}%</tspan> · {kfmt(size)}B</text>')
            out.append(f'<rect x="48" y="{y + 9:.1f}" width="{bar_w}" height="8" rx="4" fill="{PANEL2}"/>')
            out.append(f'<g class="bar" style="animation-delay:{.2 + i * .1:.2f}s">'
                       f'<rect x="48" y="{y + 9:.1f}" width="{bar_w * pct / 100:.1f}" height="8" rx="4" fill="{color}"/></g>')
            out.append('</g>')
            y += 34

    out.append(demo_tag(d, W - 26, H - 10))
    css = f"""
  text {{ font-family: {FONT}; }}
  .row {{ animation: row .6s cubic-bezier(.2,.8,.2,1) both; }}
  @keyframes row {{ from {{ opacity: 0; transform: translateX(-14px) }} to {{ opacity: 1; transform: none }} }}
  .bar {{ animation: bar 1.5s cubic-bezier(.3,.9,.3,1) both; transform-box: fill-box; transform-origin: left center; }}
  @keyframes bar {{ from {{ transform: scaleX(0) }} }}
  .pulse {{ animation: pulse 1.8s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity: .4 }} 50% {{ opacity: 1 }} }}
"""
    return (svg_open(W, H, f"Top languages for {d['login']}", "KCN_LAB :: TOP LANGUAGES")
            + f"<style>{css}</style>\n<defs>{DEFS_COMMON}</defs>\n" + "\n".join(o for o in out if o) + "\n</svg>\n")


# ──────────────────────── 3D CONTRIBUTION GRAPH ───────────────────────────
# isometric projection helpers -----------------------------------------------
CELL = 11.0                        # logical cell size
CW = CELL * math.cos(math.pi / 6)  # week step on screen
CH = CELL * 0.42                   # weekday step on screen (flattened isometric)
OX, OY = 250.0, 150.0              # screen position of grid corner (0,0)
GX, GY = 470.0, 290.0              # pivot used by the rotation transforms
MAXH = 58.0                        # tallest pillar


def iso(x: float, z: float, y: float = 0.0):
    return (OX + (x - z) * CW, OY + (x + z) * CH - y)


def render_contrib3d(d: dict) -> str:
    """Isometric 3D contribution graph — multi-colour pillars, hover to rotate."""
    W, H = 1000, 570
    weeks = d["calendar"]
    nW = max(1, len(weeks))
    days = days_flat(d)
    counts = [x["count"] for x in days]
    mx = max(counts) if counts else 0
    sm = summary(d)
    nz = sorted((c for c in counts if c > 0), reverse=True)
    hot_min = nz[3] if len(nz) >= 4 else (nz[0] if nz else None)

    out = []
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="18" fill="url(#paper)"/>')
    out.append(f'<rect x="0" y="0" width="{W}" height="4" rx="2" fill="url(#holo)"/>')
    out.append(f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="17.5" fill="none" '
               f'stroke="{LINE}" stroke-width="1.5"/>')

    # ---------------- header ----------------
    out.append(f'<circle cx="42" cy="40" r="13" fill="none" stroke="{GRID}" stroke-width="4"/>')
    out.append(f'<circle cx="42" cy="40" r="13" fill="none" stroke="url(#holo)" stroke-width="4" '
               f'stroke-linecap="round" stroke-dasharray="54 28" class="spin"/>')
    out.append(f'<text x="66" y="46" font-size="19" font-weight="800" fill="{INK}" letter-spacing="1.4">'
               f'CONTRIBUTION GRAPH <tspan fill="{MUTED}" font-weight="500">· 3D ISOMETRIC</tspan></text>')
    out.append(f'<text x="67" y="66" font-size="11.5" fill="{MUTED}" letter-spacing=".6">'
               f'<tspan fill="{VI}" font-weight="700">{sm["total"]:,}</tspan> contributions · last 12 months · '
               f'one pillar per day</text>')
    out.append(f'<text x="{W - 26}" y="46" font-size="10.5" fill="{MUTED}" text-anchor="end" letter-spacing="1.4">'
               f'INTERACTIVE VIEW → <tspan fill="{CY}" font-weight="700">kcn-369.github.io/KCN-369</tspan></text>')

    # ---------------- rotation chips (hover targets) ----------------
    # NOTE: these must appear BEFORE <g id="stage"> in document order so the
    # CSS sibling selector `#z1:hover ~ #stage #view` can rotate the scene.
    chips = [("◀ 40°", -36, 5), ("◀ 20°", -18, 2), ("FRONT", 0, 0), ("20° ▶", 18, -2), ("40° ▶", 36, -5)]
    cw_, chh = 104, 30
    x0 = (W - (len(chips) * cw_ + (len(chips) - 1) * 10)) / 2
    chip_markup = []
    for i, (label, yaw, pitch) in enumerate(chips):
        x = x0 + i * (cw_ + 10)
        chip_markup.append(f'<g class="chip" id="z{i + 1}">')
        chip_markup.append(f'<rect x="{x:.1f}" y="492" width="{cw_}" height="{chh}" rx="15" fill="{PANEL}" '
                           f'stroke="{LINE}" stroke-width="1.3" pointer-events="all"/>')
        chip_markup.append(f'<text x="{x + cw_ / 2:.1f}" y="512" font-size="11" font-weight="600" fill="{INK2}" '
                           f'text-anchor="middle" letter-spacing="1.2">{label}</text>')
        chip_markup.append('</g>')
    out.append("".join(chip_markup))

    # ---------------- stage: glass platform ----------------
    pad = 0.7
    c = [iso(-pad, -pad), iso(nW + pad, -pad), iso(nW + pad, 7 + pad), iso(-pad, 7 + pad)]
    thick = 12
    out.append(f'<path d="M{c[3][0]:.1f},{c[3][1]:.1f} L{c[2][0]:.1f},{c[2][1]:.1f} '
               f'L{c[2][0]:.1f},{c[2][1] + thick:.1f} L{c[3][0]:.1f},{c[3][1] + thick:.1f} Z" fill="#C9D8EE"/>')
    out.append(f'<path d="M{c[2][0]:.1f},{c[2][1]:.1f} L{c[1][0]:.1f},{c[1][1]:.1f} '
               f'L{c[1][0]:.1f},{c[1][1] + thick:.1f} L{c[2][0]:.1f},{c[2][1] + thick:.1f} Z" fill="#AFC2DE"/>')
    out.append(f'<polygon points="{c[0][0]:.1f},{c[0][1]:.1f} {c[1][0]:.1f},{c[1][1]:.1f} '
               f'{c[2][0]:.1f},{c[2][1]:.1f} {c[3][0]:.1f},{c[3][1]:.1f}" fill="#FFFFFF" '
               f'stroke="url(#holo)" stroke-opacity=".55" stroke-width="1.3"/>')

    # ---------------- pillars (painter order) ----------------
    pillars = []
    for k in range(7):                       # k = 0 back row (Sun) → 6 front row (Sat)
        v = (k + .5) / 7
        rx, ry = CW * .40, CH * .40
        for wi in range(nW):
            day = next((x for x in weeks[wi] if x["weekday"] == k), None)
            if day is None:
                continue
            u = (wi + .5) / nW
            bx, by = iso(wi + .5, k + .5)
            cnt, lvl = day["count"], day["level"]
            tip = f'{day["date"]} · {cnt} contribution' + ("s" if cnt != 1 else "")
            if cnt == 0:
                pillars.append((wi + k, wi,
                    f'<polygon points="{bx - rx:.1f},{by - ry:.1f} {bx + rx:.1f},{by - ry:.1f} '
                    f'{bx + rx:.1f},{by + ry:.1f} {bx - rx:.1f},{by + ry:.1f}" fill="{EMPTY_CELL}" '
                    f'stroke="#D2DFF0" stroke-width=".7"><title>{esc(tip)}</title></polygon>'))
                continue
            h = 4 + MAXH * (cnt / mx) ** .55 if mx else 4
            ty = by - h
            col = ramp_color(u)
            alpha = [0, .55, .7, .85, 1][min(lvl, 4)]
            top = shade(col, 1.30)
            left = shade(col, .68)
            right = shade(col, .92)
            is_hot = hot_min is not None and cnt >= hot_min
            g = [f'<g class="pl" style="animation-delay:{.05 + wi * .022 + k * .012:.3f}s">', f'<title>{esc(tip)}</title>']
            # soft contact shadow
            g.append(f'<ellipse cx="{bx:.1f}" cy="{by + 2:.1f}" rx="{rx * 1.7:.1f}" ry="{ry * 1.5:.1f}" '
                     f'fill="{col}" fill-opacity=".10"/>')
            # side faces
            g.append(f'<path d="M{bx - rx:.1f},{ty:.1f} L{bx - rx:.1f},{by:.1f} '
                     f'A{rx:.1f},{ry:.1f} 0 0 0 {bx + rx:.1f},{by:.1f} L{bx + rx:.1f},{ty:.1f} Z" '
                     f'fill="{left}" fill-opacity="{alpha:.2f}"/>')
            g.append(f'<path d="M{bx + rx:.1f},{ty:.1f} L{bx + rx:.1f},{by:.1f} '
                     f'A{rx:.1f},{ry:.1f} 0 0 0 {bx - rx:.1f},{by:.1f} L{bx - rx:.1f},{ty:.1f} Z" '
                     f'fill="{right}" fill-opacity="{alpha:.2f}"/>')
            # top face
            g.append(f'<ellipse cx="{bx:.1f}" cy="{ty:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{top}" '
                     f'fill-opacity="{alpha:.2f}" stroke="#FFFFFF" stroke-opacity=".6" stroke-width=".5" '
                     f'class="{"hot" if is_hot else "tp"}" style="animation-delay:{wi * .08:.2f}s"/>')
            if is_hot:
                g.append(f'<circle cx="{bx:.1f}" cy="{ty - 2:.1f}" r="1.3" fill="{col}" class="spark" '
                         f'style="animation-delay:-{wi % 5 * .5:.1f}s"/>')
            g.append('</g>')
            # painter's algorithm: draw back-to-front, i.e. increasing (week + weekday)
            pillars.append((wi + k, wi, "".join(g)))
    pillars.sort(key=lambda t: (t[0], t[1]))
    out.append(f'<g id="stage"><g id="view">{"".join(m for _, _, m in pillars)}</g></g>')

    # ---------------- axis labels ----------------
    for k, name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        x, y = iso(-0.35, k + .5)
        out.append(f'<text x="{x - 10:.1f}" y="{y + 3:.1f}" font-size="10.5" fill="{MUTED}" '
                   f'text-anchor="end" class="lbl">{name}</text>')
    last_m, last_wi = None, -99
    for wi, w in enumerate(weeks):
        if not w:
            continue
        m = dt.date.fromisoformat(w[0]["date"]).month
        if m != last_m:
            if wi - last_wi >= 3 and wi < nW - 2:
                x, y = iso(wi + .5, 7.45)
                out.append(f'<text x="{x:.1f}" y="{y + 20:.1f}" font-size="10" fill="{MUTED}" '
                           f'text-anchor="middle" class="lbl">{dt.date(2000, m, 1).strftime("%b")}</text>')
                last_wi = wi
            last_m = m

    # ---------------- right HUD ----------------
    hx, hy, hw, hh = 786, 104, 194, 340
    out.append(f'<rect x="{hx}" y="{hy}" width="{hw}" height="{hh}" rx="16" fill="{PANEL}" '
               f'stroke="{LINE}" stroke-width="1.4"/>')
    out.append(f'<rect x="{hx}" y="{hy}" width="{hw}" height="3" rx="1.5" fill="url(#holo)"/>')
    out.append(f'<text x="{hx + 18}" y="{hy + 30}" font-size="11.5" font-weight="700" fill="{INK}" '
               f'letter-spacing="1.6">12-MONTH SUMMARY</text>')
    rows = [
        ("TOTAL", f'{sm["total"]:,}', VI),
        ("ACTIVE DAYS", f'{sm["active"]}/{sm["days"]}', CY),
        ("CURRENT STREAK", f'{sm["current_streak"]}d', GR),
        ("LONGEST STREAK", f'{sm["longest_streak"]}d', BL),
        ("AVG / ACTIVE DAY", f'{sm["avg_active"]:.1f}', AM),
        ("BUSIEST WEEKDAY", sm["busiest_weekday"], MG),
    ]
    yy = hy + 58
    for i, (label, val, c) in enumerate(rows):
        out.append(f'<g class="slide" style="animation-delay:{.3 + i * .09:.2f}s">')
        out.append(f'<rect x="{hx + 12}" y="{yy - 17:.1f}" width="{hw - 24}" height="30" rx="8" '
                   f'fill="{c}" fill-opacity=".05"/>')
        out.append(f'<rect x="{hx + 12}" y="{yy - 17:.1f}" width="3" height="30" rx="1.5" fill="{c}"/>')
        out.append(f'<text x="{hx + 26}" y="{yy + 2:.1f}" font-size="10.5" fill="{MUTED}" '
                   f'letter-spacing="1.1">{label}</text>')
        out.append(f'<text x="{hx + hw - 22}" y="{yy + 2:.1f}" font-size="13" font-weight="700" fill="{INK}" '
                   f'text-anchor="end">{esc(val)}</text>')
        out.append('</g>')
        yy += 34
    # peak day
    if sm["peak"]:
        pd_ = dt.date.fromisoformat(sm["peak"]["date"])
        out.append(f'<text x="{hx + 18}" y="{yy + 8:.1f}" font-size="10.5" fill="{MUTED}" letter-spacing="1.1">'
                   f'PEAK DAY</text>')
        out.append(f'<text x="{hx + hw - 22}" y="{yy + 8:.1f}" font-size="11.5" font-weight="700" fill="{MG}" '
                   f'text-anchor="end">{pd_.strftime("%b %d")} · {sm["peak"]["count"]}</text>')
    # legend
    ly = hy + hh - 34
    out.append(f'<text x="{hx + 18}" y="{ly:.1f}" font-size="10.5" fill="{MUTED}" letter-spacing="1.1">Less</text>')
    for i, col in enumerate([ramp_color(t) for t in (.05, .3, .5, .72, 1.0)]):
        cxx = hx + 52 + i * 22
        pts = " ".join(f"{cxx + 9 * math.cos(math.radians(60 * j + 30)):.1f},"
                       f"{ly - 4 + 9 * math.sin(math.radians(60 * j + 30)):.1f}" for j in range(6))
        out.append(f'<polygon points="{pts}" fill="{col}"/>')
    out.append(f'<text x="{hx + hw - 18}" y="{ly:.1f}" font-size="10.5" fill="{MUTED}" text-anchor="end" '
               f'letter-spacing="1.1">More</text>')

    out.append(f'<text x="{W / 2:.1f}" y="548" font-size="10.5" fill="{MUTED}" text-anchor="middle" '
               f'letter-spacing="1.6">HOVER AN ANGLE CHIP TO ROTATE THE SCENE · HOVER A PILLAR FOR ITS DATE</text>')
    out.append(demo_tag(d, W / 2, 566, "middle"))

    css = f"""
  text {{ font-family: {FONT}; }}
  .lbl {{ paint-order: stroke; stroke: {PAPER}; stroke-width: 3px; stroke-linejoin: round; }}
  #stage {{ transform-box: view-box; transform-origin: {GX}px {GY}px;
            animation: sway 22s ease-in-out infinite; }}
  @keyframes sway {{ 0%,100% {{ transform: rotateY(-9deg) }} 50% {{ transform: rotateY(9deg) }} }}
  #view {{ transform-box: view-box; transform-origin: {GX}px {GY}px;
           transition: transform 1.1s cubic-bezier(.2,.8,.2,1); }}
  #z1:hover ~ #stage #view {{ transform: perspective(1400px) rotateY(-36deg) rotateX(5deg) scale(.93); }}
  #z2:hover ~ #stage #view {{ transform: perspective(1400px) rotateY(-18deg) rotateX(2deg) scale(.96); }}
  #z3:hover ~ #stage #view {{ transform: perspective(1400px) rotateY(0deg) rotateX(0deg) scale(1); }}
  #z4:hover ~ #stage #view {{ transform: perspective(1400px) rotateY(18deg) rotateX(-2deg) scale(.96); }}
  #z5:hover ~ #stage #view {{ transform: perspective(1400px) rotateY(36deg) rotateX(-5deg) scale(.93); }}
  #z1:hover rect, #z2:hover rect, #z3:hover rect, #z4:hover rect, #z5:hover rect {{ stroke: {VI}; fill: {PANEL2}; }}
  #z1:hover text, #z2:hover text, #z3:hover text, #z4:hover text, #z5:hover text {{ fill: {VI}; }}
  .pl {{ animation: grow 1.1s cubic-bezier(.2,.9,.25,1.05) both; transform-box: fill-box; transform-origin: 50% 100%; }}
  @keyframes grow {{ from {{ transform: scaleY(0); opacity: 0 }} 35% {{ opacity: 1 }} to {{ transform: scaleY(1); opacity: 1 }} }}
  .tp {{ animation: wave 5s ease-in-out infinite; }}
  @keyframes wave {{ 0%,100% {{ opacity: .8 }} 12% {{ opacity: 1 }} 24% {{ opacity: .8 }} }}
  .hot {{ animation: hot 1.9s ease-in-out infinite; }}
  @keyframes hot {{ 0%,100% {{ opacity: 1 }} 50% {{ opacity: .62 }} }}
  .spark {{ animation: spark 2.6s ease-out infinite; }}
  @keyframes spark {{ 0% {{ transform: translateY(0); opacity: 0 }} 20% {{ opacity: 1 }} 100% {{ transform: translateY(-26px); opacity: 0 }} }}
  .slide {{ animation: slide .6s cubic-bezier(.2,.8,.2,1) both; }}
  @keyframes slide {{ from {{ opacity: 0; transform: translateX(16px) }} to {{ opacity: 1; transform: none }} }}
  .spin {{ animation: spin 14s linear infinite; transform-box: fill-box; transform-origin: center; }}
  @keyframes spin {{ to {{ transform: rotate(360deg) }} }}
  .pulse {{ animation: pulse 1.8s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity: .4 }} 50% {{ opacity: 1 }} }}
"""
    return (svg_open(W, H, f"3D isometric contribution graph: {sm['total']} contributions in the last 12 months, "
                           f"{sm['active']} active days, current streak {sm['current_streak']} days",
                     "KCN_LAB :: 3D CONTRIBUTION GRAPH")
            + f"<style>{css}</style>\n<defs>{DEFS_COMMON}</defs>\n" + "\n".join(o for o in out if o) + "\n</svg>\n")


# ───────────────────── ANIMATED FLOW CONTRIBUTION GRAPH ───────────────────
def render_flow(d: dict) -> str:
    """Aurora-flow graph: weekly waveform on top + 53x7 heat grid below."""
    W, H = 1000, 492
    weeks = d["calendar"]
    nW = max(1, len(weeks))
    sm = summary(d)

    # weekly totals
    wtot = [sum(x["count"] for x in w) for w in weeks]
    wmax = max(wtot) if wtot else 0

    # chart geometry
    cx0, cx1 = 74.0, 962.0
    cy0, cy1 = 268.0, 118.0     # baseline / top
    step = (cx1 - cx0) / max(1, nW - 1)

    def px(i):
        return cx0 + i * step

    def py(v):
        return cy0 - (cy0 - cy1) * (v / wmax if wmax else 0)

    pts = [(px(i), py(v)) for i, v in enumerate(wtot)]
    line = smooth_path(pts)
    area = line + f" L{pts[-1][0]:.1f},{cy0:.1f} L{pts[0][0]:.1f},{cy0:.1f} Z"

    out = []
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="18" fill="url(#paper)"/>')
    out.append(f'<rect x="0" y="0" width="{W}" height="4" rx="2" fill="url(#holo)"/>')
    out.append(f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="17.5" fill="none" '
               f'stroke="{LINE}" stroke-width="1.5"/>')

    # header
    out.append(f'<text x="30" y="42" font-size="17" font-weight="800" fill="{INK}" letter-spacing="1.6">'
               f'<tspan fill="{CY}">≋</tspan> CONTRIBUTION FLOW <tspan fill="{MUTED}" font-weight="500" '
               f'font-size="12">· WEEKLY WAVEFORM + DAY MATRIX</tspan></text>')
    out.append(f'<text x="30" y="62" font-size="11" fill="{MUTED}" letter-spacing=".6">'
               f'<tspan fill="{VI}" font-weight="700">{sm["total"]:,}</tspan> contributions · '
               f'{sm["active"]} active days · {sm["weeks"]} weeks</text>')
    years = sorted(d["years"].items())[-4:]
    tx = W - 28
    for y, info in reversed(years):
        w = 62
        tx -= w
        cur = y == d["year"]
        if cur:
            out.append(f'<rect x="{tx:.1f}" y="26" width="{w}" height="28" rx="9" fill="{VI}" '
                       f'fill-opacity=".1" stroke="{VI}" stroke-opacity=".55"/>')
        out.append(f'<text x="{tx + w / 2:.1f}" y="{44:.1f}" font-size="12.5" font-weight="{700 if cur else 500}" '
                   f'fill="{INK if cur else MUTED}" text-anchor="middle">{y}</text>')
        out.append(f'<text x="{tx + w / 2:.1f}" y="{64:.1f}" font-size="9.5" fill="{MUTED}" '
                   f'text-anchor="middle">{kfmt(info["total"])}</text>')
        tx -= 6

    # gridlines
    for f in (0, .25, .5, .75, 1):
        y = py(wmax * f)
        out.append(f'<line x1="{cx0}" y1="{y:.1f}" x2="{cx1}" y2="{y:.1f}" stroke="{GRID}" '
                   f'stroke-dasharray="{"0" if f == 0 else "3 5"}"/>')
        out.append(f'<text x="{cx0 - 10}" y="{y + 3:.1f}" font-size="9.5" fill="{MUTED}" text-anchor="end">'
                   f'{int(round(wmax * f))}</text>')
    # month ticks
    last_m, last_wi = None, -99
    for wi, w in enumerate(weeks):
        if not w:
            continue
        m = dt.date.fromisoformat(w[0]["date"]).month
        if m != last_m:
            if wi - last_wi >= 3 and wi < nW - 2:
                out.append(f'<line x1="{px(wi):.1f}" y1="{cy0:.1f}" x2="{px(wi):.1f}" y2="{cy0 + 6:.1f}" '
                           f'stroke="{LINE}"/>')
                out.append(f'<text x="{px(wi):.1f}" y="{cy0 + 20:.1f}" font-size="10" fill="{MUTED}" '
                           f'text-anchor="middle">{dt.date(2000, m, 1).strftime("%b")}</text>')
                last_wi = wi
            last_m = m

    # waveform
    out.append(f'<path d="{area}" fill="url(#wave)"/>')
    out.append(f'<path d="{line}" fill="none" stroke="url(#holo)" stroke-width="2.6" stroke-linecap="round" '
               f'stroke-dasharray="4000" stroke-dashoffset="4000" class="draw" filter="url(#glow)"/>')
    out.append(f'<path d="{line}" fill="none" stroke="#FFFFFF" stroke-width="3.4" stroke-linecap="round" '
               f'stroke-dasharray="46 1400" class="shimmer" opacity=".9"/>')
    out.append(f'<circle r="5" fill="{VI}" class="scan"><animateMotion dur="16s" repeatCount="indefinite" '
               f'path="{line}"/></circle>')
    out.append(f'<circle r="11" fill="{VI}" fill-opacity=".18" class="scan2">'
               f'<animateMotion dur="16s" repeatCount="indefinite" path="{line}"/></circle>')

    # peak marker
    if wmax:
        pi = wtot.index(wmax)
        out.append(f'<circle cx="{px(pi):.1f}" cy="{py(wmax):.1f}" r="9" fill="none" stroke="{MG}" '
                   f'stroke-width="1.6" class="ping"/>')
        out.append(f'<circle cx="{px(pi):.1f}" cy="{py(wmax):.1f}" r="3.4" fill="{MG}"/>')
        anchor = "end" if pi > nW * .72 else ("start" if pi < nW * .2 else "middle")
        dx = -14 if anchor == "end" else (14 if anchor == "start" else 0)
        out.append(f'<text x="{px(pi) + dx:.1f}" y="{py(wmax) - 14:.1f}" font-size="10.5" fill="{MG}" '
                   f'font-weight="700" text-anchor="{anchor}">PEAK {wmax}/wk</text>')

    # ---- day matrix ----
    gx, gy = 74.0, 316.0
    cell, gap = 15.0, 2.6
    for k, name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        out.append(f'<text x="{gx - 10}" y="{gy + k * (cell + gap) + 11:.1f}" font-size="10" fill="{MUTED}" '
                   f'text-anchor="end">{name}</text>')
    cells = []
    for wi, w in enumerate(weeks):
        for day in w:
            x = gx + wi * (cell + gap)
            y = gy + day["weekday"] * (cell + gap)
            cnt, lvl = day["count"], day["level"]
            fill = EMPTY_CELL if cnt == 0 else LEVEL_COLORS[min(lvl, 4)]
            tip = f'{day["date"]} · {cnt} contribution' + ("s" if cnt != 1 else "")
            cells.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="4" fill="{fill}" '
                         f'class="cell" style="animation-delay:{wi * .028 + day["weekday"] * .01:.3f}s">'
                         f'<title>{esc(tip)}</title></rect>')
    out.append("".join(cells))
    out.append(f'<text x="{gx}" y="{gy + 7 * (cell + gap) + 18:.1f}" font-size="10.5" fill="{MUTED}" '
               f'letter-spacing="1.2">DAY MATRIX · {nW} WEEKS × 7 DAYS · COLOUR = CONTRIBUTION LEVEL</text>')

    # footer telemetry
    fy = H - 14
    items = [("CURRENT STREAK", f'{sm["current_streak"]}d', GR), ("LONGEST", f'{sm["longest_streak"]}d', BL),
             ("ACTIVE", f'{sm["active"]}/{sm["days"]}', CY), ("AVG/ACTIVE", f'{sm["avg_active"]:.1f}', AM),
             ("BUSIEST", sm["busiest_weekday"], MG)]
    tx = 30
    for i, (label, val, c) in enumerate(items):
        out.append(f'<circle cx="{tx + 4}" cy="{fy - 4}" r="4" fill="{c}"/>')
        out.append(f'<text x="{tx + 16}" y="{fy:.1f}" font-size="10.5" fill="{MUTED}" letter-spacing="1.1">'
                   f'{label} <tspan fill="{INK}" font-weight="700">{esc(val)}</tspan></text>')
        tx += 178
    lx = W - 176
    out.append(f'<text x="{lx}" y="{fy:.1f}" font-size="10.5" fill="{MUTED}" letter-spacing="1.1">Less</text>')
    for i, col in enumerate(LEVEL_COLORS[1:]):
        out.append(f'<rect x="{lx + 40 + i * 20}" y="{fy - 11}" width="14" height="14" rx="4" fill="{col}"/>')
    out.append(f'<text x="{lx + 124}" y="{fy:.1f}" font-size="10.5" fill="{MUTED}" letter-spacing="1.1">More</text>')

    css = f"""
  text {{ font-family: {FONT}; }}
  .draw {{ animation: draw 2.6s cubic-bezier(.4,.9,.4,1) both .2s; }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0 }} }}
  .shimmer {{ animation: shim 4.5s linear infinite 2.4s; }}
  @keyframes shim {{ from {{ stroke-dashoffset: 0 }} to {{ stroke-dashoffset: -1446 }} }}
  .scan, .scan2 {{ filter: drop-shadow(0 0 6px {VI}); }}
  .cell {{ animation: cell .5s cubic-bezier(.2,.8,.2,1) both; transform-box: fill-box; transform-origin: center; }}
  @keyframes cell {{ from {{ opacity: 0; transform: scale(.3) }} to {{ opacity: 1; transform: scale(1) }} }}
  .ping {{ animation: ping 2.4s ease-out infinite; transform-box: fill-box; transform-origin: center; }}
  @keyframes ping {{ 0% {{ transform: scale(.6); opacity: 1 }} 100% {{ transform: scale(1.9); opacity: 0 }} }}
"""
    defs = DEFS_COMMON + f"""
  <linearGradient id="wave" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{VI_L}" stop-opacity=".30"/>
    <stop offset=".55" stop-color="{BL_L}" stop-opacity=".16"/>
    <stop offset="1" stop-color="{CY_L}" stop-opacity=".04"/>
  </linearGradient>
"""
    return (svg_open(W, H, f"Animated contribution flow graph: {sm['total']} contributions over "
                           f"{sm['weeks']} weeks, {sm['active']} active days",
                     "KCN_LAB :: CONTRIBUTION FLOW")
            + f"<style>{css}</style>\n<defs>{defs}</defs>\n" + "\n".join(o for o in out if o) + "\n</svg>\n")


# ───────────────────────────── JSON PAYLOAD ───────────────────────────────
def build_payload(d: dict) -> dict:
    L = level_info(d)
    sm = summary(d)
    days = [{"d": x["date"], "c": x["count"], "l": x["level"], "w": x["weekday"]} for x in days_flat(d)]
    tot = sum(l[2] for l in d["languages"]) or 1
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user": {"login": d["login"], "name": d["name"], "followers": d["followers"],
                 "repos": d["repos"], "stars": d["stars"], "forks": d["forks"],
                 "created_at": d["created_at"], "demo": d["demo"]},
        "level": {"level": L["level"], "rank": L["rank"], "xp": L["xp"],
                  "progress": round(L["progress"], 4), "next": L["next"]},
        "stats": {"commits_year": d["commits_year"], "commits_all": d["commits_all"],
                  "prs": d["prs"], "issues": d["issues"], "contrib_all": d["contrib_all"],
                  "total_12m": d["total_last_year"]},
        "summary": sm,
        "years": [{"year": y, "total": v["total"], "commits": v["commits"]}
                  for y, v in sorted(d["years"].items())],
        "calendars": {str(y): {"total": sum(x["count"] for w in wks for x in w),
                               "weeks": [[{"d": x["date"], "c": x["count"], "l": x["level"],
                                           "w": x["weekday"]} for x in w] for w in wks]}
                      for y, wks in sorted(d.get("calendars", {}).items())},
        "languages": [{"name": n, "color": c or LANG_FALLBACK[i % len(LANG_FALLBACK)],
                       "size": s, "percent": round(100 * s / tot, 2)}
                      for i, (n, c, s) in enumerate(d["languages"][:10])],
        "days": days,
    }


# ───────────────────────────────── MAIN ───────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "KCN-369"))
    ap.add_argument("--out", default="profile")
    ap.add_argument("--data-out", default=os.path.join("docs", "data"),
                    help="folder for the interactive-viewer JSON payload")
    ap.add_argument("--demo", action="store_true", help="render with simulated data (no network)")
    args = ap.parse_args()

    if args.demo:
        data = demo(args.user)
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            print("error: set GITHUB_TOKEN (or use --demo)", file=sys.stderr)
            return 2
        data = fetch(args.user, token)

    os.makedirs(args.out, exist_ok=True)
    cards = [
        ("stats.svg", render_stats(data)),
        ("top-langs.svg", render_top_langs(data)),
        ("contrib3d.svg", render_contrib3d(data)),
        ("flow.svg", render_flow(data)),
    ]
    for name, svg in cards:
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"wrote {os.path.join(args.out, name)} ({len(svg) / 1024:.0f} KB)")

    if args.data_out:
        os.makedirs(args.data_out, exist_ok=True)
        path = os.path.join(args.data_out, "contrib.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(build_payload(data), fh, separators=(",", ":"))
        print(f"wrote {path} ({os.path.getsize(path) / 1024:.1f} KB)")

    L, sm = level_info(data), summary(data)
    print(f"level {L['level']} ({L['rank']}) · xp {L['xp']} · {sm['total']} contributions (12m) · "
          f"{sm['active']} active days · streak {sm['current_streak']}d")
    return 0


if __name__ == "__main__":
    sys.exit(main())
