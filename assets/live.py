#!/usr/bin/env python3
"""
cyberRuptor profile — live telemetry.

Pulls real data from the GitHub API and renders on-brand SVGs into assets/live/.
Runs daily via .github/workflows/live.yml; also works locally without a token
(the contribution calendar is then read from the public contributions page).

    GITHUB_TOKEN=... python3 assets/live.py
"""
import base64
import datetime as dt
import functools
import html
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter, OrderedDict

from build import THEMES, SANS, MONO, W, svg, text, line, esc, ruler  # shared design tokens

USER = os.environ.get("PROFILE_USER", "cyberRuptor")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live")

# Orgs that don't appear publicly (private membership / workplace). Shown first.
# Tip: make an org membership public (org → People → your name → Public) and it
# will be picked up automatically.
# Repos never shown anywhere on the profile (network panel + live log),
# even if GitHub reports them as public. Match "owner/repo" or a whole "owner/".
HIDE_REPOS = [
    "iitdeveloper-git/iitdeveloper-website",
    "iitdeveloper-git/oryne_web",
]


def hidden(full_name):
    full_name = full_name.lower()
    return any(full_name == h.lower() or (h.endswith("/") and full_name.startswith(h.lower())) for h in HIDE_REPOS)


EXTRA_ORGS = [
    dict(name="Airtel Digital", role="WORKPLACE · DEVSECOPS", login=None),
]

NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date()
SYNCED = NOW.strftime("SYNCED %Y-%m-%d %H:%M UTC")


# ─── HTTP ────────────────────────────────────────────────────────────────────
def req(url, data=None, raw=False):
    headers = {"User-Agent": f"{USER}-profile-renderer", "Accept": "application/vnd.github+json"}
    if TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        data = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as r:
        body = r.read()
    return body if raw else json.loads(body)


def api(path):
    return req("https://api.github.com" + path)


@functools.lru_cache(maxsize=None)
def avatar_data_uri(url, size=96):
    """Images inside an <img>-rendered SVG can't load external URLs, so inline them."""
    try:
        sep = "&" if "?" in url else "?"
        b = req(f"{url}{sep}s={size}", raw=True)
        return "data:image/png;base64," + base64.b64encode(b).decode()
    except Exception as e:  # noqa: BLE001
        print("  avatar failed:", e)
        return None


# ─── Data ────────────────────────────────────────────────────────────────────
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def calendar():
    """[(date, count, level)] for the trailing year."""
    if TOKEN:
        q = """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
               weeks{contributionDays{date contributionCount contributionLevel}}}}}}"""
        d = req("https://api.github.com/graphql", {"query": q, "variables": {"u": USER}})
        weeks = d["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        return [
            (dt.date.fromisoformat(x["date"]), x["contributionCount"], LEVELS[x["contributionLevel"]])
            for w in weeks for x in w["contributionDays"]
        ]
    if os.environ.get("CALENDAR_HTML"):  # local preview: pre-downloaded contributions page
        with open(os.environ["CALENDAR_HTML"], encoding="utf-8") as f:
            page = f.read()
    else:
        page = req(f"https://github.com/users/{USER}/contributions", raw=True).decode()
    cells = {m[1]: (m[0], int(m[2])) for m in re.findall(
        r'data-date="([\d-]+)"\s+id="([^"]+)"\s+data-level="(\d)"', page)}
    tips = dict(re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)', page))
    days = []
    for cid, (date, lvl) in cells.items():
        m = re.match(r"\s*(\d[\d,]*) contribution", tips.get(cid, ""))
        days.append((dt.date.fromisoformat(date), int(m[1].replace(",", "")) if m else 0, lvl))
    return sorted(days)


