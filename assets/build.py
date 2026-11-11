#!/usr/bin/env python3
"""
cyberRuptor profile — "Field Manual" design system.

Generates every SVG used by README.md in a light and a dark variant.
Run:  python3 assets/build.py
Edit the CONTENT section below and re-run to update the profile.
"""
import math
from pathlib import Path
from xml.sax.saxutils import escape as esc

OUT = Path(__file__).parent

# ─── Tokens ──────────────────────────────────────────────────────────────────
THEMES = {
    "dark": dict(
        page="#0D1117",   # GitHub dark canvas — boxes sit flush on the page
        ink="#ECEAE4",    # warm off-white
        muted="#8B929B",
        faint="#3A4048",
        line="#262C34",
        accent="#FF5A1F", # signal orange
    ),
    "light": dict(
        page="#FFFFFF",
        ink="#121417",
        muted="#636A73",
        faint="#C9CDD2",
        line="#E4E6E9",
        accent="#E8470F",
    ),
}
SANS = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
DEVA = "'Kohinoor Devanagari', 'Noto Sans Devanagari', 'Nirmala UI', 'Devanagari Sangam MN', Mangal, sans-serif"
W = 1200

# ─── Content ─────────────────────────────────────────────────────────────────
PROJECTS = [
    dict(slug="redis-sentinel", idx="P/01", tag="HELM CHART", name="redis-sentinel-helm-chart",
         lines=["Redis Sentinel as a highly-available cache", "manager, packaged for one-command installs."],
         stack="Helm · Kubernetes · Redis"),
    dict(slug="mongodb", idx="P/02", tag="HELM CHART", name="mongodb-helm-chart",
         lines=["MongoDB on Kubernetes with automatic", "replica-set initialisation built in."],
         stack="Helm · Kubernetes · MongoDB"),
    dict(slug="sharepoint-mcp", idx="P/03", tag="CONTRIBUTOR", name="sharepoint-mcp",
         lines=["MCP server that gives AI agents live access", "to read, write and manage SharePoint."],
         stack="Python · MCP · Microsoft Graph"),
    dict(slug="ocft", idx="P/04", tag="CONTRIBUTOR", name="ocft",
         lines=["Organisation contact finder — OSINT and", "reconnaissance automation."],
         stack="Python · OSINT · Automation"),
]

TOOLKIT = [
    ("A", "CLOUD + IAC", ["AWS", "GCP", "Azure", "Terraform", "Ansible"]),
    ("B", "ORCHESTRATION", ["Kubernetes", "Docker", "Helm", "ArgoCD", "Jenkins", "GitHub Actions"]),
    ("C", "OFFENSIVE SEC", ["Kali Linux", "Metasploit", "Nmap", "Wireshark"]),
    ("D", "LANGUAGES", ["Python", "Go", "Rust", "Bash", "JavaScript"]),
    ("E", "DATA", ["PostgreSQL", "MongoDB", "Redis", "GraphQL"]),
]

CONTACTS = [
    dict(slug="email", idx="C/01", glyph="@", name="Email", handle="goyalnikhil743@gmail.com", note="PREFERRED",
         url="mailto:goyalnikhil743@gmail.com"),
    dict(slug="linkedin", idx="C/02", glyph="in", name="LinkedIn", handle="/in/cyberRuptor", note="PROFESSIONAL",
         url="https://linkedin.com/in/cyberRuptor"),
    dict(slug="medium", idx="C/03", glyph="M", name="Medium", handle="@cyberRuptor", note="LONG-FORM",
         url="https://cyberruptor.medium.com"),
    dict(slug="devto", idx="C/04", glyph="DEV", name="Dev.to", handle="/cyberruptor", note="CROSS-POSTS",
         url="https://dev.to/cyberruptor"),
    dict(slug="x", idx="C/05", glyph="X", name="X / Twitter", handle="@cyberruptor", note="SHORT-FORM",
         url="https://twitter.com/cyberruptor"),
    dict(slug="dailydev", idx="C/06", glyph="dd", name="daily.dev", handle="/cyberruptor", note="READING LIST",
         url="https://app.daily.dev/cyberruptor"),
]

