#!/usr/bin/env python3
"""Generates every SVG in assets/ for the profile README.

    python scripts/build.py

Each card is drawn twice, in a light and a dark version; the README shows the one that matches the
viewer's GitHub theme. Edit the content below and re-run. Only the activity card pulls live data
(GitHub API, cached in scripts/.github-cache.json); everything else is static. Standard library only.
"""
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

# One system, two themes. Ink and bone carry the design; orange is the only accent.
# accent_ink is the orange that still passes contrast as small text on the card.
THEMES = {
    "light": dict(
        card="#FBFAF7", line="#E4E0D7", rule="#ECE8E1",
        text="#111111", soft="#3A3732", muted="#66625A", dim="#85817A",
        accent="#FF5A1F", accent_ink="#B83C0B", live="#1A7F37",
        chip="#F3F0EA", chip_line="#E1DCD2",
        mark="#111111", mark_line="#111111",
        btn="#111111", btn_ink="#FBFAF7", btn2_line="#C9C3B8", btn2_ink="#111111",
        bars=["#FF5A1F", "#111111", "#5E5A53", "#9A958B", "#C9C3B8", "#E3DED5"],
    ),
    "dark": dict(
        card="#151412", line="#2D2B27", rule="#252320",
        text="#F2EEE7", soft="#D3CEC4", muted="#A39F96", dim="#7F7B72",
        accent="#FF5A1F", accent_ink="#FF8152", live="#3FB950",
        chip="#1C1B18", chip_line="#33312C",
        mark="#1F1E1B", mark_line="#3A3833",
        btn="#F2EEE7", btn_ink="#151412", btn2_line="#4A4741", btn2_ink="#F2EEE7",
        bars=["#FF5A1F", "#F2EEE7", "#A39F96", "#6F6B63", "#4C4943", "#363430"],
    ),
}

SANS = "Inter,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono','SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
CSS = f".s{{font-family:{SANS}}}.m{{font-family:{MONO}}}"


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


def arrow(x, y, color, size=9):
    return (f'<path d="M{x} {y + size}L{x + size} {y}M{x + 2.5} {y}H{x + size}V{y + size - 2.5}" '
            f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>')


def doc(w, h, title, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(title)}">\n<title>{esc(title)}</title>\n<style>{CSS}</style>\n'
            f"<defs>{defs}</defs>\n{body}\n</svg>\n")


