#!/usr/bin/env python3
"""
cyberRuptor profile — supply-chain provenance for the profile itself.

Every SVG on this profile is attested by GitHub Artifact Attestations (Sigstore,
SLSA build provenance) in .github/workflows/provenance.yml. Anyone can verify:

    curl -sLO https://raw.githubusercontent.com/cyberRuptor/cyberRuptor/main/assets/shiva-dark.svg
    gh attestation verify shiva-dark.svg -R cyberRuptor/cyberRuptor

    python3 assets/provenance.py checksums <out>   # manifest of all SVGs; sets changed=true|false
    python3 assets/provenance.py render            # ATTEST_URL, COMMIT_SHA → badge + manifest
"""
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from build import THEMES, SANS, W, svg, text, line

HERE = Path(__file__).parent
ROOT = HERE.parent
LIVE = HERE / "live"
MANIFEST = LIVE / "SHA256SUMS"
STATE = LIVE / "provenance.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "cyberRuptor/cyberRuptor")


def subjects():
    # The badge itself is excluded: it's rendered *after* attesting, so it can't attest itself.
    return sorted(p for p in HERE.rglob("*.svg") if not p.name.startswith("provenance-"))


def checksums(out):
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}" for p in subjects()]
    body = "\n".join(lines) + "\n"
    Path(out).write_text(body)
    changed = not MANIFEST.exists() or MANIFEST.read_text() != body
    gho = os.environ.get("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\ncount={len(lines)}\n")
    print(f"{len(lines)} subjects · changed={changed}")


def render(t, P):
    H = 112
    b = [f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="none" stroke="{t["line"]}"/>',
         line(24, 0.5, 64, 0.5, t["accent"], 2)]
    # shield + check
    b.append(f'<path d="M44 26 L62 32 V46 C62 58 54 66 44 70 C34 66 26 58 26 46 V32 Z" fill="none" '
             f'stroke="{t["accent"]}" stroke-width="2" stroke-linejoin="round"/>'
             f'<path d="M36 47 L42 53 L53 40" fill="none" stroke="{t["accent"]}" stroke-width="2.4" '
             f'stroke-linecap="round" stroke-linejoin="round"/>')
    b.append(f'<text x="84" y="44" font-family="{SANS}" font-size="20" font-weight="800" letter-spacing="-0.4" '
             f'fill="{t["ink"]}">{"Signing in progress…" if P.get("pending") else "Every graphic on this page is signed."}</text>')
    b.append(text(84, 66, f"{P['count']} SVG ASSETS · SIGSTORE · SLSA BUILD PROVENANCE · "
                          f"BUILT BY provenance.yml @ {'—' if P.get('pending') else P['commit'][:7]}", 10, t["muted"], ls=1.5))
    b.append(line(24, 80, W - 24, 80, t["line"]))
    b.append(text(24, 99, f"$ gh attestation verify <asset.svg> -R {REPO}", 12, t["ink"]))
    stamp = ("FIRST ATTESTATION PENDING" if P.get("pending") else
             "ATTESTED " + P["attested_at"].replace("T", " ").replace("Z", " UTC"))
    b.append(text(W - 24, 99, stamp, 10, t["muted"], anchor="end", ls=1.5))
    alt = ("Asset signing is in progress." if P.get("pending") else
           f"Every graphic on this profile is signed: {P['count']} SVG assets with Sigstore SLSA build provenance. "
           "Verify with gh attestation verify.")
    return svg(W, H, "".join(b), alt)


def render_all():
    try:
        P = json.loads(STATE.read_text())
    except Exception:  # noqa: BLE001  (before the first CI attestation — never claim a signature we don't have)
        P = dict(count=len(subjects()), commit="pending", attested_at="pending", pending=True)
    for theme, t in THEMES.items():
        (LIVE / f"provenance-{theme}.svg").write_text(render(t, P), encoding="utf-8")
    print("rendered provenance badge")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "render"
    if cmd == "checksums":
        checksums(sys.argv[2])
    else:
        src = os.environ.get("SUMS")
        if src:  # after a successful attestation: record it
            shutil.copy(src, MANIFEST)
            P = dict(count=sum(1 for _ in open(src)), commit=os.environ.get("COMMIT_SHA", "local"),
                     url=os.environ.get("ATTEST_URL", ""),
                     attested_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"))
            STATE.write_text(json.dumps(P, indent=2) + "\n")
        render_all()