HEADERS = [
    ("now", "01", "NOW", "what's on the bench"),
    ("telemetry", "02", "TELEMETRY", "live · redrawn daily from the github api"),
    ("systems", "03", "SYSTEMS", "self-healing ci/cd · reference architecture"),
    ("work", "04", "SELECTED WORK", "repositories"),
    ("network", "05", "NETWORK", "organisations & upstreams"),
    ("toolkit", "06", "TOOLKIT", "daily drivers"),
    ("writing", "07", "WRITING", "auto-synced from medium"),
    ("log", "08", "LIVE LOG", "recent public activity"),
    ("contact", "09", "CONTACT", "open channels"),
]


# ─── Helpers ─────────────────────────────────────────────────────────────────
def svg(w, h, body, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>{body}</svg>\n'
    )


def text(x, y, s, size, fill, family=MONO, weight=400, anchor="start", ls=0, extra=""):
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{esc(s)}</text>'
    )


def line(x1, y1, x2, y2, stroke, w=1, extra=""):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{w}" {extra}/>'


def write(name, theme, content):
    (OUT / f"{name}-{theme}.svg").write_text(content, encoding="utf-8")


def anim(attr, frm, to, delay, dur, ease=True):
    """Intro animation that rests on the final value (element attrs hold the final state)."""
    total = delay + dur
    k = delay / total if total else 0
    spline = ' calcMode="spline" keySplines="0 0 1 1;.2 .7 .2 1"' if ease else ""
    return (f'<animate attributeName="{attr}" values="{frm};{frm};{to}" keyTimes="0;{k:.3f};1" '
            f'dur="{total:.2f}s" fill="freeze"{spline}/>')


def ruler(y, t, x0=0, x1=W, step=12):
    """Blueprint ruler: minor ticks every `step`, majors every 10."""
    out = [line(x0, y, x1, y, t["line"])]
    for i, x in enumerate(range(x0, x1 + 1, step)):
        major = i % 10 == 0
        out.append(line(x, y, x, y - (8 if major else 4), t["faint"] if major else t["line"]))
    return "".join(out)


