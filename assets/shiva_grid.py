#!/usr/bin/env python3
"""
Dev-only: rasterise the Mahadev illustration into contribution-graph cells.

Draws each layer as a vector mask, renders it with rsvg-convert, and measures
how much of every cell it covers. The result is saved to assets/shiva.grid,
which build.py turns into the cell artwork (no extra tools needed in CI).

    python3 assets/shiva_grid.py        # needs rsvg-convert + Pillow
"""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
CW, CH = 1200, 560          # vector canvas
COLS, ROWS = 150, 70        # 8 px cells

# ── Illustration layers (later layers paint over earlier ones) ───────────────
# (code, svg-fragment). Codes: a–d ink level 1–4, A–D accent level 1–4, E third eye
S = 'fill="#000"'


def stroke(w):
    return f'fill="none" stroke="#000" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"'


LAYERS = [
    # Kailash ranges behind everything
    ("a", f'<path {S} d="M0 560 L0 470 L120 410 L220 350 L300 390 L370 310 L450 390 L520 370 L600 300 '
          f'L680 370 L760 390 L840 300 L920 380 L1000 330 L1090 400 L1200 360 L1200 560 Z"/>'),
    # snow caps
    ("b", f'<path {S} d="M370 310 L340 345 L360 340 L372 352 L392 338 L405 350 Z"/>'
          f'<path {S} d="M600 300 L566 340 L585 336 L600 352 L618 336 L636 342 Z"/>'
          f'<path {S} d="M840 300 L808 338 L826 332 L842 346 L860 332 L874 340 Z"/>'
          f'<path {S} d="M220 350 L196 378 L212 374 L224 384 L240 372 Z"/>'
          f'<path {S} d="M1000 330 L976 358 L992 354 L1004 364 L1020 352 Z"/>'),
    # rock seat
    ("b", f'<rect x="360" y="500" width="480" height="44" rx="20" {S}/>'),
    # ── seated figure ──
    ("d", f'<ellipse cx="600" cy="112" rx="36" ry="42" {S}/>'          # jata bun
          f'<circle cx="600" cy="70" r="22" {S}/>'                    # top knot
          f'<ellipse cx="600" cy="176" rx="40" ry="48" {S}/>'         # head
          f'<path {S} d="M556 150 Q548 210 572 236 L628 236 Q652 210 644 150 Z"/>'  # hair falling
          f'<rect x="582" y="210" width="36" height="40" {S}/>'       # neck
          f'<path {S} d="M498 280 Q500 248 540 242 L660 242 Q700 248 702 280 L668 400 L532 400 Z"/>'  # torso
          f'<path {stroke(36)} d="M512 270 Q470 330 476 372 Q480 410 446 438"/>'   # left arm
          f'<path {stroke(36)} d="M688 270 Q730 330 724 372 Q720 410 754 438"/>'   # right arm
          f'<circle cx="438" cy="446" r="20" {S}/><circle cx="762" cy="446" r="20" {S}/>'  # hands (mudra)
          f'<ellipse cx="600" cy="458" rx="214" ry="60" {S}/>'),      # crossed legs
    # inner details (lower intensity inside the silhouette)
    ("b", f'<path {stroke(7)} d="M572 246 Q600 330 628 246"/>'             # rudraksha mala
          f'<path {stroke(5)} d="M578 186 Q585 191 592 186"/><path {stroke(5)} d="M608 186 Q615 191 622 186"/>'  # closed eyes
          f'<path {stroke(4)} d="M580 160 H620"/><path {stroke(4)} d="M582 168 H618"/>'   # tripundra
          f'<path {stroke(7)} d="M540 400 Q600 420 660 400"/>'             # waist sash
          f'<path {stroke(6)} d="M470 470 Q600 430 730 470"/>'),           # leg fold
    # Vasuki around the neck, hood rising at the right shoulder
    ("B", f'<path {stroke(10)} d="M570 236 Q600 262 632 236 Q650 222 652 200"/>'
          f'<ellipse cx="654" cy="190" rx="13" ry="16" {S}/>'),
    # Ganga flowing from the jata
    ("A", f'<path {stroke(7)} d="M618 62 Q660 30 700 52 Q740 74 780 44 Q810 24 840 40"/>'),
    # crescent moon in the hair
    ("D", f'<path {S} fill-rule="evenodd" d="M532 98 a26 26 0 1 0 52 0 a26 26 0 1 0 -52 0 Z '
          f'M544 88 a22 22 0 1 0 44 0 a22 22 0 1 0 -44 0 Z"/>'),
    # trishul shaft + damru + head
    ("c", f'<path {stroke(9)} d="M900 120 V544"/>'),
    ("C", f'<path {S} d="M872 176 L928 176 L906 196 L928 216 L872 216 L894 196 Z"/>'   # damru
          f'<path {stroke(4)} d="M928 196 Q950 210 944 236"/>'),                       # damru cord
    ("D", f'<path {S} d="M900 22 L914 64 L906 64 L906 128 L894 128 L894 64 L886 64 Z"/>'  # centre spear
          f'<path {stroke(11)} d="M900 128 Q858 124 856 64"/><path {stroke(11)} d="M900 128 Q942 124 944 64"/>'
          f'<path {S} d="M856 40 L866 72 L846 72 Z"/><path {S} d="M944 40 L954 72 L934 72 Z"/>'
          f'<rect x="882" y="124" width="36" height="12" rx="4" {S}/>'),
    # third eye
    ("E", f'<ellipse cx="600" cy="149" rx="5" ry="8" {S}/>'),
]


def coverage(fragment):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{CW}" height="{CH}" viewBox="0 0 {CW} {CH}">'
           f'<rect width="100%" height="100%" fill="#fff"/>{fragment}</svg>')
    with tempfile.TemporaryDirectory() as d:
        src, png = Path(d, "l.svg"), Path(d, "l.png")
        src.write_text(svg)
        subprocess.run(["rsvg-convert", "-w", str(CW), "-h", str(CH), "-o", str(png), str(src)], check=True)
        img = Image.open(png).convert("L").resize((COLS, ROWS), Image.BOX)
    return [[1 - img.getpixel((c, r)) / 255 for c in range(COLS)] for r in range(ROWS)]


def main():
    grid = [["." for _ in range(COLS)] for _ in range(ROWS)]
    for code, frag in LAYERS:
        cov = coverage(frag)
        level = "abcdABCDE".index(code)
        for r in range(ROWS):
            for c in range(COLS):
                v = cov[r][c]
                if code == "E":
                    if v > 0.25:
                        grid[r][c] = "E"
                elif v >= 0.5:
                    grid[r][c] = code
                elif v >= 0.18 and grid[r][c] == "." and code not in "aA":
                    # soft anti-aliased edge: one level lower
                    grid[r][c] = chr(ord(code) - 1)
    out = HERE / "shiva.grid"
    out.write_text("\n".join("".join(row) for row in grid) + "\n")
    print(f"wrote {out} ({sum(ch != '.' for row in grid for ch in row)} lit cells)")
    print("\n".join("".join(row) for row in grid))


if __name__ == "__main__":
    _ = "abcdABCDE"  # code alphabet
    main()
