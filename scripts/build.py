#!/usr/bin/env python3
"""Generates every SVG in assets/ for the profile README.

    python scripts/build.py

Each card is drawn twice, in a light and a dark version; the README shows the one that matches the
viewer's GitHub theme. Edit the content below and re-run. Only the activity card pulls live data
(GitHub API, cached in scripts/.github-cache.json); everything else is static. Standard library only.

Two things are fetched at build time and inlined, so a reader never depends on a third-party
service: the display typeface (Space Grotesk, OFL) as a base64 woff2, embedded only in the cards
that set type in it.

Motion: the cards use SMIL (<animate>). Browsers run declarative animation in SVGs loaded as
<img>, which is how GitHub renders them, so the scanlines and pulses play on the profile.
"""
import base64
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USER = "AKSHATHEHE11"
OUT = Path(__file__).resolve().parent.parent / "assets"
CACHE = Path(__file__).resolve().parent / ".github-cache.json"  # last good API responses (gitignored)
FONT_URL = ("https://cdn.jsdelivr.net/npm/@fontsource/space-grotesk@5.2.10/files/"
            "space-grotesk-latin-700-normal.woff2")

# One system, two themes: a near-black console and its daylight twin. The accent is a ramp,
# cyan → blue → violet, used for edges, rules and the headline ink.
# accent_ink is the accent tone that still passes contrast as small text on the card.
THEMES = {
    "light": dict(
        bg=("#FFFFFF", "#F4F8FF", "#EAF0FE"), card="#F7FAFF", line="#D3DEF2", rule="#E3EAF7",
        text="#0A1020", soft="#303E59", muted="#4F5E79", dim="#6C7B94",
        accent="#0891B2", accent_ink="#0E7490", live="#15803D",
        acc=("#0891B2", "#2563EB", "#7C3AED"), ink=("#0E7490", "#1D4ED8", "#7C3AED"),
        glow=(("#22D3EE", .18), ("#A855F7", .14)), grid=("#0A1020", ".055"), bracket=("#0891B2", ".5"),
        chip="#EDF3FD", chip_line="#D7E2F5",
        mark="#0A1020", mark_line="#0A1020",
        btn_ink="#FFFFFF", btn2_line="#C3D1E8", btn2_ink="#0A1020",
        bars=["#0891B2", "#2563EB", "#7C3AED", "#0F766E", "#64748B", "#A3B1C6"],
    ),
    "dark": dict(
        bg=("#04060C", "#070C16", "#0A1024"), card="#070C16", line="#1A2437", rule="#1C2740",
        text="#EAF1FF", soft="#B6C2D9", muted="#8494AE", dim="#5A6679",
        accent="#22D3EE", accent_ink="#7DD8F0", live="#34D399",
        acc=("#22D3EE", "#4C7DFF", "#A855F7"), ink=("#22D3EE", "#CFE0FF", "#A855F7"),
        glow=(("#4C7DFF", .20), ("#A855F7", .14)), grid=("#FFFFFF", ".04"), bracket=("#22D3EE", ".45"),
        chip="#0A111C", chip_line="#1C2740",
        mark="#0A1024", mark_line="#2A3650",
        btn_ink="#FFFFFF", btn2_line="#2A3650", btn2_ink="#E6ECF7",
        bars=["#22D3EE", "#4C7DFF", "#A855F7", "#2DD4BF", "#64748B", "#3F4A61"],
    ),
}

SANS = "Inter,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono','SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
DISPLAY = "'SpaceGrotesk','Space Grotesk',Inter,'Segoe UI',system-ui,sans-serif"
CSS = f".s{{font-family:{SANS}}}.m{{font-family:{MONO}}}.d{{font-family:{DISPLAY}}}"
FONT_B64 = ""  # filled in main(); empty falls back to whatever the reader has installed


def esc(s):
    return escape(str(s), {'"': "&quot;"})