def gather():
    print("fetching profile…")
    user = api(f"/users/{USER}")
    repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
    own = [r for r in repos if not r["fork"]]
    langs = Counter()
    for r in own:
        for k, v in api(f"/repos/{USER}/{r['name']}/languages").items():
            langs[k] += v

    def count(q, kind="issues"):
        return api(f"/search/{kind}?q={urllib.parse.quote(q)}&per_page=1")["total_count"]

    stats = OrderedDict(
        commits=count(f"author:{USER}", "commits"),
        prs=count(f"author:{USER} type:pr"),
        merged=count(f"author:{USER} type:pr is:merged"),
        issues=count(f"author:{USER} type:issue"),
        stars=sum(r["stargazers_count"] for r in own),
        repos=len(own),
        followers=user["followers"],
    )

    # contributed-to: repos (not mine) I've opened PRs against
    prs = api(f"/search/issues?q={urllib.parse.quote(f'author:{USER} type:pr -user:{USER}')}&per_page=100")["items"]
    contrib = OrderedDict()  # full_name → {prs, merged, open, meta}
    meta = {}
    for i in prs:
        full = i["repository_url"].split("/repos/")[1]
        if hidden(full):
            continue
        if full not in meta:  # only repos that are public right now
            try:
                r = api(f"/repos/{full}")
                meta[full] = r if r.get("visibility") == "public" and not r.get("private") else None
            except Exception:  # noqa: BLE001  (404 → private or deleted)
                meta[full] = None
        if not meta[full]:
            continue
        c = contrib.setdefault(full, dict(prs=0, merged=0, open=0, meta=meta[full]))
        c["prs"] += 1
        if (i.get("pull_request") or {}).get("merged_at"):
            c["merged"] += 1
        elif i.get("state") == "open":
            c["open"] += 1

    starred = [r for r in api(f"/users/{USER}/starred?per_page=12")
               if not r.get("private") and not hidden(r["full_name"]) and r["owner"]["login"].lower() != USER.lower()][:4]

    orgs = api(f"/users/{USER}/orgs")
    events = [e for e in api(f"/users/{USER}/events/public?per_page=60") if not hidden(e["repo"]["name"])]

    print("fetching contribution calendar…")
    days = calendar()
    return dict(user=user, langs=langs, stats=stats, contrib=contrib, starred=starred, orgs=orgs, events=events, days=days)


# ─── Helpers ─────────────────────────────────────────────────────────────────
def fmt(n):
    return f"{n/1000:.1f}k" if n >= 10000 else f"{n:,}"


def ordinal_day(d):
    return d.strftime("%d %b").lstrip("0").upper()


def streaks(days):
    longest = cur = run = 0
    for _, c, _ in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    seq = [c for d, c, _ in days if d <= TODAY]
    if seq and seq[-1] == 0:  # today not yet active — streak still alive from yesterday
        seq = seq[:-1]
    for c in reversed(seq):
        if not c:
            break
        cur += 1
    return cur, longest


def stamp(t, x, y, anchor="end"):
    return (
        f'<circle cx="{x - (len(SYNCED)*8.1 + 12 if anchor == "end" else -6)}" cy="{y-4}" r="3.5" fill="{t["accent"]}">'
        f'<animate attributeName="opacity" values="1;.2;1" dur="1.6s" repeatCount="indefinite"/></circle>'
        + text(x, y, SYNCED, 11, t["muted"], anchor=anchor, ls=1.5)
    )


def anim(attr, frm, to, delay, dur, ease=True):
    """Intro animation that starts at t=0 (no flash) and rests on the final value.
    The element's own attribute must hold the FINAL value, so renderers without
    SMIL support still show the finished graphic."""
    total = delay + dur
    k = delay / total if total else 0
    spline = ' calcMode="spline" keySplines="0 0 1 1;.2 .7 .2 1"' if ease else ""
    return (f'<animate attributeName="{attr}" values="{frm};{frm};{to}" keyTimes="0;{k:.3f};1" '
            f'dur="{total:.2f}s" fill="freeze"{spline}/>')


def level_fill(t, lvl):
    if lvl == 0:
        return t["line"], 1
    return t["accent"], (0.28, 0.5, 0.75, 1)[lvl - 1]


