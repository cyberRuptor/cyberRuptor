#!/usr/bin/env python3
"""
cyberRuptor profile — the profile heals itself.

A small, real version of the self-healing pipeline from my Medium series, running
on this repository's own workflows (.github/workflows/heal.yml):

    workflow fails  → open an incident issue → retry with backoff (2m · 6m · 15m)
    workflow passes → close the incident, record time-to-recovery
    retries exhausted → label `needs-human` and leave it open

Incidents live in assets/live/incidents.json; the panel is assets/live/health-*.svg.

    python3 assets/heal.py fail|pass     # CI: WF, RUN_ID, ATTEMPT, RUN_URL, EVENT_AT, GH_TOKEN
    python3 assets/heal.py render
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time

from build import THEMES, SANS, W, svg, text, line, anim

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "live")
STATE = os.path.join(OUT, "incidents.json")
REPO = os.environ.get("GITHUB_REPOSITORY", "cyberRuptor/cyberRuptor")
BACKOFF_MIN = [2, 6, 15]          # minutes before retry #1, #2, #3
WINDOW = 90                       # days
NOW = dt.datetime.now(dt.timezone.utc)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def load():
    try:
        return json.load(open(STATE))
    except Exception:  # noqa: BLE001
        return dict(since=iso(NOW), incidents=[])


def save(S):
    os.makedirs(OUT, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(S, f, indent=2)
        f.write("\n")


def gh(*args, check=True):
    p = subprocess.run(["gh", *args, "--repo", REPO], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and p.returncode:
        raise RuntimeError(f"gh {args[0]} {args[1]} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def human(minutes):
    m = round(minutes)
    return f"{m}m" if m < 60 else (f"{m // 60}h {m % 60:02d}m" if m < 1440 else f"{m / 1440:.1f}d")


# ─── Event handlers ──────────────────────────────────────────────────────────
def on_fail(S):
    wf, run_id = os.environ["WF"], os.environ["RUN_ID"]
    attempt = int(os.environ.get("ATTEMPT") or 1)
    at = os.environ.get("EVENT_AT") or iso(NOW)
    url = os.environ.get("RUN_URL", "")
    inc = next((i for i in S["incidents"] if i["workflow"] == wf and not i.get("closed_at")), None)
    if not inc:
        gh("label", "create", "incident", "--color", "E8470F", "--description", "auto-filed by heal.yml", "--force")
        body = (f"**{wf}** failed.\n\n- run: {url}\n- detected: `{at}`\n\n"
                f"The self-healing loop will retry with backoff ({' · '.join(f'{m}m' for m in BACKOFF_MIN)}) "
                f"and close this issue automatically on recovery.")
        link = gh("issue", "create", "--title", f"🔴 incident: {wf} failing", "--body", body, "--label", "incident")
        inc = dict(workflow=wf, opened_at=at, issue=int(link.rstrip("/").split("/")[-1]), run_id=run_id, retries=0)
        S["incidents"].append(inc)
        print(f"opened incident #{inc['issue']}")
    if str(inc.get("run_id")) != str(run_id):
        inc["run_id"] = run_id  # a new run failed while the incident was already open
    if inc["retries"] >= len(BACKOFF_MIN) or attempt > len(BACKOFF_MIN):
        gh("label", "create", "needs-human", "--color", "121417", "--force")
        gh("issue", "edit", str(inc["issue"]), "--add-label", "needs-human", check=False)
        gh("issue", "comment", str(inc["issue"]), "--body",
           f"Retries exhausted after {inc['retries']} attempts ({url}). Paging a human. 🧑‍🚒")
        save(S)
        return
    wait = BACKOFF_MIN[inc["retries"]]
    inc["retries"] += 1
    save(S)  # persist before sleeping, in case the job is cancelled
    gh("issue", "comment", str(inc["issue"]), "--body",
       f"Attempt {attempt} failed ({url}). Auto-retry #{inc['retries']} in {wait}m.")
    time.sleep(wait * 60)
    gh("run", "rerun", str(run_id), "--failed")
    print(f"retry #{inc['retries']} dispatched for run {run_id}")


def on_pass(S):
    wf = os.environ["WF"]
    run_id, attempt = os.environ.get("RUN_ID"), int(os.environ.get("ATTEMPT") or 1)
    at = os.environ.get("EVENT_AT") or iso(NOW)
    inc = next((i for i in S["incidents"] if i["workflow"] == wf and not i.get("closed_at")), None)
    if not inc:
        return
    inc["closed_at"] = at
    inc["healed_by"] = "retry" if str(inc.get("run_id")) == str(run_id) and attempt > 1 else "fix"
    mins = (parse(at) - parse(inc["opened_at"])).total_seconds() / 60
    how = f"auto-healed by retry #{inc['retries']}" if inc["healed_by"] == "retry" else "recovered after a fix"
    gh("issue", "comment", str(inc["issue"]), "--body", f"✅ **Recovered** — {how}. Time to recovery: **{human(mins)}**.")
    gh("issue", "close", str(inc["issue"]), "--reason", "completed", check=False)
    save(S)
    print(f"closed incident #{inc['issue']} after {human(mins)}")


# ─── Metrics + render ────────────────────────────────────────────────────────
def metrics(S):
    start = NOW - dt.timedelta(days=WINDOW)
    since = max(parse(S.get("since", iso(NOW))), start)
    observed = max((NOW - since).total_seconds(), 1)
    down, closed, incs, days = 0.0, [], [], set()
    for i in S["incidents"]:
        a = parse(i["opened_at"])
        b = parse(i["closed_at"]) if i.get("closed_at") else NOW
        if b < start:
            continue
        incs.append(i)
        down += (b - max(a, start)).total_seconds()
        d = max(a, start).date()
        while d <= b.date():
            days.add(d)
            d += dt.timedelta(days=1)
        if i.get("closed_at"):
            closed.append((b - a).total_seconds() / 60)
    healed = [i for i in incs if i.get("healed_by") == "retry"]
    return dict(
        uptime=max(0.0, 1 - down / observed) * 100,
        mttr=sum(closed) / len(closed) if closed else None,
        count=len(incs),
        healed=(100 * len(healed) / len([i for i in incs if i.get("closed_at")])) if closed else None,
        open=[i for i in S["incidents"] if not i.get("closed_at")],
        days=days, since=since.date(),
    )


def render(t, S):
    M = metrics(S)
    H = 236
    b = []
    status = "DEGRADED" if M["open"] else "OPERATIONAL"
    hot = bool(M["open"])
    b.append(text(0, 20, "FIG. 2 — THIS PROFILE RUNS THE LOOP ON ITSELF", 11, t["muted"], ls=2.5))
    b.append(f'<circle cx="{W - 134}" cy="16" r="4" fill="{t["accent"] if hot else t["ink"]}">'
             '<animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/></circle>')
    b.append(text(W - 4, 20, status, 11, t["accent"] if hot else t["ink"], anchor="end", ls=2.5, weight=700))
    items = [
        (f"README UPTIME · {WINDOW}D", f"{M['uptime']:.2f}%".replace(".00%", "%"), f"tracked since {M['since']:%d %b %Y}"),
        ("MTTR", human(M["mttr"]) if M["mttr"] is not None else "—", "mean time to recovery"),
        (f"INCIDENTS · {WINDOW}D", str(M["count"]), f"{len(M['open'])} open"),
        ("AUTO-HEALED", f"{M['healed']:.0f}%" if M["healed"] is not None else "—", "recovered with no human"),
    ]
    cw = W / len(items)
    y0 = 40
    b += [line(0, y0 + 0.5, W, y0 + 0.5, t["line"]), line(0, y0 + 112.5, W, y0 + 112.5, t["line"])]
    for i, (lbl, val, sub) in enumerate(items):
        x = i * cw + (0 if i == 0 else 20)
        if i:
            b.append(line(i * cw, y0 + 18, i * cw, y0 + 96, t["line"]))
        b.append(text(x, y0 + 32, lbl, 11, t["muted"], ls=2))
        b.append(f'<text x="{x}" y="{y0 + 80}" font-family="{SANS}" font-size="40" font-weight="800" letter-spacing="-1.4" '
                 f'fill="{t["ink"]}">{val}' + anim("opacity", 0, 1, i * 0.12, 0.6) + "</text>")
        b.append(text(x, y0 + 100, sub, 11, t["muted"]))
    # status-page style day bars
    by = y0 + 140
    n, gap = WINDOW, 3
    bw = (W - gap * (n - 1)) / n
    today = NOW.date()
    for k in range(n):
        d = today - dt.timedelta(days=n - 1 - k)
        if d < M["since"]:
            fill, op = t["line"], 1
        elif d in M["days"]:
            fill, op = t["accent"], 1
        else:
            fill, op = t["ink"], 0.78
        b.append(f'<rect x="{k * (bw + gap):.2f}" y="{by}" width="{bw:.2f}" height="30" rx="1.5" fill="{fill}" opacity="{op}">'
                 f'<title>{d.isoformat()}{" · incident" if d in M["days"] else ""}</title>'
                 + anim("opacity", 0, op, 0.4 + k * 0.008, 0.3, ease=False) + "</rect>")
    b.append(text(0, by + 52, f"{WINDOW} DAYS AGO", 10, t["muted"], ls=1.5))
    lx = W / 2 - 190
    for fill, op, lbl, w in ((t["ink"], 0.78, "HEALTHY", 110), (t["accent"], 1, "INCIDENT", 116), (t["line"], 1, "NOT YET TRACKED", 0)):
        b.append(f'<rect x="{lx}" y="{by + 43}" width="10" height="10" rx="1.5" fill="{fill}" opacity="{op}"/>')
        b.append(text(lx + 16, by + 52, lbl, 10, t["muted"], ls=1.5))
        lx += w
    b.append(text(W - 2, by + 52, "TODAY", 10, t["muted"], anchor="end", ls=1.5))
    alt = (f"Self-healing status of this profile: {status.lower()}. Uptime {M['uptime']:.2f}% over {WINDOW} days, "
           f"{M['count']} incidents, MTTR {human(M['mttr']) if M['mttr'] is not None else 'n/a'}.")
    return svg(W, H, "".join(b), alt)


def render_all(S):
    os.makedirs(OUT, exist_ok=True)
    for theme, t in THEMES.items():
        with open(os.path.join(OUT, f"health-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render(t, S))
    print(f"rendered health → {OUT}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "render"
    S = load()
    if cmd == "fail":
        on_fail(S)
    elif cmd == "pass":
        on_pass(S)
    if not os.path.exists(STATE):
        save(S)
    render_all(load())
