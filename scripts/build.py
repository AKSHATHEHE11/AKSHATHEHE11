#!/usr/bin/env python3
"""Generates every SVG in assets/ for the profile README.

    python scripts/build.py

Edit the content below and re-run. Only the activity card pulls live data (GitHub API);
everything else is static. Standard library only. Logos: Simple Icons (CC0), embedded at build
time, so the README never depends on a third-party image service at render time.
"""
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USER = "AKSHATHEHE11"
OUT = Path(__file__).resolve().parent.parent / "assets"
ICON_URL = "https://cdn.jsdelivr.net/npm/simple-icons@16.37.0/icons/{}.svg"

TEXT, SOFT, MUTED, DIM = "#F3F6FC", "#C9D3EA", "#8D97AD", "#5B647A"
BLUE, VIOLET, CYAN, GREEN = "#4F7CFF", "#8B5CF6", "#22D3EE", "#34D399"
CHIP, CHIP_LINE, LINE = "#0E1526", "#1F2942", "#1C2540"

CSS = (
    ".s{font-family:Inter,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif}"
    ".m{font-family:'JetBrains Mono','SF Mono',Menlo,Consolas,'Liberation Mono',monospace}"
    ".blink{animation:blink 1.1s steps(1) infinite}"
    ".pulse{animation:pulse 2.4s ease-in-out infinite}"
    ".flow{stroke-dasharray:3 9;animation:flow 1.8s linear infinite}"
    "@keyframes blink{50%{opacity:0}}"
    "@keyframes pulse{50%{opacity:.25}}"
    "@keyframes flow{to{stroke-dashoffset:-24}}"
    "@media (prefers-reduced-motion:reduce){.blink,.pulse,.flow{animation:none}}"
)


def esc(s):
    return escape(str(s), {'"': "&quot;"})


def mono_w(s, size):
    # Monospace fallbacks all sit near 0.6em per glyph; 0.62 keeps chips from clipping.
    return len(s) * size * 0.62


def t(x, y, s, size=14, fill=TEXT, cls="s", weight=400, anchor="start", ls=0):
    extra = f' letter-spacing="{ls}"' if ls else ""
    return (f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def span(s, fill=None, **attrs):
    a = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    f = f' fill="{fill}"' if fill else ""
    return f"<tspan{f}{a}>{esc(s)}</tspan>"


def grad(id_, *stops, x1=0, y1=0, x2=1, y2=0, user=False):
    units = ' gradientUnits="userSpaceOnUse"' if user else ""
    st = "".join(f'<stop offset="{s[0]}" stop-color="{s[1]}" stop-opacity="{s[2] if len(s) > 2 else 1}"/>'
                 for s in stops)
    return f'<linearGradient id="{id_}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"{units}>{st}</linearGradient>'


ACCENT = ((0, "#60A5FA"), (0.55, "#A78BFA"), (1, CYAN))


def doc(w, h, title, defs, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(title)}">\n<title>{esc(title)}</title>\n<style>{CSS}</style>\n'
            f"<defs>{defs}</defs>\n{body}\n</svg>\n")