# ─── 1 · KPI strip ───────────────────────────────────────────────────────────
def kpis(t, D):
    s = D["stats"]
    cur, longest = streaks(D["days"])
    total = sum(c for _, c, _ in D["days"])
    items = [
        ("CONTRIBUTIONS", fmt(total), "trailing 12 months"),
        ("CURRENT STREAK", f"{cur}d", f"longest {longest}d"),
        ("COMMITS", fmt(s["commits"]), "all-time, public"),
        ("PULL REQUESTS", fmt(s["prs"]), f"{s['merged']} merged"),
        ("ISSUES", fmt(s["issues"]), "opened"),
        ("STARS", fmt(s["stars"]), f"across {s['repos']} repos"),
    ]
    H, cw = 132, W / len(items)
    b = [line(0, 0.5, W, 0.5, t["line"]), line(0, H - 0.5, W, H - 0.5, t["line"])]
    for i, (lbl, val, sub) in enumerate(items):
        x = i * cw + (0 if i == 0 else 20)
        if i:
            b.append(line(i * cw, 18, i * cw, H - 18, t["line"]))
        b.append(text(x, 34, lbl, 11, t["muted"], ls=2))
        b.append(
            f'<text x="{x}" y="86" font-family="{SANS}" font-size="44" font-weight="800" letter-spacing="-1.5" '
            f'fill="{t["accent"] if i == 1 else t["ink"]}">{esc(val)}'
            + anim("opacity", 0, 1, i * 0.12, 0.6) + anim("y", 98, 86, i * 0.12, 0.6) + "</text>"
        )
        b.append(text(x, 112, sub, 11, t["muted"]))
    return svg(W, H, "".join(b), "Stats: " + "; ".join(f"{a} {v}" for a, v, _ in items))


# ─── 2 · Contribution heatmap ────────────────────────────────────────────────
def heatmap(t, D):
    days = D["days"]
    first = days[0][0] - dt.timedelta(days=(days[0][0].weekday() + 1) % 7)  # back to Sunday
    pitch, cell, x0, y0 = 21, 17, 44, 44
    ncols = (days[-1][0] - first).days // 7 + 1
    H = y0 + 7 * pitch + 58
    b = []
    # weekday labels
    for r, lbl in ((1, "MON"), (3, "WED"), (5, "FRI")):
        b.append(text(0, y0 + r * pitch + 13, lbl, 10, t["muted"], ls=1))
    # month labels
    seen = None
    for d, _, _ in days:
        if d.day <= 7 and d.weekday() == 6 or d == days[0][0]:
            col = (d - first).days // 7
            m = d.strftime("%b").upper()
            if m != seen and col < ncols - 1:
                b.append(text(x0 + col * pitch, y0 - 14, m, 10, t["muted"], ls=1.5))
                seen = m
    # cells — sweep in left→right like a scanline
    best = max(days, key=lambda x: x[1])
    for d, c, lvl in days:
        col, row = (d - first).days // 7, (d.weekday() + 1) % 7
        x, y = x0 + col * pitch, y0 + row * pitch
        fill, op = level_fill(t, lvl)
        delay = col * 0.025 + row * 0.01
        b.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{fill}" opacity="{op}">'
            f'<title>{c} contribution{"s" if c != 1 else ""} · {d.isoformat()}</title>'
            + anim("opacity", 0, op, delay, 0.35, ease=False) + "</rect>"
        )
        if d == TODAY:
            b.append(f'<rect x="{x-2.5}" y="{y-2.5}" width="{cell+5}" height="{cell+5}" rx="4.5" fill="none" '
                     f'stroke="{t["ink"]}" stroke-width="1.2"><animate attributeName="opacity" values="1;.2;1" '
                     f'dur="1.6s" repeatCount="indefinite"/></rect>')
    # footer: legend + annotations
    fy = y0 + 7 * pitch + 34
    b.append(text(x0, fy, "LESS", 10, t["muted"], ls=1.5))
    for i in range(5):
        fill, op = level_fill(t, i)
        b.append(f'<rect x="{x0 + 40 + i*18}" y="{fy-11}" width="13" height="13" rx="2.5" fill="{fill}" opacity="{op}"/>')
    b.append(text(x0 + 40 + 5 * 18 + 6, fy, "MORE", 10, t["muted"], ls=1.5))
    active = sum(1 for _, c, _ in days if c)
    b.append(text(x0 + 260, fy, f"BEST DAY {best[1]} · {ordinal_day(best[0])} {best[0].year}    ACTIVE {active}/{len(days)} DAYS",
                  10, t["muted"], ls=1.5))
    b.append(stamp(t, W, fy))
    return svg(W, H, "".join(b), f"Contribution heatmap, last 12 months: {sum(c for _,c,_ in days)} contributions.")