def mono_w(s, size, ls=0):
    # Monospace fallbacks all sit near 0.6em per glyph; 0.62 keeps boxes from clipping.
    return len(s) * (size * 0.62 + ls)


def t(x, y, s, size, fill, cls="s", weight=400, anchor="start", ls=0):
    extra = f' letter-spacing="{ls}"' if ls else ""
    return (f'<text x="{x:.1f}" y="{y}" class="{cls}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def span(s, fill, **attrs):
    a = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<tspan fill="{fill}"{a}>{esc(s)}</tspan>'


def rect(x, y, w, h, fill, rx=0, extra=""):
    return f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{rx}" fill="{fill}"{extra}/>'


def grad(id_, *stops, x1=0, y1=0, x2=1, y2=0):
    st = "".join(f'<stop offset="{s[0]}" stop-color="{s[1]}" stop-opacity="{s[2] if len(s) > 2 else 1}"/>'
                 for s in stops)
    return f'<linearGradient id="{id_}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{st}</linearGradient>'


def arrow(x, y, color, size=9):
    return (f'<path d="M{x} {y + size}L{x + size} {y}M{x + 2.5} {y}H{x + size}V{y + size - 2.5}" '
            f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>')


def anim(attr, values, dur, begin=0):
    return (f'<animate attributeName="{attr}" values="{values}" dur="{dur}s" '
            f'begin="{begin}s" repeatCount="indefinite"/>')


def pulse_ring(cx, cy, r0, r1, color, dur=3.2, begin=0):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r0}" fill="none" stroke="{color}" stroke-width="1.2">'
            f"{anim('r', f'{r0};{r1}', dur, begin)}{anim('opacity', '.55;0', dur, begin)}</circle>")


def live_dot(cx, cy, color, r=4):
    """Breathing status dot: a halo pulsing out from behind a solid core."""
    return (f'<circle cx="{cx:.1f}" cy="{cy}" r="{r}" fill="{color}" opacity=".35">'
            f"{anim('r', f'{r};{r + 5};{r}', 2.4)}{anim('opacity', '.35;0;.35', 2.4)}</circle>"
            f'<circle cx="{cx:.1f}" cy="{cy}" r="{r}" fill="{color}"/>')


def corners(P, w, h, size=13, inset=11):
    """HUD corner brackets — the cheapest way to make a card read as an instrument panel."""
    c, op = P["bracket"]
    s, i = size, inset
    d = [f"M{i} {i + s}V{i}H{i + s}", f"M{w - i - s} {i}H{w - i}V{i + s}",
         f"M{w - i} {h - i - s}V{h - i}H{w - i - s}", f"M{i + s} {h - i}H{i}V{h - i - s}"]
    return "".join(f'<path d="{p}" fill="none" stroke="{c}" stroke-width="1.4" '
                   f'stroke-linecap="round" opacity="{op}"/>' for p in d)


def doc(w, h, title, body, defs=""):
    face = (f"@font-face{{font-family:'SpaceGrotesk';font-style:normal;font-weight:700;"
            f"src:url(data:font/woff2;base64,{FONT_B64}) format('woff2')}}"
            if FONT_B64 and 'class="d"' in body else "")  # inline the font only where it is used
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(title)}">\n<title>{esc(title)}</title>\n'
            f"<style>{face}{CSS}</style>\n<defs>{defs}</defs>\n{body}\n</svg>\n")