def panel(w, h, glows, r=18, grid=True):
    """Dark card: gradient base, faded grid, soft glows, hairline border, lit top edge."""
    defs = [
        grad("bg", (0, "#050505"), (0.55, "#080B12"), (1, "#0B1020"), x2=1, y2=1),
        grad("edge", (0, BLUE, 0), (0.3, BLUE), (0.7, VIOLET), (1, VIOLET, 0)),
        f'<clipPath id="clip"><rect width="{w}" height="{h}" rx="{r}"/></clipPath>',
        '<pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">'
        '<path d="M28 0H0V28" fill="none" stroke="#FFFFFF" stroke-opacity=".05"/></pattern>',
        '<radialGradient id="gfade"><stop offset="0" stop-color="#FFF"/>'
        '<stop offset="1" stop-color="#FFF" stop-opacity="0"/></radialGradient>',
        f'<mask id="gmask"><rect width="{w}" height="{h}" fill="url(#gfade)"/></mask>',
    ]
    body = ['<g clip-path="url(#clip)">', f'<rect width="{w}" height="{h}" fill="url(#bg)"/>']
    if grid:
        body.append(f'<rect width="{w}" height="{h}" fill="url(#grid)" mask="url(#gmask)"/>')
    for i, (cx, cy, rx, ry, c, o) in enumerate(glows):
        defs.append(f'<radialGradient id="glow{i}"><stop offset="0" stop-color="{c}" stop-opacity="{o}"/>'
                    f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
        body.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#glow{i})"/>')
    body.append(f'<rect x="{r}" y="0" width="{w - 2 * r}" height="1" fill="url(#edge)" opacity=".7"/>')
    body.append("</g>")
    body.append(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{r}" fill="none" stroke="{LINE}"/>')
    return "".join(defs), "\n".join(body)


def hline(x, y, w, opacity=0.07):
    return f'<rect x="{x}" y="{y}" width="{w}" height="1" fill="#FFFFFF" opacity="{opacity}"/>'


def arrow(x, y, color, size=9):
    return (f'<path d="M{x} {y + size}L{x + size} {y}M{x + 2.5} {y}H{x + size}V{y + size - 2.5}" '
            f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>')


# ───────────────────────────── content ─────────────────────────────

STACK = [  # (group, [(label, simple-icons slug or None)])
    ("Languages", [("C", "c"), ("C++", "cplusplus"), ("Java", "openjdk"), ("JavaScript", "javascript"),
                   ("TypeScript", "typescript"), ("Python", "python")]),
    ("Frontend", [("React", "react"), ("Next.js", "nextdotjs"), ("Redux Toolkit", "redux"),
                  ("Tailwind CSS", "tailwindcss")]),
    ("Backend", [("Node.js", "nodedotjs"), ("Express.js", "express"), ("FastAPI", "fastapi"),
                 ("REST APIs", None), ("JWT", "jsonwebtokens"), ("Bcrypt", None), ("RBAC", None)]),
    ("Database", [("MongoDB", "mongodb"), ("PostgreSQL", "postgresql"), ("MySQL", "mysql"),
                  ("Redis", "redis")]),
    ("Cloud & Deploy", [("AWS", None), ("Vercel", "vercel"), ("Cloudinary", "cloudinary"),
                        ("Git", "git"), ("GitHub", "github")]),
    ("AI / ML", [("Scikit-learn", "scikitlearn"), ("Pandas", "pandas"), ("NumPy", "numpy"),
                 ("XGBoost", None), ("YOLOv8", "ultralytics"), ("OpenCV", "opencv"), ("OpenAI API", None)]),
    ("Integrations", [("Razorpay", "razorpay"), ("Webhooks", None), ("Shiprocket", None),
                      ("Shipmozo", None), ("Meta Pixel", "meta"), ("Google Analytics", "googleanalytics"),
                      ("Google Tag Manager", "googletagmanager")]),
]

PROJECTS = [
    dict(slug="credwise", idx="P/01", tag="AI · FINTECH", name="CredWise AI", accent=VIOLET, live=False,
         desc=["Credit-risk scoring platform. An XGBoost model",
               "trained on 150K borrowers scores applicants and",
               "explains every score with SHAP reasons."],
         proof="AUC 0.871 on 30K unseen borrowers",
         stack=["XGBoost", "FastAPI", "React", "TypeScript", "PostgreSQL"]),
    dict(slug="taskflow", idx="P/02", tag="SECURITY · AUTH", name="TaskFlow Auth", accent=BLUE, live=True,
         desc=["MERN authentication module: two-token JWT,",
               "refresh-token rotation, SHA-256 hashed tokens",
               "and reuse-attack detection."],
         proof="session console · Axios auto-refresh",
         stack=["React", "Node.js", "Express", "MongoDB", "Jest"]),
    dict(slug="leaddesk", idx="P/03", tag="FULL-STACK · CRM", name="LeadDesk Mini", accent=CYAN, live=True,
         desc=["Lead-management CRM for small sales teams:",
               "capture, assign and track leads through a",
               "six-stage pipeline with role-based access."],
         proof="Vercel + Render + MongoDB Atlas",
         stack=["React", "Express", "MongoDB", "Tailwind", "RBAC"]),
    dict(slug="agent", idx="P/04", tag="AI · AGENTS", name="AI Coding Agent", accent="#2DD4BF", live=False,
         desc=["Framework-free autonomous agent that explores",
               "a codebase, plans, edits files through LLM tool",
               "calls and verifies its work in a sandbox."],
         proof="explore → plan → execute → verify",
         stack=["Python", "OpenAI API", "Pydantic", "Tool calling"]),
]

SECTIONS = {
    "02": ("ABOUT", "the short version"),
    "03": ("STACK", "tools I ship with"),
    "04": ("EXPERIENCE", "where I work"),
    "05": ("NOW BUILDING", "flagship"),
    "06": ("SELECTED WORK", "public repositories"),
    "07": ("HIGHLIGHTS", "numbers, not adjectives"),
    "08": ("ACTIVITY", "synced from the GitHub API"),
    "09": ("CONNECT", "let's talk"),
}


# ───────────────────────────── components ─────────────────────────────

def hero():
    w, h = 1000, 420
    d, b = panel(w, h, [(150, 30, 400, 230, VIOLET, .30), (860, 50, 380, 230, BLUE, .32),
                        (500, 480, 460, 170, CYAN, .16)])
    d += grad("acc", *ACCENT, x1=500, x2=880, user=True)
    d += grad("mono", (0, BLUE), (1, VIOLET), x2=1, y2=1)
    pill = "CURRENTLY AT IMPERIAL TECH INNOVATIONS"
    pw = mono_w("● " + pill, 12) + 44
    stack = ["React", "Next.js", "Node.js", "AWS", "AI/ML"]
    stack_line = "".join((span("  •  ", BLUE) if i else "") + span(s, SOFT) for i, s in enumerate(stack))
    parts = [
        b,
        f'<rect x="40" y="28" width="30" height="30" rx="8" fill="{CHIP}" stroke="url(#mono)"/>',
        t(55, 48, "AA", 12, TEXT, "m", 700, "middle"),
        t(84, 48, f"github.com/{USER}", 12, MUTED, "m"),
        t(960, 48, "01 — PROFILE", 12, DIM, "m", anchor="end", ls=1),
        hline(40, 78, 920, .06),
        f'<rect x="{500 - pw / 2}" y="104" width="{pw}" height="32" rx="16" fill="{CHIP}" '
        f'fill-opacity=".85" stroke="#26304A"/>',
        f'<text x="500" y="125" class="m" font-size="12" text-anchor="middle" letter-spacing=".5">'
        f'{span("●", GREEN)} {span(pill, SOFT)}</text>',
        f'<text x="500" y="222" class="s" font-size="80" font-weight="800" text-anchor="middle" '
        f'letter-spacing="-1.5">{span("AKSHAT ", TEXT)}{span("AGRAWAL", "url(#acc)")}</text>',
        t(500, 268, "Full-Stack Developer", 26, TEXT, weight=600, anchor="middle"),
        f'<text x="500" y="306" class="m" font-size="15" text-anchor="middle">{stack_line}</text>',
        t(500, 344, "Building scalable web applications and AI-powered products.", 17, MUTED, anchor="middle"),
        hline(40, 370, 920, .06),
        f'<text x="40" y="398" class="m" font-size="11" letter-spacing="1">'
        f'{span("EDU", DIM)}{span("B.TECH CSE · 2027", MUTED, dx=10)}</text>',
        t(500, 398, "FULL-STACK — CLOUD — AI/ML — PRODUCT", 11, DIM, "m", anchor="middle", ls=1),
        f'<text x="960" y="398" class="m" font-size="11" text-anchor="end" letter-spacing="1">'
        f'{span("NOW", DIM)}{span("BUILDING DECISIONOS AI", MUTED, dx=10)}</text>',
    ]
    return doc(w, h, "Akshat Agrawal — Full-Stack Developer", d, "\n".join(parts))


def button(label, primary):
    w, h = 176, 48
    if primary:
        d = grad("fill", (0, "#3B6BFF"), (1, "#7C4DFF"), x2=1, y2=1)
        shape = f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{h / 2 - 1}" fill="url(#fill)"/>'
        ink = "#FFFFFF"
    else:
        d = grad("stroke", (0, BLUE), (1, VIOLET), x2=1, y2=1)
        shape = (f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{h / 2 - 1}" fill="#0B1020" '
                 f'stroke="url(#stroke)" stroke-width="1.2"/>')
        ink = TEXT
    body = shape + t((w - 18) / 2, 30, label, 15, ink, weight=600, anchor="middle") + arrow(w - 40, 19.5, ink)
    # Transparent top margin: GitHub's sanitizer leaves no reliable way to space images apart.
    pad = 20
    return doc(w, h + pad, label, d, f'<g transform="translate(0 {pad})">{body}</g>')


def section(num, title, note):
    w, h = 1000, 64
    d = grad("hg", (0, BLUE), (1, VIOLET), x1=40, x2=360, user=True)
    d += grad("rule", (0, BLUE), (0.45, VIOLET), (1, VIOLET, 0))
    body = "\n".join([
        f'<text x="0" y="36"><tspan class="m" font-size="14" font-weight="700" fill="#2F81F7">{num}</tspan>'
        f'<tspan class="m" font-size="14" fill="#6E7781" dx="10">/</tspan>'
        f'<tspan class="s" font-size="24" font-weight="800" fill="url(#hg)" dx="12" letter-spacing=".6">'
        f"{esc(title)}</tspan></text>",
        t(1000, 36, f"// {note}", 12, "#6E7781", "m", anchor="end"),
        '<rect x="0" y="52" width="1000" height="1.5" fill="url(#rule)" opacity=".55"/>',
    ])
    return doc(w, h, f"{num} — {title.title()}", d, body)


def about():
    w, h = 360, 262
    d, b = panel(w, h, [(340, 0, 240, 150, VIOLET, .22), (0, 262, 200, 120, BLUE, .14)], r=14, grid=False)
    d += grad("val", (0, "#93C5FD"), (1, "#C4B5FD"), x1=104, x2=300, user=True)
    rows = [("name", "Akshat Agrawal"), ("role", "Full-Stack Developer"), ("at", "Imperial Tech Innovations"),
            ("focus", "web · cloud · ai/ml"), ("edu", "B.Tech CSE · 2027"), ("building", "DecisionOS AI")]
    parts = [b] + [f'<circle cx="{20 + 15 * i}" cy="20" r="4.5" fill="#232C42"/>' for i in range(3)]
    parts += [t(w / 2, 24, "~/akshat — whoami", 11, DIM, "m", anchor="middle"), hline(0, 40, w, .07)]
    parts.append(f'<text x="22" y="70" class="m" font-size="13">{span("$", CYAN)} {span("whoami", TEXT)}</text>')
    for i, (k, v) in enumerate(rows):
        y = 98 + i * 24
        fill = "url(#val)" if k == "building" else SOFT
        parts += [t(22, y, k, 13, "#6B7593", "m"), t(104, y, v, 13, fill, "m", 600 if k == "building" else 400)]
    y = 98 + len(rows) * 24 + 4
    parts += [t(22, y, "$", 13, CYAN, "m"), f'<rect class="blink" x="36" y="{y - 11}" width="8" height="14" fill="{SOFT}"/>']
    return doc(w, h, "whoami — Akshat Agrawal", d, "\n".join(parts))


def stack(icons):
    w, x0, x_max = 1000, 236, 960
    chip_h, gap, row_pad = 34, 8, 14
    accents = [BLUE, VIOLET, CYAN]
    parts, y = [], 36
    for gi, (group, items) in enumerate(STACK):
        accent = accents[gi % 3]
        x, top = x0, y
        chips = []
        for label, slug in items:
            cw = 38 + mono_w(label, 13) + 14
            if x + cw > x_max:
                x, y = x0, y + chip_h + gap
            chips.append(f'<rect x="{x}" y="{y}" width="{cw:.0f}" height="{chip_h}" rx="9" fill="{CHIP}" stroke="{CHIP_LINE}"/>')
            if slug:
                chips.append(f'<path transform="translate({x + 12} {y + 9}) scale({16 / 24})" fill="#AEB8D0" d="{icons[slug]}"/>')
            else:
                chips.append(f'<rect x="{x + 16}" y="{y + 13}" width="8" height="8" rx="2" fill="{accent}" opacity=".85"/>')
            chips.append(t(x + 38, y + 22, label, 13, SOFT, "m"))
            x += cw + gap
        bottom = y + chip_h
        mid = (top + bottom) / 2
        parts.append(f'<rect x="40" y="{top + 4}" width="2" height="{bottom - top - 8}" rx="1" fill="{accent}"/>')
        parts.append(t(56, mid - 3, f"{gi + 1:02d}", 11, DIM, "m", ls=1))
        parts.append(t(56, mid + 15, group, 16, TEXT, weight=700))
        parts += chips
        y = bottom + row_pad
        if gi < len(STACK) - 1:
            parts.append(hline(40, y, 920, .05))
            y += row_pad
    h = y + 22
    d, b = panel(w, h, [(1000, 0, 420, 260, VIOLET, .16), (0, h, 420, 260, BLUE, .14)])
    return doc(w, h, "Tech stack", d, b + "\n" + "\n".join(parts))


def now_building():
    w, h = 1000, 340
    d, b = panel(w, h, [(120, 40, 420, 240, VIOLET, .30), (800, 170, 360, 260, CYAN, .16),
                        (900, 0, 300, 160, BLUE, .22)])
    d += grad("acc", *ACCENT, x1=300, x2=470, user=True)
    d += grad("link", (0, "#FFFFFF", 0), (1, CYAN), x1=640, x2=790, user=True)
    hub, out = (790, 170), (905, 170)
    ins = [(640, 70 + i * 50) for i in range(5)]
    viz = [f'<circle cx="{hub[0]}" cy="{hub[1]}" r="{r}" fill="none" stroke="#FFFFFF" stroke-opacity=".06"/>'
           for r in (34, 62, 92)]
    for (x, y) in ins:
        c = f"M{x} {y}C{x + 80} {y} {hub[0] - 80} {hub[1]} {hub[0] - 10} {hub[1]}"
        viz += [f'<path d="{c}" fill="none" stroke="#FFFFFF" stroke-opacity=".10"/>',
                f'<path class="flow" d="{c}" fill="none" stroke="url(#link)" stroke-width="1.4"/>',
                f'<circle cx="{x}" cy="{y}" r="5" fill="#0B1020" stroke="#3A4766"/>']
    viz += [
        f'<circle cx="{hub[0]}" cy="{hub[1]}" r="22" fill="{VIOLET}" opacity=".18" class="pulse"/>',
        f'<circle cx="{hub[0]}" cy="{hub[1]}" r="11" fill="#0B1020" stroke="url(#acc)" stroke-width="2"/>',
        f'<circle cx="{hub[0]}" cy="{hub[1]}" r="4" fill="{TEXT}"/>',
        f'<path class="flow" d="M{hub[0] + 12} {hub[1]}H{out[0] - 6}" stroke="{CYAN}" stroke-width="1.4"/>',
        f'<rect x="{out[0] - 6}" y="{out[1] - 15}" width="66" height="30" rx="8" fill="{CHIP}" stroke="{CYAN}" stroke-opacity=".6"/>',
        t(out[0] + 27, out[1] + 4, "decide", 11, CYAN, "m", anchor="middle"),
    ]
    tw = mono_w("NOW BUILDING", 11) + 12 + 34
    parts = [
        b,
        f'<rect x="48" y="44" width="{tw}" height="28" rx="14" fill="{CHIP}" stroke="#26304A"/>',
        f'<circle class="pulse" cx="66" cy="58" r="4" fill="{GREEN}"/>',
        t(78, 62, "NOW BUILDING", 11, SOFT, "m", ls=1),
        f'<text x="46" y="138" class="s" font-size="54" font-weight="800" letter-spacing="-1">'
        f'{span("DecisionOS", TEXT)}{span(" AI", "url(#acc)")}</text>',
        t(48, 180, "An AI-powered business operating system —", 18, SOFT),
        t(48, 206, "designed to help businesses make better", 18, SOFT),
        t(48, 232, "decisions using AI.", 18, SOFT),
        hline(48, 262, 480, .07),
        f'<text x="48" y="294" class="m" font-size="11" letter-spacing="1">{span("STATUS", DIM)}'
        f'{span("IN DEVELOPMENT", MUTED, dx=10)}{span("CATEGORY", DIM, dx=36)}'
        f'{span("AI · BUSINESS SOFTWARE", MUTED, dx=10)}</text>',
    ] + viz
    return doc(w, h, "Now building — DecisionOS AI", d, "\n".join(parts))


def project(p):
    w, h = 480, 300
    a = p["accent"]
    d, b = panel(w, h, [(w, 0, 300, 200, a, .30), (0, h, 260, 160, a, .10)], r=16)
    d += grad("name", (0, TEXT), (1, SOFT), x2=0, y2=1)
    status = ("LIVE", GREEN) if p["live"] else ("SOURCE", MUTED)
    pulse = ' class="pulse"' if p["live"] else ""
    sw = mono_w(status[0], 10) + 30
    parts = [
        b,
        t(28, 40, p["idx"], 11, a, "m", 700, ls=1),
        t(28 + mono_w(p["idx"], 11) + 14, 40, p["tag"], 11, DIM, "m", ls=1),
        f'<rect x="{w - 28 - sw}" y="25" width="{sw}" height="22" rx="11" fill="{CHIP}" stroke="#26304A"/>',
        f'<circle cx="{w - 28 - sw + 12}" cy="36" r="3" fill="{status[1]}"{pulse}/>',
        t(w - 28 - sw + 21, 40, status[0], 10, SOFT, "m", ls=1),
        t(28, 92, p["name"], 30, "url(#name)", weight=800),
    ]
    parts += [t(28, 126 + i * 22, line, 14.5, MUTED) for i, line in enumerate(p["desc"])]
    parts += [f'<rect x="28" y="196" width="2" height="16" rx="1" fill="{a}"/>',
              t(38, 209, p["proof"], 12, SOFT, "m")]
    x = 28
    for s in p["stack"]:
        cw = mono_w(s, 11) + 20
        parts += [f'<rect x="{x}" y="240" width="{cw:.0f}" height="26" rx="7" fill="{CHIP}" stroke="{CHIP_LINE}"/>',
                  t(x + 10, 257, s, 11, SOFT, "m")]
        x += cw + 6
    return doc(w, h, f'{p["name"]} — {" ".join(p["desc"])}', d, "\n".join(parts))


def highlights():
    w, h = 1000, 190
    d, b = panel(w, h, [(160, 0, 300, 160, VIOLET, .22), (840, 190, 320, 160, BLUE, .22)])
    d += grad("num", (0, "#93C5FD"), (1, "#C4B5FD"), x2=1, y2=1)
    tiles = [("0.871", "Test AUC — CredWise AI", "ON 30K UNSEEN BORROWERS"),
             ("5", "Client web properties", "CONTRIBUTED TO AT IMPERIAL"),
             ("2", "Live full-stack apps", "TASKFLOW AUTH · LEADDESK MINI")]
    col = w / len(tiles)
    parts = [b]
    for i, (num, label, sub) in enumerate(tiles):
        x = i * col + 40
        if i:
            parts.append(f'<rect x="{i * col}" y="36" width="1" height="{h - 72}" fill="#FFFFFF" opacity=".07"/>')
        parts += [t(x, 92, num, 54, "url(#num)", weight=800, ls=-1), t(x, 126, label, 16, TEXT, weight=600),
                  t(x, 152, sub, 11, DIM, "m", ls=.5)]
    return doc(w, h, "Highlights: 0.871 test AUC on CredWise AI; 5 client web properties at Imperial; 2 live full-stack apps",
               d, "\n".join(parts))


def fetch(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-profile-build"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def activity():
    token = os.environ.get("GITHUB_TOKEN")
    api = "https://api.github.com"
    repos = [r for r in json.loads(fetch(f"{api}/users/{USER}/repos?per_page=100&type=owner", token))
             if not r["fork"] and r["name"].lower() != USER.lower()]  # skip this profile repo
    langs = {}
    for r in repos:
        if r["size"]:
            for k, v in json.loads(fetch(f"{api}/repos/{USER}/{r['name']}/languages", token)).items():
                langs[k] = langs.get(k, 0) + v
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])
    shown = top[:5] + ([("Other", sum(v for _, v in top[5:]))] if len(top) > 5 else [])
    recent = sorted((r for r in repos if r["size"]), key=lambda r: r["pushed_at"], reverse=True)[:3]
    live = sum(1 for r in repos if r.get("homepage"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    w, h = 1000, 280
    d, b = panel(w, h, [(0, 0, 360, 200, BLUE, .22), (1000, 280, 380, 200, VIOLET, .20)])
    d += grad("num", (0, "#93C5FD"), (1, "#C4B5FD"), x2=1, y2=1)
    parts = [b, t(40, 46, "PUBLIC FOOTPRINT", 11, DIM, "m", ls=1),
             t(960, 46, f"SYNCED {today} · GITHUB API", 11, DIM, "m", anchor="end", ls=1)]
    for i, (n, label) in enumerate([(len(repos), "PUBLIC REPOS"), (live, "LIVE DEMOS"), (len(langs), "LANGUAGES")]):
        x = 40 + i * 170
        parts += [t(x, 112, n, 48, "url(#num)", weight=800), t(x, 136, label, 11, MUTED, "m", ls=1)]
    parts += [f'<rect x="590" y="66" width="1" height="80" fill="#FFFFFF" opacity=".07"/>',
              t(620, 78, "RECENTLY PUSHED", 11, DIM, "m", ls=1)]
    for i, r in enumerate(recent):
        y = 104 + i * 22
        parts += [t(620, y, r["name"], 13, SOFT, "m"), t(960, y, r["pushed_at"][:10], 12, DIM, "m", anchor="end")]
    parts += [hline(40, 168, 920, .07), t(40, 198, "LANGUAGES BY CODE SIZE", 11, DIM, "m", ls=1)]
    colors = [BLUE, VIOLET, CYAN, "#2DD4BF", "#64748B", "#3F4A61"]
    x, bar_w = 40.0, 920
    parts.append(f'<clipPath id="bar"><rect x="40" y="212" width="{bar_w}" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">')
    for i, (_, v) in enumerate(shown):
        seg = bar_w * v / total
        parts.append(f'<rect x="{x:.1f}" y="212" width="{seg + .5:.1f}" height="10" fill="{colors[i]}"/>')
        x += seg
    parts.append("</g>")
    x = 40
    for i, (k, v) in enumerate(shown):
        label = f"{k} {100 * v / total:.1f}%"
        parts += [f'<rect x="{x}" y="243" width="8" height="8" rx="2" fill="{colors[i]}"/>',
                  t(x + 14, 251, label, 12, SOFT, "m")]
        x += 14 + mono_w(label, 12) + 26
    title = (f"GitHub activity: {len(repos)} public repos, {live} live demos; languages "
             + ", ".join(f"{k} {100 * v / total:.0f}%" for k, v in shown))
    return doc(w, h, title, d, "\n".join(parts))


def connect():
    w, h = 1000, 230
    d, b = panel(w, h, [(500, 0, 520, 200, VIOLET, .26), (500, 230, 520, 160, BLUE, .22)])
    d += grad("acc", *ACCENT, x1=300, x2=720, user=True)
    parts = [
        b,
        f'<text x="500" y="98" class="s" font-size="40" font-weight="800" text-anchor="middle" letter-spacing="-.5">'
        f'{span("Building something ", TEXT)}{span("interesting?", "url(#acc)")}</text>',
        t(500, 136, "Let's talk about full-stack products, cloud and applied AI.", 17, MUTED, anchor="middle"),
        hline(40, 172, 920, .06),
        t(500, 202, "AKSHAT AGRAWAL  ·  FULL-STACK DEVELOPER  ·  B.TECH CSE 2027", 11, DIM, "m", anchor="middle", ls=1),
    ]
    return doc(w, h, "Building something interesting? Let's talk.", d, "\n".join(parts))


# ───────────────────────────── build ─────────────────────────────

def main():
    OUT.mkdir(exist_ok=True)
    slugs = {s for _, items in STACK for _, s in items if s}
    icons = {s: re.search(r' d="([^"]+)"', fetch(ICON_URL.format(s))).group(1) for s in sorted(slugs)}
    files = {
        "hero.svg": hero(),
        "btn-linkedin.svg": button("LinkedIn", True),
        "btn-github.svg": button("GitHub", False),
        "about.svg": about(),
        "stack.svg": stack(icons),
        "now-building.svg": now_building(),
        "highlights.svg": highlights(),
        "activity.svg": activity(),
        "connect.svg": connect(),
        **{f"sec-{n}.svg": section(n, *v) for n, v in SECTIONS.items()},
        **{f'project-{p["slug"]}.svg': project(p) for p in PROJECTS},
    }
    for name, svg in files.items():
        ET.fromstring(svg)  # malformed SVG renders as a broken image on GitHub: fail the build instead
        (OUT / name).write_text(svg, encoding="utf-8", newline="\n")
    print(f"wrote {len(files)} files to {OUT}")


if __name__ == "__main__":
    main()