# ─── 3 · Weekly activity line chart ──────────────────────────────────────────
def nice_max(v):
    if v <= 4:
        return 4
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * mag:
            return m * mag
    return v


def activity(t, D):
    days = D["days"]
    weeks = OrderedDict()
    for d, c, _ in days:
        wk = d - dt.timedelta(days=(d.weekday() + 1) % 7)
        weeks[wk] = weeks.get(wk, 0) + c
    keys, vals = list(weeks), list(weeks.values())
    H, L, R, T, B = 330, 48, W - 8, 40, 270
    top = nice_max(max(vals) or 1)
    n = len(vals)
    X = lambda i: L + (R - L) * i / (n - 1)
    Y = lambda v: B - (B - T) * v / top
    b = [
        "<defs>"
        f'<linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["accent"]}" stop-opacity=".30"/>'
        f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="reveal"><rect x="0" y="0" width="{W}" height="{H}">'
        + anim("width", 0, W, 0.1, 2.2) + "</rect></clipPath>"
        "</defs>"
    ]
    # grid
    for k in range(5):
        v = top * k / 4
        y = Y(v)
        b.append(line(L, y, R, y, t["line"], 1, "" if k == 0 else 'stroke-dasharray="2 5"'))
        b.append(text(L - 12, y + 4, f"{v:g}", 10, t["muted"], anchor="end"))
    # month ticks
    last = None
    for i, k in enumerate(keys):
        if k.month != last and i < n - 2:
            b.append(line(X(i), B, X(i), B + 6, t["faint"]))
            b.append(text(X(i), B + 22, k.strftime("%b").upper(), 10, t["muted"], ls=1.5))
            last = k.month
    pts = [(X(i), Y(v)) for i, v in enumerate(vals)]

    # smooth path (Catmull-Rom → Bézier)
    def smooth(p):
        d = f"M{p[0][0]:.1f} {p[0][1]:.1f}"
        for i in range(len(p) - 1):
            p0, p1, p2 = p[max(i - 1, 0)], p[i], p[i + 1]
            p3 = p[min(i + 2, len(p) - 1)]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, min(B, p1[1] + (p2[1] - p0[1]) / 6))
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, min(B, p2[1] - (p3[1] - p1[1]) / 6))
            d += f" C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
        return d

    curve = smooth(pts)
    ma = [sum(vals[max(0, i - 3): i + 1]) / len(vals[max(0, i - 3): i + 1]) for i in range(n)]
    g = ['<g clip-path="url(#reveal)">']
    g.append(f'<path d="{curve} L{pts[-1][0]:.1f} {B} L{pts[0][0]:.1f} {B} Z" fill="url(#ag)"/>')
    g.append(f'<path d="{smooth([(X(i), Y(v)) for i, v in enumerate(ma)])}" fill="none" stroke="{t["muted"]}" '
             f'stroke-width="1.2" stroke-dasharray="4 4"/>')
    g.append(f'<path d="{curve}" fill="none" stroke="{t["accent"]}" stroke-width="2.2" stroke-linejoin="round"/>')
    # peak
    pi = max(range(n), key=lambda i: vals[i])
    px, py = pts[pi]
    g.append(line(px, py, px, T - 6, t["faint"], 1, 'stroke-dasharray="2 3"'))
    g.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{t["page"]}" stroke="{t["accent"]}" stroke-width="2"/>')
    anchor = "end" if px > W - 260 else "start"
    g.append(text(px + (-8 if anchor == "end" else 8), T - 10,
                  f"PEAK {vals[pi]} · WK OF {ordinal_day(keys[pi])}", 10, t["ink"], anchor=anchor, ls=1.5, weight=700))
    g.append("</g>")
    b.append("".join(g))
    # live head
    lx, ly = pts[-1]
    b.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="{t["accent"]}"/>')
    b.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="none" stroke="{t["accent"]}" stroke-width="1.5">'
             f'<animate attributeName="r" values="4;14" dur="1.8s" repeatCount="indefinite"/>'
             f'<animate attributeName="opacity" values="1;0" dur="1.8s" repeatCount="indefinite"/></circle>')
    # legend
    ly2 = H - 6
    b.append(line(L, ly2 - 4, L + 26, ly2 - 4, t["accent"], 2.2))
    b.append(text(L + 34, ly2, "contributions / week", 11, t["muted"]))
    b.append(line(L + 200, ly2 - 4, L + 226, ly2 - 4, t["muted"], 1.2, 'stroke-dasharray="4 4"'))
    b.append(text(L + 234, ly2, "4-week moving average", 11, t["muted"]))
    b.append(stamp(t, W - 8, ly2))
    return svg(W, H, "".join(b), f"Weekly contributions over the last year; peak {vals[pi]} in week of {keys[pi]}.")


