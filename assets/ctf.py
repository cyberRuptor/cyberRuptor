#!/usr/bin/env python3
"""
cyberRuptor profile — "Open the Third Eye" CTF.

Three prongs of the trishul, all hidden in the Mahadev artwork (assets/shiva-*.svg):

    I   RECON   something in the artwork's source that isn't drawn
    II  CRYPTO  five syllables
    III STEGO   the earth beneath him

The flag never lives in this repository in plain text. The only server-side copy
is the CTF_FLAG Actions secret. Solvers prove a solve with sha256("<flag>:<login>"),
which is bound to their GitHub login, so a public issue never leaks the answer.

    python3 assets/ctf.py seal      # dev: CTF_FLAG=… → encode the flag into assets/shiva.grid
    python3 assets/ctf.py verify    # CI: ISSUE_TITLE, ISSUE_USER, ISSUE_NUMBER, CTF_FLAG → ctf.json
    python3 assets/ctf.py render    # render assets/live/ctf-{dark,light}.svg from ctf.json
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import sys

from build import THEMES, SANS, W, svg, text, line, anim

HERE = os.path.dirname(os.path.abspath(__file__))
GRID = os.path.join(HERE, "shiva.grid")
OUT = os.path.join(HERE, "live")
STATE = os.path.join(OUT, "ctf.json")
REPO = "cyberRuptor/cyberRuptor"

KEY = "NAMASHIVAYA"  # Panchakshara: na · maḥ · śi · vā · ya
EARTH_ROWS = 2       # bottom rows of the grid carry the payload; 'a' = 0, 'z' = 1

STAGE2 = (
    "THE SECOND PRONG IS YOURS. THE THIRD EYE READS THE EARTH BENEATH HIM: "
    "THE LAST TWO ROWS OF CELLS, UPPER ROW FIRST, LEFT TO RIGHT. TWO SHADES OF ASH - "
    "THE FAINTER IS ZERO, MOST SIGNIFICANT BIT FIRST. THE FIRST BYTE COUNTS THE REST. "
    "XOR WHAT FOLLOWS WITH THE SAME FIVE SYLLABLES. THEN COME BACK WITH PROOF."
)


# ─── Puzzle construction ─────────────────────────────────────────────────────
def vigenere(s, key=KEY):
    out, k = [], 0
    for ch in s:
        if "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + ord(key[k % len(key)]) - 65) % 26 + 65))
            k += 1
        else:
            out.append(ch)
    return "".join(out)


def stage1_comment():
    """Embedded by build.shiva() as an XML comment — invisible when rendered."""
    # encrypt the prefix too, so decrypting the whole decoded string lines the key up correctly
    blob = base64.b64encode(vigenere("II/ " + STAGE2).encode()).decode()
    return f"<!-- प्रथम · {blob} -->"


def seal():
    flag = os.environ.get("CTF_FLAG", "").strip()
    if not flag:
        sys.exit("set CTF_FLAG")
    body = bytes(b ^ ord(KEY[i % len(KEY)]) for i, b in enumerate(flag.encode()))
    payload = bytes([len(body)]) + body
    bits = "".join(f"{b:08b}" for b in payload)
    rows = open(GRID).read().split()
    earth = rows[-EARTH_ROWS:]
    if any(set(r) - {"a", "z"} for r in earth):
        sys.exit("earth rows must be solid ground (only 'a' cells)")
    cap = sum(len(r) for r in earth)
    if len(bits) > cap:
        sys.exit(f"flag too long: {len(bits)} bits > {cap}")
    bits = bits.ljust(cap, "0")
    w = len(earth[0])
    rows[-EARTH_ROWS:] = ["".join("z" if bit == "1" else "a" for bit in bits[i * w:(i + 1) * w])
                          for i in range(EARTH_ROWS)]
    open(GRID, "w").write("\n".join(rows) + "\n")
    print(f"sealed {len(payload)} bytes into the earth ({len(bits)} cells)")


# ─── State ───────────────────────────────────────────────────────────────────
def load():
    try:
        return json.load(open(STATE))
    except Exception:  # noqa: BLE001
        return dict(attempts=0, solvers=[])


def save(S):
    os.makedirs(OUT, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(S, f, indent=2)
        f.write("\n")


def output(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if path:
            with open(path, "a") as f:
                f.write(f"{k}={v}\n")


def verify():
    flag = os.environ.get("CTF_FLAG", "").strip()
    if not flag:
        sys.exit("CTF_FLAG secret missing")
    title = os.environ.get("ISSUE_TITLE", "")
    login = os.environ.get("ISSUE_USER", "").strip()
    S = load()
    m = re.fullmatch(r"\s*ctf:\s*([0-9a-f]{64})\s*", title, re.I)
    if not m or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
        output(result="malformed")
        return
    S["attempts"] = S.get("attempts", 0) + 1
    got = m[1].lower()
    ok = False
    for name in {login, login.lower()}:  # accept the login as typed or lowercased
        ok |= hmac.compare_digest(hashlib.sha256(f"{flag}:{name}".encode()).hexdigest(), got)
    if not ok:
        result = "wrong"
    elif any(s["login"].lower() == login.lower() for s in S["solvers"]):
        result = "repeat"
    else:
        S["solvers"].append(dict(login=login, solved_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                                 issue=int(os.environ.get("ISSUE_NUMBER") or 0)))
        result = "solved"
    save(S)
    output(result=result, rank=len(S["solvers"]))


# ─── Render ──────────────────────────────────────────────────────────────────
PRONGS = [
    ("I", "RECON", "His image says more than it shows.", "Read it — don't look at it."),
    ("II", "CRYPTO", "Five syllables open the second prong.", "पञ्चाक्षर is the key."),
    ("III", "STEGO", "The earth beneath him speaks", "in two shades of ash."),
]


def trishul(t, x, y, lit):
    """Three prongs; each lights up as more people solve."""
    c = lambda i: t["accent"] if i < lit else t["faint"]
    return "".join([
        f'<path d="M{x} {y+86} V{y+4}" stroke="{c(1)}" stroke-width="3" stroke-linecap="round"/>',
        f'<path d="M{x-26} {y+20} C{x-26} {y+54} {x-14} {y+62} {x} {y+62}" fill="none" stroke="{c(0)}" stroke-width="3" stroke-linecap="round"/>',
        f'<path d="M{x+26} {y+20} C{x+26} {y+54} {x+14} {y+62} {x} {y+62}" fill="none" stroke="{c(2)}" stroke-width="3" stroke-linecap="round"/>',
        f'<path d="M{x} {y-2} l-6 12 h12 z" fill="{c(1)}"/>',
        f'<path d="M{x-26} {y+12} l-6 12 h12 z" fill="{c(0)}"/>',
        f'<path d="M{x+26} {y+12} l-6 12 h12 z" fill="{c(2)}"/>',
        f'<rect x="{x-12}" y="{y+70}" width="24" height="6" rx="3" fill="{c(1)}"/>',
    ])


def render(t, S):
    sol = S.get("solvers", [])
    H = 470
    RX = 660
    b = []
    # ── left: the brief
    b.append(text(0, 22, "CTF · ALWAYS OPEN", 11, t["accent"], weight=700, ls=3))
    b.append(f'<text x="0" y="78" font-family="{SANS}" font-size="46" font-weight="800" letter-spacing="-1.5" '
             f'fill="{t["ink"]}">Open the third eye.</text>')
    b.append(text(0, 110, "A flag is hidden in the Mahadev artwork above.", 15, t["muted"], SANS))
    b.append(text(0, 132, "Three prongs stand between you and it. No brute force needed — only sight.", 15, t["muted"], SANS))
    for i, (num, name, h1, h2) in enumerate(PRONGS):
        y = 182 + i * 62
        b.append(f'<g>{text(0, y, num, 12, t["accent"], weight=700, ls=2)}'
                 f'{text(44, y, name, 12, t["ink"], weight=700, ls=3)}'
                 f'{text(160, y, h1, 15, t["ink"], SANS, 500)}'
                 f'{text(160, y + 22, h2, 15, t["muted"], SANS)}'
                 + anim("opacity", 0, 1, 0.2 + i * 0.15, 0.4, ease=False) + "</g>")
        if i < 2:
            b.append(line(0, y + 40, 600, y + 40, t["line"], 1, 'stroke-dasharray="1 4"'))
    # submit box
    sy = 370
    b.append(f'<rect x="0.5" y="{sy+0.5}" width="599" height="86" rx="8" fill="none" stroke="{t["line"]}"/>')
    b.append(text(20, sy + 26, "SUBMIT — PROOF, NOT THE FLAG", 10, t["muted"], ls=2))
    b.append(text(20, sy + 52, "$ echo -n 'flag{…}:<your-login>' | sha256sum", 13, t["ink"]))
    b.append(text(20, sy + 74, "→ open an issue titled  ctf: <hash>", 13, t["accent"]))

    # ── right: the leaderboard
    b.append(line(RX - 30, 0, RX - 30, H, t["line"]))
    b.append(text(RX, 22, "THOSE WHO SAW", 11, t["muted"], ls=3))
    b.append(text(W, 22, f"{len(sol)} SOLVED · {S.get('attempts', 0)} ATTEMPTS", 11,
                  t["accent"] if sol else t["muted"], anchor="end", ls=2, weight=700))
    b.append(trishul(t, W - 40, 56, min(len(sol), 3)))
    if not sol:
        b.append(text(RX, 86, "No one yet.", 26, t["ink"], SANS, 800, ls=-0.5))
        b.append(text(RX, 114, "First blood is still on the table.", 15, t["muted"], SANS))
    for i, s in enumerate(sol[:8]):
        y = 74 + i * 48
        when = s["solved_at"][:10]
        first = i == 0
        g = [text(RX, y, f"{i+1:02d}", 13, t["accent"] if first else t["muted"], weight=700, ls=1),
             text(RX + 44, y, "@" + s["login"], 18, t["ink"], SANS, 700, ls=-0.3),
             text(RX + 44, y + 18, ("FIRST BLOOD · " if first else "") + when, 10,
                  t["accent"] if first else t["muted"], ls=1.5)]
        b.append("<g>" + "".join(g) + anim("opacity", 0, 1, 0.3 + i * 0.1, 0.4, ease=False) + "</g>")
    if len(sol) > 8:
        b.append(text(RX + 44, 74 + 8 * 48, f"+ {len(sol) - 8} more", 13, t["muted"]))
    b.append(text(W, H - 8, "VERIFIED BY ACTIONS · HMAC-SAFE · LOGIN-BOUND", 10, t["muted"], anchor="end", ls=1.5))
    alt = (f"Capture the flag: open the third eye. A flag is hidden in the Mahadev artwork across three stages — "
           f"recon, crypto, stego. {len(sol)} solved so far.")
    return svg(W, H, "".join(b), alt)


def render_all(S=None):
    S = S or load()
    os.makedirs(OUT, exist_ok=True)
    for theme, t in THEMES.items():
        with open(os.path.join(OUT, f"ctf-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render(t, S))
    print(f"rendered ctf → {OUT}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "render"
    if cmd == "seal":
        seal()
    elif cmd == "verify":
        verify()
        render_all()
    else:
        if not os.path.exists(STATE):
            save(load())
        render_all()