# ─── Hero ────────────────────────────────────────────────────────────────────
def hero(t):
    H = 470
    cx, cy, R = 940, 252, 134
    b = []

    # meta bar
    b.append(text(48, 40, "CYBERRUPTOR / FIELD MANUAL", 12, t["muted"], ls=2.5))
    b.append(text(W - 48, 40, "REV 2026.11  ·  28.46°N 77.03°E  ·  IST +05:30", 12, t["muted"], anchor="end", ls=2))
    b.append(line(48, 58, W - 48, 58, t["line"]))

    # status
    b.append(
        f'<circle cx="54" cy="113" r="5" fill="{t["accent"]}">'
        f'<animate attributeName="opacity" values="1;.25;1" dur="1.8s" repeatCount="indefinite"/></circle>'
    )
    b.append(text(70, 118, "ONLINE — DEVSECOPS ENGINEER @ AIRTEL DIGITAL", 13, t["ink"], ls=2))

    # name
    b.append(text(44, 222, "Nikhil", 104, t["ink"], SANS, 800, ls=-4))
    b.append(
        f'<text x="44" y="320" font-family="{SANS}" font-size="104" font-weight="800" letter-spacing="-4" '
        f'fill="{t["ink"]}">Goyal<tspan fill="{t["accent"]}">.</tspan></text>'
    )

    # tagline
    b.append(text(48, 376, "I build pipelines that heal themselves", 22, t["muted"], SANS, 400))
    b.append(text(48, 406, "and clusters that never need saving.", 22, t["muted"], SANS, 400))

    # ── emblem: radar dial around a Kubernetes heptagon ──
    g = [f'<g transform="translate({cx} {cy})">']
    for r, dash in ((R, None), (R * 0.72, "2 6"), (R * 0.44, None)):
        da = f'stroke-dasharray="{dash}"' if dash else ""
        g.append(f'<circle r="{r:.1f}" fill="none" stroke="{t["line"] if not dash else t["faint"]}" {da}/>')
    g.append(line(-R - 14, 0, R + 14, 0, t["line"]))
    g.append(line(0, -R - 14, 0, R + 14, t["line"]))
    # dial ticks
    for i in range(72):
        a = math.radians(i * 5)
        major = i % 6 == 0
        r0 = R + (4 if not major else 2)
        r1 = R + (10 if not major else 16)
        g.append(line(f"{r0*math.cos(a):.1f}", f"{r0*math.sin(a):.1f}", f"{r1*math.cos(a):.1f}",
                      f"{r1*math.sin(a):.1f}", t["faint"] if major else t["line"]))
    # degree labels
    for deg, lbl in ((0, "090"), (90, "180"), (180, "270"), (270, "000")):
        a = math.radians(deg)
        g.append(text(f"{(R+32)*math.cos(a):.1f}", f"{(R+32)*math.sin(a)+4:.1f}", lbl, 10, t["muted"],
                      anchor="middle", ls=1))
    # sweep (stacked slices fake a conic gradient), rotates clockwise
    PERIOD = 6
    sweep = ['<g>']
    for k in range(10):
        a0, a1 = math.radians(-(k + 1) * 4), math.radians(-k * 4)
        op = 0.30 * (1 - k / 10) ** 1.6
        sweep.append(
            f'<path d="M0 0 L{R*math.cos(a0):.1f} {R*math.sin(a0):.1f} A{R} {R} 0 0 1 '
            f'{R*math.cos(a1):.1f} {R*math.sin(a1):.1f} Z" fill="{t["accent"]}" opacity="{op:.3f}"/>'
        )
    sweep.append(line(0, 0, R, 0, t["accent"], 1.5))
    sweep.append(
        f'<animateTransform attributeName="transform" type="rotate" from="0" to="360" '
        f'dur="{PERIOD}s" repeatCount="indefinite"/></g>'
    )
    g.append("".join(sweep))
    # blips light up as the sweep passes them
    for ang, dist, rr in ((38, 0.82, 3.5), (128, 0.58, 3), (205, 0.9, 2.5), (292, 0.66, 3.5), (334, 0.38, 2.5)):
        a = math.radians(ang)
        begin = ang / 360 * PERIOD
        g.append(
            f'<circle cx="{R*dist*math.cos(a):.1f}" cy="{R*dist*math.sin(a):.1f}" r="{rr}" fill="{t["accent"]}" opacity="0">'
            f'<animate attributeName="opacity" values="1;.15;0" keyTimes="0;.55;1" dur="{PERIOD}s" '
            f'begin="{begin:.2f}s" repeatCount="indefinite"/></circle>'
        )
    # heptagon core
    hp = " ".join(
        f"{40*math.cos(math.radians(-90 + i*360/7)):.1f},{40*math.sin(math.radians(-90 + i*360/7)):.1f}"
        for i in range(7)
    )
    g.append(f'<polygon points="{hp}" fill="{t["page"]}" stroke="{t["ink"]}" stroke-width="1.5"/>')
    for i in range(7):
        a = math.radians(-90 + i * 360 / 7)
        g.append(line(0, 0, f"{24*math.cos(a):.1f}", f"{24*math.sin(a):.1f}", t["ink"], 1.5,
                      'stroke-linecap="round"'))
    g.append(f'<circle r="7" fill="{t["page"]}" stroke="{t["ink"]}" stroke-width="1.5"/>')
    g.append("</g>")
    b.append("".join(g))


    # footer: motto + ruler
    b.append(text(48, H - 26, "यत भावो तत भवति", 15, t["ink"], DEVA, 500))
    b.append(text(184, H - 27, "— as you feel, so you become.", 12, t["muted"], ls=0.5))
    b.append(text(W - 48, H - 27, "SCROLL ↓", 11, t["muted"], anchor="end", ls=3))
    b.append(ruler(H - 1, t, 48, W - 48))
    return svg(W, H, "".join(b), "Nikhil Goyal — DevSecOps engineer. I build pipelines that heal themselves.")


# ─── Section headers ─────────────────────────────────────────────────────────
def header(t, num, label, note):
    b = [
        text(0, 34, num, 14, t["accent"], weight=700, ls=2),
        line(30, 29, 46, 29, t["accent"], 1.5),
        text(56, 34, label, 14, t["ink"], weight=700, ls=4),
        text(W, 34, note.upper(), 11, t["muted"], anchor="end", ls=2.5),
        line(0, 54, W, 54, t["line"]),
        line(0, 54, 46, 54, t["accent"], 2),
    ]
    return svg(W, 60, "".join(b), f"{num} {label}")