# ─── 4 · Rhythm (weekday) + language mix ─────────────────────────────────────
def rhythm(t, D):
    H = 290
    b = []
    # left: weekday distribution
    wd = [0] * 7
    for d, c, _ in D["days"]:
        wd[(d.weekday() + 1) % 7] += c
    names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    top, hi = max(wd) or 1, max(range(7), key=lambda i: wd[i])
    b.append(text(0, 20, "WEEKLY RHYTHM", 11, t["muted"], ls=2.5))
    b.append(text(540, 20, f"MOST ACTIVE · {names[hi]}", 11, t["accent"], anchor="end", ls=2, weight=700))
    base, bw, gap = 240, 56, 25
    for i, v in enumerate(wd):
        h = max(3, 170 * v / top)
        x = i * (bw + gap)
        fill = t["accent"] if i == hi else t["ink"]
        op = 1 if i == hi else 0.82
        b.append(
            f'<rect x="{x}" y="{base-h:.1f}" width="{bw}" height="{h:.1f}" rx="3" fill="{fill}" opacity="{op}">'
            + anim("height", 0, f"{h:.1f}", i * 0.08, 0.7) + anim("y", base, f"{base-h:.1f}", i * 0.08, 0.7) + "</rect>"
        )
        b.append(text(x + bw / 2, base - h - 8, str(v), 11, t["ink"], anchor="middle"))
        b.append(text(x + bw / 2, base + 22, names[i], 10, t["muted"], anchor="middle", ls=1.5))
    b.append(line(-4, base + 0.5, 7 * (bw + gap) - gap + 4, base + 0.5, t["faint"]))

    # right: language mix
    X0, X1 = 640, W
    b.append(line(600, 0, 600, H, t["line"]))
    total = sum(D["langs"].values()) or 1
    top_l = D["langs"].most_common(5)
    other = total - sum(v for _, v in top_l)
    if other > 0:
        top_l.append(("Other", other))
    b.append(text(X0, 20, "LANGUAGE MIX", 11, t["muted"], ls=2.5))
    b.append(text(X1, 20, "BY BYTES · OWN REPOS", 11, t["muted"], anchor="end", ls=2))
    shades = [(t["accent"], 1), (t["ink"], 0.9), (t["ink"], 0.6), (t["ink"], 0.38), (t["muted"], 0.5), (t["faint"], 1)]
    x, bar_w = X0, X1 - X0
    for i, (name, v) in enumerate(top_l):
        w = bar_w * v / total
        c, op = shades[i]
        b.append(f'<rect x="{x:.1f}" y="44" width="{max(w-2,1):.1f}" height="14" fill="{c}" opacity="{op}">'
                 + anim("opacity", 0, op, 0.3 + i * 0.12, 0.4) + "</rect>")
        x += w
    for i, (name, v) in enumerate(top_l):
        y = 100 + i * 31
        c, op = shades[i]
        b.append(f'<rect x="{X0}" y="{y-10}" width="10" height="10" fill="{c}" opacity="{op}"/>')
        b.append(text(X0 + 22, y, name, 16, t["ink"], SANS, 500))
        b.append(line(X0 + 170, y - 4, X1 - 70, y - 4, t["line"], 1, 'stroke-dasharray="1 4"'))
        b.append(text(X1, y, f"{100*v/total:.1f}%", 13, t["ink"], anchor="end"))
    return svg(W, H, "".join(b), "Weekly rhythm and language mix.")


