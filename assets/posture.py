#!/usr/bin/env python3
"""
cyberRuptor profile — security posture.

Scans my own public repositories with real tools and renders the result as an
on-brand SVG panel (assets/live/posture-{dark,light}.svg):

    trivy      vulnerabilities (CVE by severity) · IaC/Helm misconfig · secrets in tree
    gitleaks   secrets anywhere in git history
    scorecard  OpenSSF Scorecard (0–10) supply-chain hygiene

Runs daily via .github/workflows/posture.yml. Any tool that is missing or fails
falls back to the last known value (assets/live/posture.json), so a flaky run
never blanks the panel. Only *counts* are stored or printed — never findings.

    GITHUB_AUTH_TOKEN=... python3 assets/posture.py
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile

from build import THEMES, SANS, W, svg, text, line, anim

USER = os.environ.get("PROFILE_USER", "cyberRuptor")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "live")
STATE = os.path.join(OUT, "posture.json")

# Repos to audit, in display order. kind: OWN = authored here, FORK = maintained fork.
TARGETS = [
    ("redis-sentinel-helm-chart", "OWN"),
    ("mongodb-helm-chart", "OWN"),
    ("sharepoint-mcp", "FORK"),
    ("ocft", "FORK"),
    ("cyberRuptor", "OWN"),  # this profile — its own pipeline is in scope too
]

NOW = dt.datetime.now(dt.timezone.utc)
SEV = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


# ─── Tools ───────────────────────────────────────────────────────────────────
def run(cmd, **kw):
    """Run quietly; never echo output (it may contain secret material)."""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=900, **kw)


def version(tool):
    if not shutil.which(tool):
        return None
    for args in (["--version"], ["version"]):
        try:
            p = run([tool, *args])
        except Exception:  # noqa: BLE001
            continue
        out = (p.stdout + p.stderr).strip()
        for tok in out.replace("\n", " ").split():
            tok = tok.strip(",").lstrip("v")
            if tok[:1].isdigit() and "." in tok:
                return tok
    return "?"


def trivy(path):
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        p = run(["trivy", "fs", "--quiet", "--scanners", "vuln,secret,misconfig",
                 "--format", "json", "--output", f.name, path])
        if p.returncode:
            raise RuntimeError(p.stderr.strip().splitlines()[-1:] or "trivy failed")
        data = json.load(open(f.name))
    vulns = dict.fromkeys(SEV, 0)
    seen = set()
    mis = dict(total=0, high=0)
    secrets = 0
    for r in data.get("Results") or []:
        for v in r.get("Vulnerabilities") or []:
            key = (v.get("VulnerabilityID"), v.get("PkgName"), v.get("InstalledVersion"))
            if key in seen:
                continue
            seen.add(key)
            if v.get("Severity") in vulns:
                vulns[v["Severity"]] += 1
        for m in r.get("Misconfigurations") or []:
            if m.get("Status", "FAIL") == "FAIL":
                mis["total"] += 1
                if m.get("Severity") in ("HIGH", "CRITICAL"):
                    mis["high"] += 1
        secrets += len(r.get("Secrets") or [])
    return dict(vulns=vulns, misconfig=mis, tree_secrets=secrets)


def gitleaks(path):
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        p = run(["gitleaks", "git", path, "--no-banner", "--redact", "--exit-code", "0",
                 "--report-format", "json", "--report-path", f.name, "--log-level", "error"])
        if p.returncode:
            raise RuntimeError("gitleaks failed")
        return len(json.load(open(f.name)) or [])


def scorecard(repo):
    if not (os.environ.get("GITHUB_AUTH_TOKEN") or os.environ.get("GITHUB_TOKEN")):
        raise RuntimeError("no token")
    env = dict(os.environ)
    env.setdefault("GITHUB_AUTH_TOKEN", env.get("GITHUB_TOKEN", ""))
    p = run(["scorecard", f"--repo=github.com/{USER}/{repo}", "--format=json", "--show-details=false"], env=env)
    if p.returncode:
        raise RuntimeError("scorecard failed")
    d = json.loads(p.stdout)
    checks = [c for c in d.get("checks", []) if isinstance(c.get("score"), (int, float)) and c["score"] >= 0]
    weakest = min(checks, key=lambda c: c["score"]) if checks else None
    return dict(score=round(float(d["score"]), 1),
                weakest=f"{weakest['name']} {weakest['score']}" if weakest else None)


def clone(repo, dest):
    p = run(["git", "clone", "--quiet", "--no-tags", f"https://github.com/{USER}/{repo}.git", dest])
    if p.returncode:
        raise RuntimeError("clone failed")


# ─── Scan ────────────────────────────────────────────────────────────────────
def scan(prev):
    tools = {k: version(k) for k in ("trivy", "gitleaks", "scorecard")}
    print("tools:", ", ".join(f"{k} {v or 'missing'}" for k, v in tools.items()))
    rows = []
    fresh = 0
    for repo, kind in TARGETS:
        old = next((r for r in prev.get("repos", []) if r["repo"] == repo), {})
        row = dict(repo=repo, kind=kind)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, repo)
            try:
                clone(repo, path)
                cloned = True
            except Exception as e:  # noqa: BLE001
                print(f"  ! {repo}: {e}")
                cloned = False
            steps = [("trivy", lambda: trivy(path), cloned),
                     ("gitleaks", lambda: gitleaks(path), cloned),
                     ("scorecard", lambda: scorecard(repo), True)]
            for tool, fn, ok in steps:
                if tools[tool] and ok:
                    try:
                        row[tool] = fn()
                        fresh += 1
                        continue
                    except Exception as e:  # noqa: BLE001
                        print(f"  ! {repo} · {tool}: {e}")
                row[tool] = old.get(tool)  # last known value
        print(f"  ✓ {repo}")
        rows.append(row)
    return dict(scanned_at=NOW.strftime("%Y-%m-%dT%H:%MZ"), tools=tools, repos=rows), fresh


# ─── Render ──────────────────────────────────────────────────────────────────
def verdict(r):
    t, g = r.get("trivy") or {}, r.get("gitleaks")
    v = t.get("vulns") or {}
    if (g or 0) + t.get("tree_secrets", 0) or v.get("CRITICAL"):
        return "EXPOSED"
    if v.get("HIGH") or (t.get("misconfig") or {}).get("high"):
        return "WATCH"
    if not t and g is None:
        return "UNKNOWN"
    return "HARDENED"


def num(v):
    return "—" if v is None else str(v)


def render(t, S):
    rows = S["repos"]
    R0, ROW = 214, 74
    H = R0 + len(rows) * ROW + 58
    b = []

    # summary strip
    tri = [r["trivy"] for r in rows if r.get("trivy")]
    crit = sum(x["vulns"]["CRITICAL"] for x in tri)
    high = sum(x["vulns"]["HIGH"] for x in tri)
    mis = sum(x["misconfig"]["total"] for x in tri)
    secrets = sum(x["tree_secrets"] for x in tri) + sum(r["gitleaks"] or 0 for r in rows if r.get("gitleaks") is not None)
    scores = [r["scorecard"]["score"] for r in rows if r.get("scorecard")]
    avg = f"{sum(scores)/len(scores):.1f}" if scores else "—"
    verdicts = [verdict(r) for r in rows]
    overall = next((v for v in ("EXPOSED", "WATCH") if v in verdicts), "HARDENED")
    items = [
        ("REPOS AUDITED", str(len(rows)), "daily, full history"),
        ("CRITICAL · HIGH", f"{crit}·{high}" if tri else "—", "open CVEs"),
        ("MISCONFIGS", str(mis) if tri else "—", "helm · docker · iac"),
        ("SECRETS", str(secrets) if tri or any(r.get("gitleaks") is not None for r in rows) else "—", "tree + git history"),
        ("SCORECARD", avg, "openssf, avg / 10"),
    ]
    cw = (W - 230) / len(items)
    b += [line(0, 0.5, W, 0.5, t["line"]), line(0, 132.5, W, 132.5, t["line"])]
    for i, (lbl, val, sub) in enumerate(items):
        x = i * cw + (0 if i == 0 else 20)
        if i:
            b.append(line(i * cw, 18, i * cw, 114, t["line"]))
        hot = (lbl == "SECRETS" and val not in ("0", "—")) or (lbl == "CRITICAL · HIGH" and val not in ("0·0", "—"))
        b.append(text(x, 34, lbl, 11, t["muted"], ls=2))
        b.append(f'<text x="{x}" y="86" font-family="{SANS}" font-size="44" font-weight="800" letter-spacing="-1.5" '
                 f'fill="{t["accent"] if hot else t["ink"]}">{val}'
                 + anim("opacity", 0, 1, i * 0.12, 0.6) + anim("y", 98, 86, i * 0.12, 0.6) + "</text>")
        b.append(text(x, 112, sub, 11, t["muted"]))
    # overall verdict stamp
    vx = W - 210
    b.append(line(vx - 20, 18, vx - 20, 114, t["line"]))
    col = t["accent"] if overall != "HARDENED" else t["ink"]
    b.append(f'<rect x="{vx+0.5}" y="30.5" width="206" height="72" rx="8" fill="none" stroke="{col}" stroke-width="1.5" '
             f'stroke-dasharray="{"0" if overall == "HARDENED" else "5 3"}"/>')
    b.append(text(vx + 103, 56, "POSTURE", 10, t["muted"], anchor="middle", ls=3))
    b.append(text(vx + 103, 88, overall, 24, col, SANS, 800, anchor="middle", ls=2))

    # table head
    C = dict(repo=0, score=330, vuln=640, mis=860, sec=990, v=W - 2)
    hy = 176
    for k, lbl in (("repo", "REPOSITORY"), ("score", "OPENSSF SCORECARD"), ("vuln", "CVE  C · H · M · L"),
                   ("mis", "MISCONFIG"), ("sec", "SECRETS")):
        b.append(text(C[k], hy, lbl, 10, t["muted"], ls=2))
    b.append(text(C["v"], hy, "VERDICT", 10, t["muted"], anchor="end", ls=2))
    b.append(line(0, hy + 16, W, hy + 16, t["line"]))

    for i, r in enumerate(rows):
        y = R0 + i * ROW
        delay = 0.3 + i * 0.12
        tr, sc, gl = r.get("trivy"), r.get("scorecard"), r.get("gitleaks")
        g = [text(C["repo"], y + 8, r["repo"], 18, t["ink"], SANS, 700, ls=-0.3),
             text(C["repo"], y + 30, f"{r['kind']} · github.com/{USER}", 10, t["muted"], ls=1.5)]
        # scorecard bar
        bw = 200
        if sc:
            s = sc["score"]
            g.append(f'<rect x="{C["score"]}" y="{y-2}" width="{bw}" height="6" rx="3" fill="{t["line"]}"/>')
            g.append(f'<rect x="{C["score"]}" y="{y-2}" width="{bw*s/10:.1f}" height="6" rx="3" '
                     f'fill="{t["accent"] if s < 5 else t["ink"]}">' + anim("width", 0, f"{bw*s/10:.1f}", delay, 0.8) + "</rect>")
            g.append(text(C["score"] + bw + 14, y + 6, f"{s:.1f}", 18, t["ink"], SANS, 800))
            if sc.get("weakest"):
                g.append(text(C["score"], y + 30, f"WEAKEST · {sc['weakest']}".upper(), 10, t["muted"], ls=1.2))
        else:
            g.append(text(C["score"], y + 8, "— pending", 13, t["muted"]))
        # CVEs
        if tr:
            v = tr["vulns"]
            x = C["vuln"]
            for k, sev in enumerate(SEV):
                n = v[sev]
                g.append(text(x + k * 46, y + 8, str(n), 18, t["accent"] if n and k < 2 else (t["ink"] if n else t["faint"]),
                              SANS, 800))
            g.append(text(C["vuln"], y + 30, f"{sum(v.values())} TOTAL", 10, t["muted"], ls=1.5))
            m = tr["misconfig"]
            g.append(text(C["mis"], y + 8, str(m["total"]), 18, t["accent"] if m["high"] else t["ink"], SANS, 800))
            g.append(text(C["mis"], y + 30, f"{m['high']} HIGH+", 10, t["muted"], ls=1.5))
        else:
            g.append(text(C["vuln"], y + 8, "—", 18, t["faint"], SANS, 800))
            g.append(text(C["mis"], y + 8, "—", 18, t["faint"], SANS, 800))
        tree = tr["tree_secrets"] if tr else None
        total = None if tree is None and gl is None else (tree or 0) + (gl or 0)
        g.append(text(C["sec"], y + 8, num(total), 18, t["accent"] if total else t["ink"], SANS, 800))
        g.append(text(C["sec"], y + 30, f"TREE {num(tree)} · HIST {num(gl)}", 10, t["muted"], ls=1.5))
        # verdict pill
        vd = verdict(r)
        hot = vd in ("EXPOSED", "WATCH")
        pw = 104
        g.append(f'<rect x="{C["v"]-pw+0.5}" y="{y-12.5}" width="{pw-1}" height="26" rx="13" '
                 f'fill="{t["accent"] if vd == "EXPOSED" else "none"}" stroke="{t["accent"] if hot else t["faint"]}"/>')
        g.append(text(C["v"] - pw / 2, y + 5, vd, 10, t["page"] if vd == "EXPOSED" else (t["accent"] if hot else t["ink"]),
                      weight=700, anchor="middle", ls=2))
        if i < len(rows) - 1:
            g.append(line(0, y + ROW - 26, W, y + ROW - 26, t["line"], 1, 'stroke-dasharray="1 4"'))
        b.append("<g>" + "".join(g) + anim("opacity", 0, 1, delay, 0.4, ease=False) + "</g>")

    # footer
    fy = H - 14
    b.append(line(0, fy - 24, W, fy - 24, t["line"]))
    tv = S.get("tools") or {}
    b.append(text(0, fy, "  ·  ".join(f"{k.upper()} {v}" for k, v in tv.items() if v) or "SCANNERS OFFLINE",
                  10, t["muted"], ls=1.5))
    stamp = "SCANNED " + S["scanned_at"].replace("T", " ").replace("Z", " UTC")
    b.append(f'<circle cx="{W - len(stamp)*7.5 - 14}" cy="{fy-4}" r="3.5" fill="{t["accent"]}">'
             '<animate attributeName="opacity" values="1;.2;1" dur="1.6s" repeatCount="indefinite"/></circle>')
    b.append(text(W, fy, stamp, 10, t["muted"], anchor="end", ls=1.5))

    alt = (f"Security posture: {overall}. {len(rows)} repos audited; {crit} critical and {high} high CVEs; "
           f"{mis} misconfigurations; {secrets} secrets; average OpenSSF Scorecard {avg}/10.")
    return svg(W, H, "".join(b), alt)


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        prev = json.load(open(STATE))
    except Exception:  # noqa: BLE001
        prev = {}
    if "--render-only" in sys.argv:
        if not prev:
            sys.exit("no posture.json to render")
        S = prev
    else:
        S, fresh = scan(prev)
        if not fresh:
            sys.exit("no scanner produced data — keeping existing posture graphics")
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(S, f, indent=2)
            f.write("\n")
    for theme, t in THEMES.items():
        with open(os.path.join(OUT, f"posture-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render(t, S))
    print(f"rendered posture → {OUT}")


if __name__ == "__main__":
    main()
