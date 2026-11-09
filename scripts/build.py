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
CACHE = Path(__file__).resolve().parent / ".github-cache.json"  # last good API responses (gitignored)
ICON_URL = "https://cdn.jsdelivr.net/npm/simple-icons@16.37.0/icons/{}.svg"

# Neutral greys carry the design; blue is the one accent, violet appears only in thin rules.
TEXT, SOFT, MUTED, DIM = "#F5F7FA", "#C8CFDB", "#9AA3B5", "#5D6575"
BLUE, VIOLET, CYAN, GREEN = "#4F7CFF", "#8B5CF6", "#22D3EE", "#3FB950"
EYEBROW = "#8FA8FF"
CHIP, CHIP_LINE, LINE = "#0E131D", "#1F2635", "#1E2433"

CSS = (".s{font-family:Inter,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif}"
       ".m{font-family:'JetBrains Mono','SF Mono',Menlo,Consolas,'Liberation Mono',monospace}")


def esc(s):
    return escape(str(s), {'"': "&quot;"})


def mono_w(s, size, ls=0):
    # Monospace fallbacks all sit near 0.6em per glyph; 0.62 keeps boxes from clipping.
    return len(s) * (size * 0.62 + ls)


def t(x, y, s, size=14, fill=TEXT, cls="s", weight=400, anchor="start", ls=0):
    extra = f' letter-spacing="{ls}"' if ls else ""
    return (f'<text x="{x:.1f}" y="{y}" class="{cls}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def span(s, fill, **attrs):
    a = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<tspan fill="{fill}"{a}>{esc(s)}</tspan>'


def grad(id_, *stops, x1=0, y1=0, x2=1, y2=0):
    st = "".join(f'<stop offset="{s[0]}" stop-color="{s[1]}" stop-opacity="{s[2] if len(s) > 2 else 1}"/>'
                 for s in stops)
    return f'<linearGradient id="{id_}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{st}</linearGradient>'


def rect(x, y, w, h, fill, rx=0, extra=""):
    return f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{rx}" fill="{fill}"{extra}/>'


def hline(x, y, w, opacity=0.07):
    return rect(x, y, w, 1, "#FFFFFF", extra=f' opacity="{opacity}"')


def vline(x, y, h, opacity=0.07):
    return rect(x, y, 1, h, "#FFFFFF", extra=f' opacity="{opacity}"')


def arrow(x, y, color, size=9):
    return (f'<path d="M{x} {y + size}L{x + size} {y}M{x + 2.5} {y}H{x + size}V{y + size - 2.5}" '
            f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>')


def doc(w, h, title, defs, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(title)}">\n<title>{esc(title)}</title>\n<style>{CSS}</style>\n'
            f"<defs>{defs}</defs>\n{body}\n</svg>\n")


def panel(w, h, glows, r=16, grid=False):
    """Dark card: gradient base, optional faint grid, soft glow, hairline border, lit top edge."""
    defs = [
        grad("bg", (0, "#050505"), (0.55, "#080B12"), (1, "#0B1020"), x2=1, y2=1),
        grad("edge", (0, BLUE, 0), (0.3, BLUE), (0.7, VIOLET), (1, VIOLET, 0)),
        grad("acc", (0, BLUE), (1, VIOLET)),
        f'<clipPath id="clip"><rect width="{w}" height="{h}" rx="{r}"/></clipPath>',
    ]
    body = ['<g clip-path="url(#clip)">', rect(0, 0, w, h, "url(#bg)")]
    if grid:
        defs += ['<pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">'
                 '<path d="M32 0H0V32" fill="none" stroke="#FFFFFF" stroke-opacity=".035"/></pattern>',
                 '<radialGradient id="gfade"><stop offset="0" stop-color="#FFF"/>'
                 '<stop offset="1" stop-color="#FFF" stop-opacity="0"/></radialGradient>',
                 f'<mask id="gmask"><rect width="{w}" height="{h}" fill="url(#gfade)"/></mask>']
        body.append(f'<rect width="{w}" height="{h}" fill="url(#grid)" mask="url(#gmask)"/>')
    for i, (cx, cy, rx, ry, c, o) in enumerate(glows):
        defs.append(f'<radialGradient id="glow{i}"><stop offset="0" stop-color="{c}" stop-opacity="{o}"/>'
                    f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
        body.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#glow{i})"/>')
    body.append(rect(r, 0, w - 2 * r, 1, "url(#edge)", extra=' opacity=".55"'))
    body.append("</g>")
    body.append(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{r}" fill="none" stroke="{LINE}"/>')
    return "".join(defs), "\n".join(body)


# ───────────────────────────── content ─────────────────────────────

FACTS = [("CURRENTLY", "Imperial Tech Innovations"), ("EDUCATION", "B.Tech CSE · 2027"),
         ("BUILDING", "DecisionOS AI")]

FOCUS = [("Product engineering", "React · Next.js · TypeScript"),
         ("Backend & APIs", "Node.js · Express · FastAPI"),
         ("Cloud & delivery", "AWS · Vercel · Cloudinary"),
         ("Applied AI / ML", "XGBoost · scikit-learn · OpenCV")]

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

def hero():
    w, h = 1000, 400
    d, b = panel(w, h, [(500, -30, 560, 250, BLUE, .20), (500, -30, 300, 150, VIOLET, .10)], grid=True)
    eyebrow = "FULL-STACK DEVELOPER"
    ew = mono_w(eyebrow, 12, 3)
    chips = ["React", "Next.js", "Node.js", "AWS", "AI/ML"]
    widths = [mono_w(c, 12) + 24 for c in chips]
    x = 500 - (sum(widths) + 8 * (len(chips) - 1)) / 2
    parts = [
        b,
        rect(500 - ew / 2 - 56, 73, 40, 1, EYEBROW, extra=' opacity=".45"'),
        rect(500 + ew / 2 + 16, 73, 40, 1, EYEBROW, extra=' opacity=".45"'),
        t(500, 78, eyebrow, 12, EYEBROW, "m", 600, "middle", ls=3),
        t(500, 160, "Akshat Agrawal", 76, TEXT, weight=700, anchor="middle", ls=-2.5),
        t(500, 204, "Building scalable web applications and AI-powered products.", 19, MUTED, anchor="middle"),
    ]
    for c, cw in zip(chips, widths):
        parts += [rect(x, 230, cw, 28, CHIP, 7, f' stroke="{CHIP_LINE}"'), t(x + cw / 2, 249, c, 12, SOFT, "m", anchor="middle")]
        x += cw + 8
    col = (w - 80) / len(FACTS)
    parts.append(hline(40, 296, w - 80, .08))
    for i, (label, value) in enumerate(FACTS):
        cx = 40 + col * (i + .5)
        if i:
            parts.append(vline(40 + col * i, 316, 64))
        parts += [t(cx, 338, label, 10.5, DIM, "m", 600, "middle", ls=1.5), t(cx, 366, value, 16, TEXT, weight=600, anchor="middle")]
    return doc(w, h, "Akshat Agrawal — Full-Stack Developer", d, "\n".join(parts))


def button(label, primary):
    w, h, pad = 168, 46, 18  # pad: transparent top margin; GitHub strips the CSS that could space images
    if primary:
        shape = rect(0, pad, w, h, "#3B6CF6", 10)
        ink = "#FFFFFF"
    else:
        shape = f'<rect x=".5" y="{pad + .5}" width="{w - 1}" height="{h - 1}" rx="10" fill="#0B0F17" stroke="#343C4F"/>'
        ink = "#E6E9EF"
    body = shape + t((w - 16) / 2, pad + 29, label, 15, ink, weight=600, anchor="middle") + arrow(w - 38, pad + 18.5, ink)
    return doc(w, h + pad, label, "", body)



def focus():
    w, row = 360, 54
    h = 54 + row * len(FOCUS) + 8
    d, b = panel(w, h, [(w, 0, 260, 160, BLUE, .14)], r=14)
    parts = [b, t(24, 34, "FOCUS AREAS", 10.5, DIM, "m", 600, ls=1.5), hline(0, 54, w)]
    for i, (title, sub) in enumerate(FOCUS):
        y = 54 + i * row
        parts += [t(24, y + 26, f"{i + 1:02d}", 11, EYEBROW, "m", 600), t(56, y + 26, title, 15, TEXT, weight=600),
                  t(56, y + 44, sub, 11.5, MUTED, "m")]
        if i < len(FOCUS) - 1:
            parts.append(hline(24, y + row, w - 48, .06))
    return doc(w, h, "Focus areas: " + "; ".join(f"{a} ({b})" for a, b in FOCUS), d, "\n".join(parts))


def stack(icons):
    w, x0, x_max = 1000, 228, 960
    chip_h, gap, pad = 32, 8, 16
    parts, y = [], 32
    for gi, (group, items) in enumerate(STACK):
        x, top = x0, y
        parts.append(t(40, top + 20.5, group.upper(), 11, MUTED, "m", 600, ls=1.5))
        for label, slug in items:
            cw = 34 + mono_w(label, 12.5) + 14
            if x + cw > x_max:
                x, y = x0, y + chip_h + gap
            parts.append(rect(x, y, cw, chip_h, CHIP, 8, f' stroke="{CHIP_LINE}"'))
            if slug:
                parts.append(f'<path transform="translate({x + 11:.1f} {y + 8.5}) scale({15 / 24:.4f})" '
                             f'fill="#B4BCCB" d="{icons[slug]}"/>')
            else:
                parts.append(f'<circle cx="{x + 18.5:.1f}" cy="{y + 16}" r="3" fill="{BLUE}" opacity=".85"/>')
            parts.append(t(x + 34, y + 20.5, label, 12.5, SOFT, "m"))
            x += cw + gap
        y += chip_h
        if gi < len(STACK) - 1:
            parts.append(hline(40, y + pad, w - 80, .06))
            y += 2 * pad + 1
    h = y + 32
    d, b = panel(w, h, [(w, 0, 420, 240, BLUE, .12)])
    return doc(w, h, "Tech stack", d, b + "\n" + "\n".join(parts))


def now_building():
    w, h = 1000, 300
    d, b = panel(w, h, [(812, 150, 340, 220, BLUE, .16), (100, 0, 340, 180, VIOLET, .10)], grid=True)
    hub, out = (812, 150), (912, 150)
    viz = [f'<circle cx="{hub[0]}" cy="{hub[1]}" r="{r}" fill="none" stroke="#FFFFFF" stroke-opacity=".05"/>'
           for r in (30, 58, 88)]
    for i in range(5):
        x, y = 652, 70 + i * 40
        viz += [f'<path d="M{x} {y}C{x + 80} {y} {hub[0] - 80} {hub[1]} {hub[0] - 10} {hub[1]}" fill="none" '
                f'stroke="#FFFFFF" stroke-opacity=".14"/>',
                f'<circle cx="{x}" cy="{y}" r="4" fill="#0B1020" stroke="#3A4458"/>']
    viz += [f'<circle cx="{hub[0]}" cy="{hub[1]}" r="18" fill="{BLUE}" opacity=".12"/>',
            f'<circle cx="{hub[0]}" cy="{hub[1]}" r="8" fill="#0B1020" stroke="{BLUE}" stroke-width="1.6"/>',
            f'<circle cx="{hub[0]}" cy="{hub[1]}" r="3" fill="{TEXT}"/>',
            rect(hub[0] + 10, hub[1] - .5, out[0] - hub[0] - 18, 1, BLUE, extra=' opacity=".7"'),
            rect(out[0] - 8, out[1] - 8, 16, 16, BLUE, 4)]
    parts = [
        b,
        f'<circle cx="52" cy="62" r="3.5" fill="{BLUE}"/>',
        t(64, 66, "NOW BUILDING", 11, EYEBROW, "m", 600, ls=2),
        t(48, 128, "DecisionOS AI", 48, TEXT, weight=700, ls=-1.2),
        t(48, 168, "An AI-powered business operating system designed to", 17, SOFT),
        t(48, 194, "help businesses make better decisions using AI.", 17, SOFT),
        hline(48, 224, 500, .08),
        f'<text x="48" y="256" class="m" font-size="11" letter-spacing="1">{span("STATUS", DIM)}'
        f'{span("IN DEVELOPMENT", SOFT, dx=10)}{span("CATEGORY", DIM, dx=32)}'
        f'{span("AI · BUSINESS SOFTWARE", SOFT, dx=10)}</text>',
    ] + viz
    return doc(w, h, "Now building — DecisionOS AI", d, "\n".join(parts))


def project(p):
    w, h = 480, 280
    d, b = panel(w, h, [(w, 0, 300, 190, BLUE, .16)], r=14)
    status, dot = ("LIVE", GREEN) if p["live"] else ("SOURCE", DIM)
    sw = mono_w(status, 10, 1) + 30
    sx = w - 28 - sw
    parts = [
        b,
        t(28, 44, p["tag"], 10.5, MUTED, "m", 600, ls=1.5),
        rect(sx, 29, sw, 22, CHIP, 6, f' stroke="{CHIP_LINE}"'),
        f'<circle cx="{sx + 11:.1f}" cy="40" r="3" fill="{dot}"/>',
        t(sx + 20, 44, status, 10, SOFT, "m", 600, ls=1),
        t(28, 92, p["name"], 28, TEXT, weight=700, ls=-.5),
    ]
    parts += [t(28, 124 + i * 21, line, 14, MUTED) for i, line in enumerate(p["desc"])]
    parts += [rect(28, 193, 2, 14, BLUE, 1), t(38, 204.5, p["proof"], 11.5, SOFT, "m")]
    x = 28
    for s in p["stack"]:
        cw = mono_w(s, 11) + 20
        parts += [rect(x, 226, cw, 26, CHIP, 6, f' stroke="{CHIP_LINE}"'), t(x + 10, 243, s, 11, SOFT, "m")]
        x += cw + 6
    return doc(w, h, f'{p["name"]} — {" ".join(p["desc"])}', d, "\n".join(parts))


def highlights():
    w, h = 1000, 176
    d, b = panel(w, h, [(500, -20, 520, 160, BLUE, .12)])
    col = w / len(HIGHLIGHTS)
    parts = [b]
    for i, (num, label, sub) in enumerate(HIGHLIGHTS):
        x = i * col + 40
        if i:
            parts.append(vline(i * col, 36, h - 72))
        parts += [rect(x, 40, 24, 2, "url(#acc)"), t(x, 100, num, 46, TEXT, weight=700, ls=-1),
                  t(x, 130, label, 15, SOFT, weight=600), t(x, 152, sub, 10.5, DIM, "m", ls=1)]
    title = "Highlights: " + "; ".join(f"{n} {l.lower()}" for n, l, _ in HIGHLIGHTS)
    return doc(w, h, title, d, "\n".join(parts))


def fetch(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-profile-build"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def api(path, token, cache):
    """GET from the GitHub API. Good responses are cached, so a rate-limited or offline rebuild
    reuses the last known data instead of failing."""
    try:
        cache[path] = json.loads(fetch(f"https://api.github.com{path}", token))
    except Exception:
        if path not in cache:
            raise
    return cache[path]


def activity():
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
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])
    shown = top[:5] + ([("Other", sum(v for _, v in top[5:]))] if len(top) > 5 else [])
    recent = sorted((r for r in repos if r["size"]), key=lambda r: r["pushed_at"], reverse=True)[:3]
    live = sum(1 for r in repos if r.get("homepage"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    w, h = 1000, 280
    d, b = panel(w, h, [(0, 0, 380, 200, BLUE, .14)])
    parts = [b, t(40, 46, "PUBLIC FOOTPRINT", 10.5, DIM, "m", 600, ls=1.5),
             t(960, 46, f"SYNCED {today} · GITHUB API", 10.5, DIM, "m", anchor="end", ls=1.5)]
    for i, (n, label) in enumerate([(len(repos), "PUBLIC REPOS"), (live, "LIVE DEMOS"), (len(langs), "LANGUAGES")]):
        x = 40 + i * 170
        parts += [t(x, 112, n, 44, TEXT, weight=700), t(x, 136, label, 10.5, MUTED, "m", 600, ls=1.5)]
    parts += [vline(590, 66, 80), t(620, 78, "RECENTLY PUSHED", 10.5, DIM, "m", 600, ls=1.5)]
    for i, r in enumerate(recent):
        y = 104 + i * 22
        parts += [t(620, y, r["name"], 13, SOFT, "m"), t(960, y, r["pushed_at"][:10], 12, DIM, "m", anchor="end")]
    parts += [hline(40, 168, 920), t(40, 198, "LANGUAGES BY CODE SIZE", 10.5, DIM, "m", 600, ls=1.5)]
    colors = [BLUE, VIOLET, CYAN, "#2DD4BF", "#64748B", "#3F4A61"]
    x, bar_w = 40.0, 920
    parts.append(f'<clipPath id="bar"><rect x="40" y="212" width="{bar_w}" height="8" rx="4"/></clipPath>'
                 '<g clip-path="url(#bar)">')
    for i, (_, v) in enumerate(shown):
        seg = bar_w * v / total
        parts.append(rect(x, 212, seg + .5, 8, colors[i]))
        x += seg
    parts.append("</g>")
    x = 40
    for i, (k, v) in enumerate(shown):
        label = f"{k} {100 * v / total:.1f}%"
        parts += [rect(x, 241, 8, 8, colors[i], 2), t(x + 14, 249, label, 12, SOFT, "m")]
        x += 14 + mono_w(label, 12) + 26
    title = (f"GitHub activity: {len(repos)} public repos, {live} live demos; languages "
             + ", ".join(f"{k} {100 * v / total:.0f}%" for k, v in shown))
    return doc(w, h, title, d, "\n".join(parts))


def connect():
    w, h = 1000, 186
    d, b = panel(w, h, [(500, -20, 520, 180, BLUE, .18)], grid=True)
    parts = [
        b,
        t(500, 58, "CONTACT", 11, EYEBROW, "m", 600, "middle", ls=2.5),
        t(500, 106, "Building something interesting?", 36, TEXT, weight=700, anchor="middle", ls=-.8),
        t(500, 142, "Let's talk about full-stack products, cloud and applied AI.", 17, MUTED, anchor="middle"),
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
        "focus.svg": focus(),
        "stack.svg": stack(icons),
        "now-building.svg": now_building(),
        "highlights.svg": highlights(),
        "activity.svg": activity(),
        "connect.svg": connect(),
        **{f'project-{p["slug"]}.svg': project(p) for p in PROJECTS},
    }
    for name, svg in files.items():
        ET.fromstring(svg)  # malformed SVG renders as a broken image on GitHub: fail the build instead
        (OUT / name).write_text(svg, encoding="utf-8", newline="\n")
    stale = {p.name for p in OUT.glob("*.svg")} - set(files)
    for name in stale:
        (OUT / name).unlink()  # assets that are no longer generated
    print(f"wrote {len(files)} files to {OUT}" + (f", removed {sorted(stale)}" if stale else ""))


if __name__ == "__main__":
    main()