# ─── 5 · Organisations + contributed-to + radar ──────────────────────────────
def network(t, D):
    members = [dict(name=o["name"], role=o["role"], avatar=None, login=o["login"]) for o in EXTRA_ORGS]
    for o in D["orgs"]:
        members.append(dict(name=o["login"], role="MEMBER", avatar=avatar_data_uri(o["avatar_url"]), login=o["login"]))
    contrib = sorted(D["contrib"].items(), key=lambda kv: (-kv[1]["merged"], -kv[1]["prs"]))[:4]
    owners = {}
    for full, _ in contrib:
        owner = full.split("/")[0]
        if owner not in owners:
            owners[owner] = avatar_data_uri(f"https://github.com/{owner}.png")

    RX = 640               # right column x
    ROW = 100
    left_h = 46 + len(members) * 84 + 20 + 4 * 30
    right_h = 70 + max(len(contrib), 1) * ROW
    top_h = max(left_h, right_h) + 10
    star = D.get("starred") or []
    H = top_h + (230 if star else 0)

    b = [
        "<defs>"
        '<filter id="mono"><feColorMatrix type="saturate" values="0"/></filter>'
        '<clipPath id="av"><circle cx="24" cy="24" r="24"/></clipPath>'
        "</defs>",
        text(0, 20, "MEMBER OF", 11, t["muted"], ls=2.5),
        text(RX, 20, "CONTRIBUTED TO", 11, t["muted"], ls=2.5),
        line(600, 0, 600, top_h - 20, t["line"]),
    ]
    tot = sum(c["prs"] for _, c in D["contrib"].items())
    mer = sum(c["merged"] for _, c in D["contrib"].items())
    if tot:
        b.append(text(W, 20, f"{tot} PRS UPSTREAM · {mer} MERGED · {100*mer/tot:.0f}% MERGE RATE", 11,
                      t["accent"], anchor="end", ls=1.8, weight=700))

    def avatar_or_mark(name, avatar, hot=False):
        if avatar:
            return (f'<g clip-path="url(#av)"><image href="{avatar}" width="48" height="48" filter="url(#mono)"/></g>'
                    f'<circle cx="24" cy="24" r="24" fill="none" stroke="{t["line"]}"/>')
        hp = " ".join(f"{24+23*math.cos(math.radians(-90+i*360/7)):.1f},{24+23*math.sin(math.radians(-90+i*360/7)):.1f}"
                      for i in range(7))
        mono = "".join(w[0] for w in re.split(r"[\s_-]+", name)[:2] if w).upper()
        return (f'<polygon points="{hp}" fill="none" stroke="{t["accent"] if hot else t["ink"]}" stroke-width="1.4"/>'
                + text(24, 29, mono, 14, t["ink"], SANS, 800, anchor="middle"))

    # left: memberships + profile facts
    for i, m in enumerate(members):
        y = 46 + i * 84
        b.append(f'<g transform="translate(0 {y})">' + avatar_or_mark(m["name"], m["avatar"], hot=i == 0)
                 + text(66, 20, m["name"], 18, t["ink"], SANS, 700, ls=-0.3)
                 + text(66, 42, m["role"], 11, t["muted"], ls=1.5) + "</g>")
    u = D["user"]
    since = dt.date.fromisoformat(u["created_at"][:10])
    facts = [("ON GITHUB SINCE", since.strftime("%b %Y").upper()), ("PUBLIC REPOS", str(u["public_repos"])),
             ("FOLLOWERS", str(u["followers"])), ("BASED IN", (u.get("location") or "—").upper())]
    fy = 46 + len(members) * 84 + 20
    b.append(line(0, fy - 18, 560, fy - 18, t["line"]))
    for i, (k, v) in enumerate(facts):
        y = fy + i * 30
        b.append(text(0, y, k, 11, t["muted"], ls=2))
        b.append(line(170, y - 4, 470, y - 4, t["line"], 1, 'stroke-dasharray="1 4"'))
        b.append(text(560, y, v, 13, t["ink"], anchor="end", weight=700, ls=1))

    # right: upstream repos, enriched
    if not contrib:
        b.append(text(RX, 80, "— no public upstream contributions yet —", 13, t["muted"]))
    for i, (full, c) in enumerate(contrib):
        owner, repo = full.split("/")
        m = c["meta"]
        y = 46 + i * ROW
        sub = " · ".join(x for x in (owner.upper(), (m.get("language") or "").upper(), f"★ {m.get('stargazers_count', 0)}") if x)
        g = [f'<g transform="translate({RX} {y})">', avatar_or_mark(repo, owners.get(owner)),
             text(66, 20, repo, 18, t["ink"], SANS, 700, ls=-0.3),
             text(66, 42, sub, 11, t["muted"], ls=1.5),
             text(W - RX, 26, str(c["merged"]), 26, t["accent"], SANS, 800, anchor="end"),
             text(W - RX, 44, "MERGED" + (f" · +{c['open']} OPEN" if c["open"] else ""), 9, t["muted"], anchor="end", ls=1.8)]
        # merge-rate bar
        bw = W - RX - 66
        frac = c["merged"] / c["prs"] if c["prs"] else 0
        g.append(f'<rect x="66" y="60" width="{bw}" height="3" rx="1.5" fill="{t["line"]}"/>')
        g.append(f'<rect x="66" y="60" width="{bw*frac:.1f}" height="3" rx="1.5" fill="{t["accent"]}">'
                 + anim("width", 0, f"{bw*frac:.1f}", 0.2 + i * 0.15, 0.8) + "</rect>")
        g.append(text(66, 80, f"{c['prs']} PR{'S' if c['prs'] != 1 else ''} · {100*frac:.0f}% MERGED", 9, t["muted"], ls=1.8))
        g.append("</g>")
        b.append("".join(g))

    # bottom: on the radar (recently starred)
    if star:
        y0 = top_h
        b.append(line(0, y0 - 10, W, y0 - 10, t["line"]))
        b.append(text(0, y0 + 22, "ON THE RADAR", 11, t["muted"], ls=2.5))
        b.append(text(W, y0 + 22, "RECENTLY STARRED", 11, t["muted"], anchor="end", ls=2))
        cw = (W - 3 * 24) / 4
        for i, r in enumerate(star):
            x = i * (cw + 24)
            desc = " ".join((r.get("description") or "").split())
            words, lines_, cur = desc.split(), [], ""
            for w_ in words:
                if len(cur) + len(w_) + 1 > 36:
                    lines_.append(cur); cur = w_
                else:
                    cur = (cur + " " + w_).strip()
            if cur:
                lines_.append(cur)
            if len(lines_) > 3:
                lines_ = lines_[:3]; lines_[2] = clip(lines_[2] + "…", 36)
            g = [f'<rect x="{x+0.5}" y="{y0+40.5}" width="{cw-1}" height="168" rx="10" fill="none" stroke="{t["line"]}"/>',
                 line(x + 18, y0 + 40.5, x + 46, y0 + 40.5, t["accent"], 2),
                 text(x + 18, y0 + 70, f"R/{i+1:02d}", 10, t["accent"], weight=700, ls=2),
                 text(x + 18, y0 + 98, clip(r["name"], 24), 17, t["ink"], SANS, 700, ls=-0.3),
                 text(x + 18, y0 + 116, clip(r["owner"]["login"].upper(), 28), 10, t["muted"], ls=1.5)]
            for k, ln in enumerate(lines_):
                g.append(text(x + 18, y0 + 140 + k * 17, ln, 12, t["muted"], SANS))
            foot = " · ".join(v for v in ((r.get("language") or ""), f"★ {fmt(r.get('stargazers_count', 0))}") if v)
            g.append(text(x + 18, y0 + 196, foot, 11, t["ink"]))
            b.append("".join(g))
    return svg(W, H, "".join(b), "Organisations, upstream contributions, and recently starred repositories.")