# ─── Pipeline diagram ────────────────────────────────────────────────────────
def pipeline(t):
    H = 360
    bw, bh, y = 150, 64, 72
    nodes = [
        ("PUSH", "developer"),
        ("BUILD", "github actions"),
        ("SCAN", "security gate"),
        ("DEPLOY", "argocd"),
        ("CLUSTER", "kubernetes"),
        ("WATCH", "threat detection"),
    ]
    xs = [20 + i * 196 for i in range(6)]
    ly = 262  # healing-loop row
    b = [
        "<defs>"
        f'<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0 L10 5 L0 10 z" fill="{t["muted"]}"/></marker>'
        f'<marker id="aa" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0 L10 5 L0 10 z" fill="{t["accent"]}"/></marker>'
        "</defs>"
    ]
    mid = y + bh / 2

    # ── edges (drawn first so boxes cover the packet path) ──
    for i in range(5):
        b.append(line(xs[i] + bw, mid, xs[i + 1] - 4, mid, t["muted"], 1.2, 'marker-end="url(#ah)"'))
    b.append(text((xs[2] + bw + xs[3]) / 2, mid - 10, "pass", 11, t["muted"], anchor="middle"))

    flow = f'stroke-dasharray="6 6"><animate attributeName="stroke-dashoffset" from="24" to="0" dur="1s" repeatCount="indefinite"/></path>'
    sx, bx = xs[2] + bw / 2, xs[1] + bw / 2
    tk_x, rm_x = xs[2], xs[1]
    # scan → ticket
    b.append(f'<path d="M{sx} {y+bh} V{ly-bh/2-4}" fill="none" stroke="{t["accent"]}" stroke-width="1.4" marker-end="url(#aa)" {flow}')
    b.append(text(sx + 10, (y + bh + ly - bh / 2) / 2 + 4, "fail", 11, t["accent"]))
    # ticket → remediate
    b.append(f'<path d="M{tk_x} {ly} H{rm_x+bw+4}" fill="none" stroke="{t["accent"]}" stroke-width="1.4" marker-end="url(#aa)" {flow}')
    # remediate → build
    b.append(f'<path d="M{bx} {ly-bh/2} V{y+bh+4}" fill="none" stroke="{t["accent"]}" stroke-width="1.4" marker-end="url(#aa)" {flow}')
    b.append(text(bx - 10, (y + bh + ly - bh / 2) / 2 + 4, "auto-fix", 11, t["accent"], anchor="end"))
    # watch → ticket (alert)
    wx = xs[5] + bw / 2
    b.append(f'<path d="M{wx} {y+bh} V{ly} H{tk_x+bw+4}" fill="none" stroke="{t["accent"]}" stroke-width="1.4" marker-end="url(#aa)" {flow}')
    b.append(text(wx + 10, (y + bh + ly) / 2 + 4, "alert", 11, t["accent"]))
    b.append(text((tk_x + bw + wx) / 2, ly - 10, "runtime findings re-enter the loop", 11, t["muted"], anchor="middle"))

    # ── packets ──
    b.append(
        f'<circle r="4" fill="{t["ink"]}"><animateMotion dur="5s" repeatCount="indefinite" '
        f'path="M{xs[0]+bw/2} {mid} H{xs[5]+bw/2}"/></circle>'
    )
    b.append(
        f'<circle r="4" fill="{t["accent"]}"><animateMotion dur="4s" repeatCount="indefinite" '
        f'path="M{sx} {mid} V{ly} H{bx} V{mid}"/></circle>'
    )

    # ── boxes ──
    def box(x, cy_, title, sub, idx, hot=False):
        stroke = t["accent"] if hot else t["ink"]
        return "".join([
            f'<rect x="{x}" y="{cy_-bh/2}" width="{bw}" height="{bh}" rx="6" fill="{t["page"]}" stroke="{stroke}" stroke-width="1.2"/>',
            text(x, cy_ - bh / 2 - 10, idx, 10, t["muted"], ls=2),
            text(x + 16, cy_ - 3, title, 15, t["ink"], weight=700, ls=2.5),
            text(x + 16, cy_ + 17, sub, 11, t["muted"]),
        ])

    for i, (n, s) in enumerate(nodes):
        b.append(box(xs[i], mid, n, s, f"0{i+1}", hot=(n == "SCAN")))
    b.append(box(tk_x, ly, "TICKET", "jira · auto-filed", "H1", True))
    b.append(box(rm_x, ly, "REMEDIATE", "self-fix scripts", "H2", True))

    # legend
    ly2 = H - 14
    b.append(line(20, ly2 - 4, 48, ly2 - 4, t["muted"], 1.2))
    b.append(text(56, ly2, "delivery path", 11, t["muted"]))
    b.append(line(170, ly2 - 4, 198, ly2 - 4, t["accent"], 1.4, 'stroke-dasharray="6 6"'))
    b.append(text(206, ly2, "healing loop", 11, t["muted"]))
    b.append(text(W - 20, ly2, "FIG. 1 — NO HUMAN IN THE HAPPY PATH", 11, t["muted"], anchor="end", ls=2))
    return svg(W, H, "".join(b), "Self-healing CI/CD: push, build, scan, deploy, cluster, watch — failures auto-file Jira tickets and trigger remediation.")