def card(P, w, h, r=16, bar=False):
    """Flat card: paper fill, hairline border, optional orange edge. No glows, no gradients."""
    defs = f'<clipPath id="card"><rect width="{w}" height="{h}" rx="{r}"/></clipPath>'
    body = [f'<g clip-path="url(#card)">', rect(0, 0, w, h, P["card"])]
    if bar:
        body.append(rect(0, 0, 5, h, P["accent"]))
    body.append("</g>")
    body.append(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{r}" fill="none" stroke="{P["line"]}"/>')
    return defs, body


def mark(P, x, y, size):
    """The [A] mark from the AKSHAT/OS identity."""
    k = size / 64
    return (f'<g transform="translate({x} {y})">'
            f'<rect width="{size}" height="{size}" rx="{size * 0.22:.1f}" fill="{P["mark"]}" stroke="{P["mark_line"]}"/>'
            f'<g transform="scale({k:.4f})" fill="none" stroke-width="4.5" stroke-linecap="square">'
            f'<path d="M19 15h-6v34h6" stroke="#FF5A1F"/><path d="M45 15h6v34h-6" stroke="#FF5A1F"/>'
            f'<path d="M24.5 44 32 20l7.5 24M27.4 36h9.2" stroke="#F2EEE7" stroke-linejoin="round"/></g></g>')


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
    d, b = card(P, w, h, r=20, bar=True)
    parts = b + [
        t(56, 122, "Akshat Agrawal", 66, P["text"], weight=800, ls=-2.2),
        f'<text x="58" y="168" class="s" font-size="21">{span("Full-stack developer", P["text"], font_weight=600)}'
        f'{span(" building scalable web applications", P["soft"])}</text>',
        t(58, 196, "and AI-powered products.", 21, P["soft"]),
        mark(P, w - 56 - 104, 52, 104),
        t(w - 56 - 52, 186, "AKSHAT/OS", 12.5, P["dim"], "m", 600, "middle", ls=2),
        rect(56, 234, w - 112, 1, P["rule"]),
    ]
    xs = [56, 392, 664]
    for (label, value), x in zip(FACTS, xs):
        parts += [t(x, 268, label, 12.5, P["dim"], "m", 600, ls=1.6), t(x, 298, value, 18, P["text"], weight=600)]
    return doc(w, h, "Akshat Agrawal — Full-stack developer building scalable web applications and AI-powered products",
               "\n".join(parts), d)


def button(P, label, primary):
    w, h, pad = 172, 48, 14  # pad: transparent top margin; GitHub strips the CSS that could space images
    if primary:
        shape, ink = rect(0, pad, w, h, P["btn"], 24), P["btn_ink"]
    else:
        shape = f'<rect x=".75" y="{pad + .75}" width="{w - 1.5}" height="{h - 1.5}" rx="24" fill="none" stroke="{P["btn2_line"]}" stroke-width="1.5"/>'
        ink = P["btn2_ink"]
    body = shape + t((w - 18) / 2, pad + 30, label, 16, ink, weight=600, anchor="middle") + arrow(w - 40, pad + 19.5, ink)
    return doc(w, h + pad, label, body)


def now_building(P):
    w, h = 1000, 268
    d, b = card(P, w, h, r=18)
    hub, out = (832, 134), (918, 134)
    viz = []
    for i in range(5):
        x, y = 668, 62 + i * 36
        viz += [f'<path d="M{x} {y}C{x + 84} {y} {hub[0] - 84} {hub[1]} {hub[0] - 16} {hub[1]}" fill="none" '
                f'stroke="{P["line"]}" stroke-width="1.4"/>',
                f'<circle cx="{x}" cy="{y}" r="5" fill="{P["card"]}" stroke="{P["dim"]}" stroke-width="1.4"/>']
    viz += [f'<circle cx="{hub[0]}" cy="{hub[1]}" r="26" fill="none" stroke="{P["rule"]}" stroke-width="1.4"/>',
            f'<circle cx="{hub[0]}" cy="{hub[1]}" r="13" fill="{P["accent"]}"/>',
            f'<circle cx="{hub[0]}" cy="{hub[1]}" r="4" fill="{P["card"]}"/>',
            rect(hub[0] + 26, hub[1] - .75, out[0] - hub[0] - 34, 1.5, P["accent"]),
            rect(out[0] - 8, out[1] - 8, 16, 16, P["text"], 4)]
    parts = b + [
        f'<circle cx="60" cy="56" r="4" fill="{P["accent"]}"/>',
        t(74, 61, "NOW BUILDING", 12.5, P["accent_ink"], "m", 700, ls=2),
        t(56, 122, "DecisionOS AI", 46, P["text"], weight=800, ls=-1.4),
        t(57, 160, "An AI-powered business operating system designed to", 18, P["soft"]),
        t(57, 186, "help businesses make better decisions using AI.", 18, P["soft"]),
        rect(56, 210, 540, 1, P["rule"]),
        f'<text x="57" y="242" class="m" font-size="12.5" letter-spacing="1.2">{span("STATUS", P["dim"], font_weight=600)}'
        f'{span("IN DEVELOPMENT", P["soft"], dx=10)}{span("CATEGORY", P["dim"], dx=34, font_weight=600)}'
        f'{span("AI · BUSINESS SOFTWARE", P["soft"], dx=10)}</text>',
    ] + viz
    return doc(w, h, "Now building — DecisionOS AI, an AI-powered business operating system. Status: in development.",
               "\n".join(parts), d)


def project(P, p):
    w, h = 480, 276
    d, b = card(P, w, h, r=16)
    status, dot = ("LIVE", P["live"]) if p["live"] else ("SOURCE", P["dim"])
    sw = mono_w(status, 11.5, 1) + 32
    sx = w - 28 - sw
    parts = b + [
        t(28, 48, p["tag"], 12, P["muted"], "m", 600, ls=1.4),
        rect(sx, 31, sw, 24, P["chip"], 12, f' stroke="{P["chip_line"]}"'),
        f'<circle cx="{sx + 13:.1f}" cy="43" r="3.5" fill="{dot}"/>',
        t(sx + 23, 47, status, 11.5, P["soft"], "m", 600, ls=1),
        t(28, 96, p["name"], 29, P["text"], weight=800, ls=-.6),
    ]
    parts += [t(28, 130 + i * 22, line, 15.5, P["soft"]) for i, line in enumerate(p["desc"])]
    parts += [rect(28, 202, 7, 7, P["accent"], 1.5), t(43, 209.5, p["proof"], 12.5, P["text"], "m", 500),
              rect(28, 228, w - 56, 1, P["rule"]),
              t(28, 254, " · ".join(p["stack"]), 12.5, P["muted"], "m")]
    return doc(w, h, f'{p["name"]} — {" ".join(p["desc"])}', "\n".join(parts), d)


def highlights(P):
    w, h = 1000, 182
    d, b = card(P, w, h, r=18)
    col = w / len(HIGHLIGHTS)
    parts = list(b)
    for i, (num, label, sub) in enumerate(HIGHLIGHTS):
        x = i * col + 44
        if i:
            parts.append(rect(i * col, 40, 1, h - 80, P["rule"]))
        parts += [rect(x, 42, 28, 3, P["accent"], 1.5), t(x, 108, num, 52, P["text"], weight=800, ls=-1.5),
                  t(x, 138, label, 17, P["soft"], weight=600), t(x, 162, sub, 12, P["dim"], "m", 600, ls=1.1)]
    title = "Highlights: " + "; ".join(f"{n} {l.lower()}" for n, l, _ in HIGHLIGHTS)
    return doc(w, h, title, "\n".join(parts), d)


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
    d, b = card(P, w, h, r=18)
    parts = b + [t(44, 52, "PUBLIC FOOTPRINT", 12.5, P["dim"], "m", 600, ls=1.6),
                 t(956, 52, f"SYNCED {a['today']} · GITHUB API", 12.5, P["dim"], "m", anchor="end", ls=1.2)]
    for i, (n, label) in enumerate([(a["repos"], "PUBLIC REPOS"), (a["live"], "LIVE DEMOS"), (a["langs"], "LANGUAGES")]):
        x = 44 + i * 172
        parts += [t(x, 120, n, 46, P["text"], weight=800, ls=-1), t(x, 146, label, 12, P["muted"], "m", 600, ls=1.5)]
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
    parts.append("</g>")
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
    OUT.mkdir(exist_ok=True)
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