# ─── 6 · Live activity log ───────────────────────────────────────────────────
def describe(e):
    p, typ = e["payload"], e["type"]
    if typ == "PushEvent":
        n = p.get("size") or len(p.get("commits") or []) or None
        ref = (p.get("ref") or "").replace("refs/heads/", "")
        return "PUSH", (f"{n} commit{'s' if n != 1 else ''} → {ref}" if n else f"pushed → {ref}")
    if typ == "PullRequestEvent":
        pr = p.get("pull_request") or {}
        act = "merged" if p.get("action") == "closed" and pr.get("merged") else p.get("action", "")
        return "PR", f"#{p.get('number')} {act} {pr.get('title') or ''}".strip()
    if typ == "IssuesEvent":
        return "ISSUE", f"#{p['issue']['number']} {p.get('action')} {p['issue'].get('title','')}"
    if typ == "IssueCommentEvent":
        return "COMMENT", f"on #{p['issue']['number']} {p['issue'].get('title','')}"
    if typ == "PullRequestReviewEvent":
        return "REVIEW", f"#{p['pull_request']['number']} {p['review'].get('state','').lower()}"
    if typ == "CreateEvent":
        return "CREATE", f"{p.get('ref_type')} {p.get('ref') or ''}".strip()
    if typ == "DeleteEvent":
        return "DELETE", f"{p.get('ref_type')} {p.get('ref') or ''}"
    if typ == "WatchEvent":
        return "STAR", "starred"
    if typ == "ForkEvent":
        return "FORK", f"→ {p['forkee']['full_name']}"
    if typ == "ReleaseEvent":
        return "RELEASE", p["release"].get("tag_name", "")
    if typ == "PublicEvent":
        return "PUBLIC", "open-sourced"
    return typ.replace("Event", "").upper()[:8], ""