# ─── Project card ────────────────────────────────────────────────────────────
def card(t, p):
    w, h = 590, 200
    b = [
        f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="none" stroke="{t["line"]}"/>',
        line(24, 0.5, 64, 0.5, t["accent"], 2),
        text(24, 40, p["idx"], 12, t["accent"], weight=700, ls=2),
        text(w - 24, 40, p["tag"], 11, t["muted"], anchor="end", ls=2.5),
        text(24, 86, p["name"], 26, t["ink"], SANS, 700, ls=-0.6),
        text(24, 118, p["lines"][0], 15, t["muted"], SANS),
        text(24, 140, p["lines"][1], 15, t["muted"], SANS),
        line(24, 164, w - 24, 164, t["line"]),
        text(24, 184, p["stack"], 12, t["ink"], ls=0.5),
        text(w - 24, 185, "VIEW REPO ↗", 11, t["accent"], anchor="end", weight=700, ls=2),
    ]
    return svg(w, h, "".join(b), f'{p["name"]}: {" ".join(p["lines"])}')


# ─── Toolkit ─────────────────────────────────────────────────────────────────
def toolkit(t):
    cols = len(TOOLKIT)
    cw = W / cols
    rows = max(len(items) for _, _, items in TOOLKIT)
    H = 70 + rows * 34
    b = []
    for c, (letter, head, items) in enumerate(TOOLKIT):
        x = c * cw
        if c:
            b.append(line(x, 8, x, H - 8, t["line"]))
        px = x + (0 if c == 0 else 24)
        b.append(text(px, 26, f"{letter}/", 12, t["accent"], weight=700))
        b.append(text(px + 24, 26, head, 12, t["muted"], ls=2))
        for r, it in enumerate(items):
            b.append(text(px, 72 + r * 34, it, 18, t["ink"], SANS, 500, ls=-0.2))
    return svg(W, H, "".join(b), "Toolkit: " + "; ".join(f"{h}: {', '.join(i)}" for _, h, i in TOOLKIT))


# ─── Contact ─────────────────────────────────────────────────────────────────
def contact_hero(t):
    H = 230
    cx, cy = 1080, 112
    b = [
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="none" stroke="{t["line"]}"/>',
        line(32, 0.5, 96, 0.5, t["accent"], 2),
        text(32, 48, "OPEN CHANNEL", 11, t["accent"], weight=700, ls=3),
        text(32, 104, "Let's talk pipelines,", 40, t["ink"], SANS, 800, ls=-1.2),
        f'<text x="32" y="150" font-family="{SANS}" font-size="40" font-weight="800" letter-spacing="-1.2" '
        f'fill="{t["ink"]}">clusters <tspan fill="{t["muted"]}">&amp;</tspan> security<tspan fill="{t["accent"]}">.</tspan></text>',
        line(32, 178, 860, 178, t["line"]),
        text(32, 204, "DEVSECOPS · KUBERNETES SECURITY · CI/CD · OPEN SOURCE", 11, t["muted"], ls=2.2),
        text(860, 204, "IST · UTC+05:30", 11, t["muted"], anchor="end", ls=2.2),
    ]
    # transmitter: core + expanding rings
    for i in range(3):
        b.append(
            f'<circle cx="{cx}" cy="{cy}" r="10" fill="none" stroke="{t["accent"]}" stroke-width="1.4" opacity="0">'
            f'<animate attributeName="r" values="10;78" dur="3s" begin="{i}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values=".9;0" dur="3s" begin="{i}s" repeatCount="indefinite"/></circle>'
        )
    for r in (40, 78):
        b.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["line"]}" stroke-dasharray="2 5"/>')
    b.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="{t["accent"]}"/>')
    b.append(line(cx, cy + 9, cx, cy + 92, t["faint"], 1.2))
    b.append(text(cx, H - 14, "TX · LISTENING", 10, t["muted"], anchor="middle", ls=2.5))
    return svg(W, H, "".join(b), "Let's talk pipelines, clusters & security.")