def card(P, w, h, r=16, bar=False, grid=False, scan=0, bracket=False, glows=()):
    """Console card: graded surface, optional grid and glows, hairline border, lit top edge.

    scan: seconds for one sweep of the scanline (0 = none). Returns (defs, body-parts).
    """
    a0, a1, a2 = P["acc"]
    defs = [grad("bg", (0, P["bg"][0]), (0.55, P["bg"][1]), (1, P["bg"][2]), x2=1, y2=1),
            grad("acc", (0, a0), (0.5, a1), (1, a2)),
            grad("edge", (0, a0, 0), (0.28, a0), (0.72, a2), (1, a2, 0)),
            f'<clipPath id="card"><rect width="{w}" height="{h}" rx="{r}"/></clipPath>']
    body = ['<g clip-path="url(#card)">', rect(0, 0, w, h, "url(#bg)")]
    if grid:
        gc, go = P["grid"]
        defs += [f'<pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">'
                 f'<path d="M30 0H0V30" fill="none" stroke="{gc}" stroke-opacity="{go}"/></pattern>',
                 '<radialGradient id="gfade"><stop offset="0" stop-color="#FFF"/>'
                 '<stop offset="1" stop-color="#FFF" stop-opacity="0"/></radialGradient>',
                 f'<mask id="gmask"><rect width="{w}" height="{h}" fill="url(#gfade)"/></mask>']
        body.append(f'<rect width="{w}" height="{h}" fill="url(#grid)" mask="url(#gmask)"/>')
    for i, (cx, cy, rx, ry, which) in enumerate(glows):
        c, o = P["glow"][which]
        defs.append(f'<radialGradient id="glow{i}"><stop offset="0" stop-color="{c}" stop-opacity="{o}"/>'
                    f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
        body.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#glow{i})"/>')
    if scan:
        defs.append(grad("scan", (0, a0, 0), (0.5, a0, 0.55), (1, a0, 0)))
        body.append(f'<rect x="0" y="0" width="{w}" height="1.5" fill="url(#scan)" opacity="0">'
                    f"{anim('y', f'-6;{h + 6}', scan)}{anim('opacity', '0;.9;.9;0', scan)}</rect>")
    if bar:
        body.append(rect(0, 0, 5, h, "url(#accv)"))
        defs.append(grad("accv", (0, a0), (0.5, a1), (1, a2), x2=0, y2=1))
    body.append(rect(r, 0, w - 2 * r, 1, "url(#edge)", extra=' opacity=".65"'))
    if bracket:
        body.append(corners(P, w, h))
    body.append("</g>")
    body.append(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{r}" fill="none" stroke="{P["line"]}"/>')
    return "".join(defs), body


def mark(P, x, y, size):
    """The [A] mark from the AKSHAT/OS identity, in the accent ramp."""
    k = size / 64
    a0, _, a2 = P["acc"]
    return (f'<g transform="translate({x} {y})">'
            f'<rect width="{size}" height="{size}" rx="{size * 0.22:.1f}" fill="{P["mark"]}" '
            f'stroke="{P["mark_line"]}"/>'
            f'<rect width="{size}" height="{size}" rx="{size * 0.22:.1f}" fill="none" stroke="url(#acc)" '
            f'stroke-opacity=".55"/>'
            f'<g transform="scale({k:.4f})" fill="none" stroke-width="4.5" stroke-linecap="square">'
            f'<path d="M19 15h-6v34h6" stroke="{a0}"/><path d="M45 15h6v34h-6" stroke="{a2}"/>'
            f'<path d="M24.5 44 32 20l7.5 24M27.4 36h9.2" stroke="#F2F6FF" stroke-linejoin="round"/></g></g>')


# ───────────────────────────── content ─────────────────────────────

FACTS = [("CURRENTLY", "Imperial Tech Innovations"), ("EDUCATION", "B.Tech CSE · 2027"),
         ("BUILDING", "DecisionOS AI")]

PROJECTS = [
    dict(slug="credwise", tag="AI · FINTECH", name="CredWise AI", live=False,
         desc=["Credit-risk scoring platform. An XGBoost model",
               "trained on 150K borrowers scores applicants and",
               "explains every score with SHAP reasons."],
         proof="AUC 0.871 on 30K unseen borrowers",
         stack=["XGBoost", "FastAPI", "React", "TypeScript", "PostgreSQL"]),
    dict(slug="taskflow", tag="SECURITY · AUTH", name="TaskFlow Auth", live=True,
         desc=["MERN authentication module: two-token JWT,",
               "refresh-token rotation, SHA-256 hashed tokens",
               "and reuse-attack detection."],
         proof="Session console · Axios auto-refresh",
         stack=["React", "Node.js", "Express", "MongoDB", "Jest"]),
    dict(slug="leaddesk", tag="FULL-STACK · CRM", name="LeadDesk Mini", live=True,
         desc=["Lead-management CRM for small sales teams:",
               "capture, assign and track leads through a",
               "six-stage pipeline with role-based access."],
         proof="Vercel + Render + MongoDB Atlas",
         stack=["React", "Express", "MongoDB", "Tailwind", "RBAC"]),
    dict(slug="agent", tag="AI · AGENTS", name="AI Coding Agent", live=False,
         desc=["Framework-free autonomous agent that explores",
               "a codebase, plans, edits files through LLM tool",
               "calls and verifies its work in a sandbox."],
         proof="Explore → plan → execute → verify",
         stack=["Python", "OpenAI API", "Pydantic", "Tool calling"]),
]

HIGHLIGHTS = [("0.871", "Test AUC, CredWise AI", "ON 30K UNSEEN BORROWERS"),
              ("5", "Client web properties", "CONTRIBUTED TO AT IMPERIAL"),
              ("2", "Live full-stack apps", "TASKFLOW AUTH · LEADDESK MINI")]


# ───────────────────────────── components ─────────────────────────────

def hero(P):
    w, h = 1000, 330
    d, b = card(P, w, h, r=20, bar=True, grid=True, scan=7, bracket=True,
                glows=[(140, 40, 420, 240, 0), (860, 300, 380, 220, 1)])
    d += grad("ink", (0, P["ink"][0]), (0.5, P["ink"][1]), (1, P["ink"][2]))
    parts = b + [
        t(56, 124, "Akshat Agrawal", 68, "url(#ink)", "d", 700, ls=-2.4),
        f'<text x="58" y="170" class="s" font-size="21">{span("Full-stack developer", P["text"], font_weight=600)}'
        f'{span(" building scalable web applications", P["soft"])}</text>',
        t(58, 198, "and AI-powered products.", 21, P["soft"]),
        mark(P, w - 56 - 104, 52, 104),
        t(w - 56 - 52, 186, "AKSHAT/OS", 12.5, P["dim"], "m", 600, "middle", ls=2),
        rect(56, 234, w - 112, 1, P["rule"]),
    ]
    xs = [56, 392, 664]
    for i, ((label, value), x) in enumerate(zip(FACTS, xs)):
        parts += [rect(x, 248, 22, 2, "url(#acc)", 1, f' opacity="{0.95 - i * 0.2:.2f}"'),
                  t(x, 276, label, 12.5, P["dim"], "m", 600, ls=1.6),
                  t(x, 304, value, 18, P["text"], weight=600)]
    return doc(w, h, "Akshat Agrawal — Full-stack developer building scalable web applications and AI-powered products",
               "\n".join(parts), d)


def button(P, label, primary):
    w, h, pad = 172, 48, 14  # pad: transparent top margin; GitHub strips the CSS that could space images
    a0, a1, a2 = P["acc"]
    defs = grad("btn", (0, a1), (1, a2))
    if primary:
        shape = (f'<rect x="0" y="{pad}" width="{w}" height="{h}" rx="24" fill="url(#btn)"/>'
                 f'<rect x=".5" y="{pad + .5}" width="{w - 1}" height="{h - 1}" rx="24" fill="none" '
                 f'stroke="#FFFFFF" stroke-opacity=".25"/>')
        ink = P["btn_ink"]
    else:
        shape = (f'<rect x=".75" y="{pad + .75}" width="{w - 1.5}" height="{h - 1.5}" rx="24" fill="none" '
                 f'stroke="{P["btn2_line"]}" stroke-width="1.5"/>'
                 f'<path d="M{w / 2 - 34} {pad + 1}h68" stroke="{a0}" stroke-width="1.5" opacity=".75"/>')
        ink = P["btn2_ink"]
    body = (defs + shape + t((w - 18) / 2, pad + 30, label, 16, ink, "d", 700, "middle")
            + arrow(w - 40, pad + 19.5, ink))
    return doc(w, h + pad, label, body)


def now_building(P):
    w, h = 1000, 268
    d, b = card(P, w, h, r=18, grid=True, scan=9, bracket=True,
                glows=[(832, 134, 330, 220, 0), (90, 20, 320, 180, 1)])
    d += grad("ink", (0, P["ink"][0]), (0.5, P["ink"][1]), (1, P["ink"][2]))
    a0 = P["acc"][0]
    hub, out = (832, 134), (918, 134)
    viz = [f'<circle cx="{hub[0]}" cy="{hub[1]}" r="26" fill="none" stroke="{P["rule"]}" stroke-width="1.4"/>']
    viz += [pulse_ring(*hub, 26, 96, a0, 4.2, i * 1.4) for i in range(3)]
    for i in range(5):
        x, y = 668, 62 + i * 36
        path = f"M{x} {y}C{x + 84} {y} {hub[0] - 84} {hub[1]} {hub[0] - 16} {hub[1]}"
        viz += [f'<path d="{path}" fill="none" stroke="{P["line"]}" stroke-width="1.4"/>',
                # a packet riding each link into the hub, staggered so the card reads as live
                f'<circle r="3" fill="{a0}">'
                f'<animateMotion dur="3.4s" begin="{i * 0.55:.2f}s" repeatCount="indefinite" path="{path}"/>'
                f"{anim('opacity', '0;.95;.95;0', 3.4, i * 0.55)}</circle>",
                f'<circle cx="{x}" cy="{y}" r="5" fill="{P["card"]}" stroke="{P["dim"]}" stroke-width="1.4"/>']
    viz += [f'<circle cx="{hub[0]}" cy="{hub[1]}" r="13" fill="url(#acc)"/>',
            f'<circle cx="{hub[0]}" cy="{hub[1]}" r="4" fill="{P["card"]}"/>',
            rect(hub[0] + 26, hub[1] - .75, out[0] - hub[0] - 34, 1.5, a0),
            rect(out[0] - 8, out[1] - 8, 16, 16, "url(#acc)", 4)]
    parts = b + [
        live_dot(60, 56, a0),
        t(74, 61, "NOW BUILDING", 12.5, P["accent_ink"], "m", 700, ls=2),
        t(56, 124, "DecisionOS AI", 48, "url(#ink)", "d", 700, ls=-1.6),
        t(57, 162, "An AI-powered business operating system designed to", 18, P["soft"]),
        t(57, 188, "help businesses make better decisions using AI.", 18, P["soft"]),
        rect(56, 212, 540, 1, P["rule"]),
        f'<text x="57" y="244" class="m" font-size="12.5" letter-spacing="1.2">{span("STATUS", P["dim"], font_weight=600)}'
        f'{span("IN DEVELOPMENT", P["soft"], dx=10)}{span("CATEGORY", P["dim"], dx=34, font_weight=600)}'
        f'{span("AI · BUSINESS SOFTWARE", P["soft"], dx=10)}</text>',
    ] + viz
    return doc(w, h, "Now building — DecisionOS AI, an AI-powered business operating system. Status: in development.",
               "\n".join(parts), d)


def project(P, p):
    w, h = 480, 276
    d, b = card(P, w, h, r=16, bracket=True, glows=[(w, 0, 300, 190, 0), (0, h, 240, 160, 1)])
    status, dot = ("LIVE", P["live"]) if p["live"] else ("SOURCE", P["dim"])
    sw = mono_w(status, 11.5, 1) + 32
    sx = w - 28 - sw
    parts = b + [
        rect(28, 36, 2, 14, "url(#acc)", 1),
        t(40, 48, p["tag"], 12, P["muted"], "m", 600, ls=1.4),
        rect(sx, 31, sw, 24, P["chip"], 12, f' stroke="{P["chip_line"]}"'),
        live_dot(sx + 13, 43, dot, 3.5) if p["live"] else f'<circle cx="{sx + 13:.1f}" cy="43" r="3.5" fill="{dot}"/>',
        t(sx + 23, 47, status, 11.5, P["soft"], "m", 600, ls=1),
        t(28, 98, p["name"], 30, P["text"], "d", 700, ls=-.6),
    ]
    parts += [t(28, 132 + i * 22, line, 15.5, P["soft"]) for i, line in enumerate(p["desc"])]
    parts += [rect(28, 202, 7, 7, "url(#acc)", 1.5), t(43, 209.5, p["proof"], 12.5, P["text"], "m", 500),
              rect(28, 228, w - 56, 1, P["rule"]),
              t(28, 254, " · ".join(p["stack"]), 12.5, P["muted"], "m")]
    return doc(w, h, f'{p["name"]} — {" ".join(p["desc"])}', "\n".join(parts), d)


def highlights(P):
    w, h = 1000, 182
    d, b = card(P, w, h, r=18, bracket=True, glows=[(500, -10, 520, 170, 0), (980, h, 300, 170, 1)])
    d += grad("ink", (0, P["ink"][0]), (0.5, P["ink"][1]), (1, P["ink"][2]))
    col = w / len(HIGHLIGHTS)
    parts = list(b)
    for i, (num, label, sub) in enumerate(HIGHLIGHTS):
        x = i * col + 44
        if i:
            parts.append(rect(i * col, 40, 1, h - 80, P["rule"]))
        parts += [rect(x, 42, 28, 3, "url(#acc)", 1.5), t(x, 108, num, 52, "url(#ink)", "d", 700, ls=-1.5),
                  t(x, 138, label, 17, P["soft"], weight=600), t(x, 162, sub, 12, P["dim"], "m", 600, ls=1.1)]
    title = "Highlights: " + "; ".join(f"{n} {l.lower()}" for n, l, _ in HIGHLIGHTS)
    return doc(w, h, title, "\n".join(parts), d)


def fetch(url, token=None, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-profile-build"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return raw if binary else raw.decode("utf-8")


def api(path, token, cache):
    """GET from the GitHub API. Good responses are cached, so a rate-limited or offline rebuild
    reuses the last known data instead of failing."""
    try:
        cache[path] = json.loads(fetch(f"https://api.github.com{path}", token))
    except Exception:
        if path not in cache:
            raise
    return cache[path]


def activity_data():
    token = os.environ.get("GITHUB_TOKEN")
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    repos = [r for r in api(f"/users/{USER}/repos?per_page=100&type=owner", token, cache)
             if not r["fork"] and r["name"].lower() != USER.lower()]  # skip this profile repo
    langs = {}
    for r in repos:
        if r["size"]:
            for k, v in api(f"/repos/{USER}/{r['name']}/languages", token, cache).items():
                langs[k] = langs.get(k, 0) + v
    CACHE.write_text(json.dumps(cache), encoding="utf-8")
    top = sorted(langs.items(), key=lambda kv: -kv[1])
    return dict(
        repos=len(repos),
        live=sum(1 for r in repos if r.get("homepage")),
        langs=len(langs),
        total=sum(langs.values()) or 1,
        shown=top[:5] + ([("Other", sum(v for _, v in top[5:]))] if len(top) > 5 else []),
        recent=[(r["name"], r["pushed_at"][:10])
                for r in sorted((r for r in repos if r["size"]), key=lambda r: r["pushed_at"], reverse=True)[:3]],
        today=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )


def activity(P, a):
    w, h = 1000, 290
    d, b = card(P, w, h, r=18, scan=11, glows=[(0, 0, 380, 210, 0), (1000, h, 320, 200, 1)])
    d += grad("ink", (0, P["ink"][0]), (0.5, P["ink"][1]), (1, P["ink"][2]))
    parts = b + [live_dot(48, 48, P["acc"][0], 3.5),
                 t(62, 52, "PUBLIC FOOTPRINT", 12.5, P["dim"], "m", 600, ls=1.6),
                 t(956, 52, f"SYNCED {a['today']} · GITHUB API", 12.5, P["dim"], "m", anchor="end", ls=1.2)]
    for i, (n, label) in enumerate([(a["repos"], "PUBLIC REPOS"), (a["live"], "LIVE DEMOS"), (a["langs"], "LANGUAGES")]):
        x = 44 + i * 172
        parts += [t(x, 120, n, 46, "url(#ink)", "d", 700, ls=-1),
                  t(x, 146, label, 12, P["muted"], "m", 600, ls=1.5)]
    parts += [rect(592, 78, 1, 76, P["rule"]), t(624, 88, "RECENTLY PUSHED", 12.5, P["dim"], "m", 600, ls=1.6)]
    for i, (name, day) in enumerate(a["recent"]):
        y = 116 + i * 24
        parts += [t(624, y, name, 14, P["soft"], "m"), t(956, y, day, 13, P["dim"], "m", anchor="end")]
    parts += [rect(44, 176, 912, 1, P["rule"]), t(44, 208, "LANGUAGES BY CODE SIZE", 12.5, P["dim"], "m", 600, ls=1.6)]
    x, bar_w = 44.0, 912
    parts.append(f'<clipPath id="bar"><rect x="44" y="222" width="{bar_w}" height="8" rx="4"/></clipPath>'
                 '<g clip-path="url(#bar)">')
    for i, (_, v) in enumerate(a["shown"]):
        seg = bar_w * v / a["total"]
        parts.append(rect(x, 222, seg + .5, 8, P["bars"][i]))
        x += seg
    # a highlight sweeping the bar, so the breakdown reads as a live meter
    parts.append(f'<rect x="44" y="222" width="90" height="8" fill="url(#scan)" opacity=".55">'
                 f"{anim('x', f'44;{44 + bar_w - 90}', 6)}</rect></g>")
    x = 44
    for i, (k, v) in enumerate(a["shown"]):
        label = f"{k} {100 * v / a['total']:.1f}%"
        parts += [rect(x, 252, 9, 9, P["bars"][i], 2, f' stroke="{P["line"]}"'), t(x + 15, 261, label, 13, P["soft"], "m")]
        x += 15 + mono_w(label, 13) + 26
    title = (f"GitHub activity: {a['repos']} public repos, {a['live']} live demos; languages "
             + ", ".join(f"{k} {100 * v / a['total']:.0f}%" for k, v in a["shown"]))
    return doc(w, h, title, "\n".join(parts), d)


# ───────────────────────────── build ─────────────────────────────

def main():
    global FONT_B64
    OUT.mkdir(exist_ok=True)
    FONT_B64 = base64.b64encode(fetch(FONT_URL, binary=True)).decode("ascii")
    act = activity_data()
    files = {}
    for theme, P in THEMES.items():
        files.update({
            f"hero-{theme}.svg": hero(P),
            f"btn-linkedin-{theme}.svg": button(P, "LinkedIn", True),
            f"btn-github-{theme}.svg": button(P, "GitHub", False),
            f"now-building-{theme}.svg": now_building(P),
            f"highlights-{theme}.svg": highlights(P),
            f"activity-{theme}.svg": activity(P, act),
            **{f'project-{p["slug"]}-{theme}.svg': project(P, p) for p in PROJECTS},
        })
    for name, svg in files.items():
        ET.fromstring(svg)  # malformed SVG renders as a broken image on GitHub: fail the build instead
        (OUT / name).write_text(svg, encoding="utf-8", newline="\n")
    stale = {p.name for p in OUT.glob("*.svg")} - set(files)
    for name in stale:
        (OUT / name).unlink()  # assets that are no longer generated
    print(f"wrote {len(files)} files to {OUT}" + (f", removed {sorted(stale)}" if stale else ""))


if __name__ == "__main__":
    main()