def clip(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def logbox(t, D):
    evs = sorted(D["events"], key=lambda e: e["created_at"], reverse=True)[:9]
    H = 84 + max(len(evs), 1) * 30 + 40
    b = [
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="none" stroke="{t["line"]}"/>',
        line(0.5, 44, W - 0.5, 44, t["line"]),
        text(24, 28, f"$ tail -f /var/log/{USER.lower()}.log", 13, t["ink"]),
        stamp(t, W - 24, 28),
    ]
    for i, e in enumerate(evs):
        y = 80 + i * 30
        ts = dt.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
        tag, msg = describe(e)
        hot = tag in ("PR", "RELEASE", "PUBLIC")
        delay = 0.2 + i * 0.12
        row = "".join([
            text(24, y, ts.strftime("%Y-%m-%d %H:%M"), 13, t["muted"]),
            text(200, y, tag, 13, t["accent"] if hot else t["ink"], weight=700, ls=1),
            text(300, y, clip(e["repo"]["name"], 40), 13, t["ink"]),
            text(660, y, clip(html.unescape(msg), 62), 13, t["muted"]),
        ])
        b.append(f'<g>{row}' + anim("opacity", 0, 1, delay, 0.3, ease=False) + "</g>")
    cy = 80 + len(evs) * 30
    b.append(text(24, cy, "$", 13, t["ink"]))
    b.append(f'<rect x="40" y="{cy-12}" width="9" height="16" fill="{t["accent"]}">'
             f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" repeatCount="indefinite"/></rect>')
    return svg(W, H, "".join(b), "Recent public GitHub activity.")


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    D = gather()
    if not D["days"]:
        sys.exit("no calendar data — refusing to overwrite existing graphics")
    os.makedirs(OUT, exist_ok=True)
    renderers = dict(kpis=kpis, heatmap=heatmap, activity=activity, rhythm=rhythm, network=network, log=logbox)
    for theme, t in THEMES.items():
        for name, fn in renderers.items():
            try:
                content = fn(t, D)
                with open(os.path.join(OUT, f"{name}-{theme}.svg"), "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:  # keep the previous file if one graphic fails
                print(f"  ! {name}-{theme}: {e}")
    print(f"rendered → {OUT}  ({SYNCED})")


if __name__ == "__main__":
    main()