def contact_card(t, c):
    w, h = 390, 132
    b = [
        f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="none" stroke="{t["line"]}"/>',
        line(20, 0.5, 52, 0.5, t["accent"], 2),
        text(20, 32, c["idx"], 11, t["accent"], weight=700, ls=2),
        text(w - 20, 32, c["note"], 10, t["muted"], anchor="end", ls=2.2),
        # glyph tile
        f'<rect x="20.5" y="52.5" width="48" height="48" rx="9" fill="none" stroke="{t["ink"]}" stroke-width="1.2"/>',
        text(44.5, 82, c["glyph"], 13 if len(c["glyph"]) > 2 else 17, t["ink"], SANS, 800, anchor="middle", ls=-0.3),
        text(84, 72, c["name"], 20, t["ink"], SANS, 700, ls=-0.4),
        text(84, 94, c["handle"], 12, t["muted"]),
        line(84, 112, w - 20, 112, t["line"]),
        text(w - 20, 126, "OPEN ↗", 10, t["accent"], anchor="end", weight=700, ls=2),
    ]
    return svg(w, h, "".join(b), f'{c["name"]}: {c["handle"]}')


# ─── Mahadev (contribution-cell invocation) ──────────────────────────────────
def shiva(t):
    """Mahadev drawn in contribution-graph cells. Grid from assets/shiva.grid
    (regenerate with assets/shiva_grid.py)."""
    import random
    rows = (OUT / "shiva.grid").read_text().split()
    R_, C_ = len(rows), len(rows[0])
    pitch = W / C_
    cell = pitch * 0.8
    gh = R_ * pitch
    H = gh + 96
    rnd = random.Random(108)  # deterministic texture
    ink_op = [0.13, 0.32, 0.62, 0.9]
    acc_op = [0.35, 0.6, 0.85, 1]
    b = [
        "<defs>"
        f'<pattern id="sg" width="{pitch}" height="{pitch}" patternUnits="userSpaceOnUse">'
        f'<rect x="{(pitch-cell)/2:.2f}" y="{(pitch-cell)/2:.2f}" width="{cell:.2f}" height="{cell:.2f}" rx="1.4" '
        f'fill="{t["line"]}" opacity=".45"/></pattern>'
        f'<radialGradient id="eyeglow"><stop offset="0" stop-color="{t["accent"]}" stop-opacity=".55"/>'
        f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["accent"]}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity=".18"/></linearGradient>'
        "</defs>",
        f'<rect width="{W}" height="{gh:.1f}" fill="url(#sg)"/>',
    ]
    eye = []
    ganga = []
    b[0] = b[0].replace("</defs>", f'<rect id="c" width="{cell:.1f}" height="{cell:.1f}" rx="1.4"/></defs>')
    off = (pitch - cell) / 2
    for r, row in enumerate(rows):
        groups = {}  # (fill, opacity) → [use, …]
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            use = f'<use href="#c" x="{c*pitch+off:.1f}" y="{r*pitch+off:.1f}"/>'
            if ch == "E":
                eye.append((c * pitch + off, r * pitch + off))
                key = (t["accent"], 1.0)
            elif ch.islower():
                lvl = "abcd".index(ch)
                jitter = rnd.uniform(0.82, 1.0) if lvl >= 2 else rnd.uniform(0.7, 1.15)
                key = (t["ink"], round(min(ink_op[lvl] * jitter, 1) * 20) / 20)  # 5% buckets
            else:
                lvl = "ABCD".index(ch)
                if ch == "A":
                    ganga.append(use)
                    continue
                key = (t["accent"], acc_op[lvl])
            groups.setdefault(key, []).append(use)
        if groups:
            body = "".join(f'<g fill="{f}" opacity="{o:g}">{"".join(u)}</g>' for (f, o), u in groups.items())
            # rise from the earth: bottom rows appear first
            b.append("<g>" + body + anim("opacity", 0, 1, (R_ - r) * 0.035, 0.4, ease=False) + "</g>")
    if ganga:  # the Ganga shimmers
        b.append(f'<g fill="{t["accent"]}" opacity="{acc_op[0]}">' + "".join(ganga) +
                 '<animate attributeName="opacity" values="{acc_op[0]};.12;{acc_op[0]}" dur="3.2s" repeatCount="indefinite"/></g>')
    if eye:
        ex = sum(x for x, _ in eye) / len(eye) + cell / 2
        ey = sum(y for _, y in eye) / len(eye) + cell / 2
        b.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="38" fill="url(#eyeglow)">'
                 f'<animate attributeName="r" values="22;44;22" dur="3s" repeatCount="indefinite"/></circle>')
        b.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="6" fill="none" stroke="{t["accent"]}" stroke-width="1.2" opacity="0">'
                 f'<animate attributeName="r" values="6;90" dur="3s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values=".8;0" dur="3s" repeatCount="indefinite"/></circle>')
    # slow meditative scanline
    b.append(f'<rect x="0" y="-60" width="{W}" height="60" fill="url(#scan)">'
             f'<animate attributeName="y" values="-60;{gh:.0f}" dur="9s" repeatCount="indefinite"/></rect>')
    # overlay labels
    b.append(text(16, 26, "00 — INVOCATION", 11, t["muted"], ls=3))
    b.append(text(W - 16, 26, f"{C_} × {R_} CELLS · {sum(ch != '.' for row in rows for ch in row):,} LIT", 11,
                  t["muted"], anchor="end", ls=2))
    # caption band
    cy = gh + 22
    b.append(line(0, cy, W, cy, t["line"]))
    b.append(line(0, cy, 46, cy, t["accent"], 2))
    b.append(text(0, cy + 44, "ॐ नमः शिवाय", 26, t["ink"], DEVA, 600))
    b.append(text(0, cy + 66, "OM NAMAH SHIVAYA", 11, t["muted"], ls=3))
    b.append(text(W / 2, cy + 44, "LEVEL 0 · · · · LEVEL 4", 10, t["muted"], anchor="middle", ls=2))
    for i, op in enumerate([0.45, *ink_op[1:], 1]):
        fill = t["line"] if i == 0 else (t["accent"] if i == 4 else t["ink"])
        b.append(f'<rect x="{W/2 - 52 + i*22:.1f}" y="{cy+52}" width="14" height="14" rx="2.5" fill="{fill}" opacity="{op}"/>')
    b.append(text(W, cy + 44, "हर हर महादेव", 26, t["ink"], DEVA, 600, anchor="end"))
    b.append(text(W, cy + 66, "FIG. 0 — MAHADEV, IN CONTRIBUTION CELLS", 11, t["muted"], anchor="end", ls=2.5))
    return svg(W, int(H), "".join(b), "Lord Shiva (Mahadev) in meditation on Kailash with trishul and damru, drawn in contribution-graph cells. Om Namah Shivaya.")


# ─── Footer ──────────────────────────────────────────────────────────────────
def footer(t):
    H = 120
    b = [
        ruler(14, t, 0, W),
        text(0, 64, "यत भावो तत भवति", 22, t["ink"], DEVA, 500),
        text(0, 92, "AS YOU FEEL, SO YOU BECOME.", 11, t["muted"], ls=3),
        text(W - 22, 64, "EOF · cyberRuptor", 13, t["muted"], anchor="end", ls=2),
        f'<rect x="{W-14}" y="51" width="10" height="16" fill="{t["accent"]}">'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" repeatCount="indefinite"/></rect>',
        text(W, 92, "UNAUTHORISED ACCESS ENCOURAGED", 11, t["muted"], anchor="end", ls=3),
    ]
    return svg(W, H, "".join(b), "यत भावो तत भवति — as you feel, so you become.")


# ─── Build ───────────────────────────────────────────────────────────────────
def main():
    for name, t in THEMES.items():
        write("shiva", name, shiva(t))
        write("hero", name, hero(t))
        write("pipeline", name, pipeline(t))
        write("toolkit", name, toolkit(t))
        write("footer", name, footer(t))
        for slug, num, label, note in HEADERS:
            write(f"h-{slug}", name, header(t, num, label, note))
        write("contact", name, contact_hero(t))
        for c in CONTACTS:
            write(f"contact-{c['slug']}", name, contact_card(t, c))
        for p in PROJECTS:
            write(f"card-{p['slug']}", name, card(t, p))
    print(f"built {len(list(OUT.glob('*.svg')))} svgs → {OUT}")


if __name__ == "__main__":
    main()
