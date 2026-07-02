#!/usr/bin/env python3
"""
Generate representative (synthetic) experiment images for the demo project:
  - western_pdl1.svg  : Western blot of PD-L1 across TNBC lines
  - if_pdl1.svg       : Immunofluorescence field (PD-L1 green / DAPI blue)
  - plate_map.svg     : 96-well plate layout with treatment groups
Written to web/uploads/. Deterministic (seeded).
"""

import math
import random
from pathlib import Path

random.seed(7)
OUT = Path(__file__).resolve().parent.parent / "web" / "uploads"
OUT.mkdir(parents=True, exist_ok=True)


def western():
    lanes = ["MCF-10A", "MDA-MB-231", "MDA-MB-468"]
    xs = [230, 360, 490]
    pdl1 = [0.22, 0.6, 0.95]      # increasing PD-L1
    gapdh = [0.85, 0.88, 0.86]    # even loading
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="640" height="250" font-family="Arial,sans-serif">']
    s.append('<rect width="640" height="250" fill="#ffffff"/>')
    s.append('<defs><filter id="b"><feGaussianBlur stdDeviation="2.4"/></filter></defs>')
    s.append('<text x="24" y="30" font-size="16" font-weight="bold" fill="#15171c">Western blot — PD-L1 expression (TNBC lines)</text>')
    s.append('<rect x="150" y="55" width="470" height="150" fill="#efeee9" stroke="#d8d6cf"/>')
    for lane, x in zip(lanes, xs):
        s.append(f'<text x="{x}" y="72" font-size="12" fill="#333" text-anchor="middle">{lane}</text>')
    # rows
    for label, y, inten in [("PD-L1  (~35 kDa)", 110, pdl1), ("GAPDH  (37 kDa)", 175, gapdh)]:
        s.append(f'<text x="24" y="{y+5}" font-size="12" fill="#333">{label}</text>')
        for x, v in zip(xs, inten):
            w = 66
            op = 0.25 + 0.7 * v
            s.append(f'<rect x="{x-w//2}" y="{y-11}" width="{w}" height="18" rx="7" fill="#1a120c" '
                     f'opacity="{op:.2f}" filter="url(#b)"/>')
    s.append('<text x="616" y="235" font-size="10" fill="#9a968c" text-anchor="end">synthetic demo image</text>')
    s.append('</svg>')
    (OUT / "western_pdl1.svg").write_text("\n".join(s))


def immunofluor():
    W, H = 480, 360
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Arial,sans-serif">']
    s.append(f'<rect width="{W}" height="{H}" fill="#04060a"/>')
    s.append('<defs><filter id="g"><feGaussianBlur stdDeviation="2"/></filter></defs>')
    cells = []
    for _ in range(26):
        x = random.randint(40, W - 40); y = random.randint(50, H - 40); r = random.randint(11, 17)
        cells.append((x, y, r))
    # DAPI nuclei (blue)
    for x, y, r in cells:
        s.append(f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{int(r*0.9)}" fill="#2b6cff" opacity="0.85" filter="url(#g)"/>')
    # PD-L1 membrane (green) on ~60%
    for x, y, r in cells:
        if random.random() < 0.6:
            s.append(f'<circle cx="{x}" cy="{y}" r="{r+6}" fill="none" stroke="#26e07a" '
                     f'stroke-width="3.2" opacity="{0.55+random.random()*0.4:.2f}" filter="url(#g)"/>')
    s.append('<text x="16" y="28" font-size="14" fill="#e8eef5">IF: PD-L1 (green) / DAPI (blue) — MDA-MB-468</text>')
    s.append(f'<rect x="{W-90}" y="{H-30}" width="60" height="5" fill="#ffffff"/>')
    s.append(f'<text x="{W-60}" y="{H-38}" font-size="11" fill="#ffffff" text-anchor="middle">20 µm</text>')
    s.append('</svg>')
    (OUT / "if_pdl1.svg").write_text("\n".join(s))


def plate():
    cols, rows = 12, 8
    r = 13; x0, y0 = 60, 70; dx, dy = 42, 34
    groups = [("Vehicle", "#9aa0aa"), ("Chemotherapy", "#3b82f6"),
              ("Immunotherapy", "#0d9488"), ("Chemo + Immuno", "#8b5cf6")]
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="600" height="380" font-family="Arial,sans-serif">']
    s.append('<rect width="600" height="380" fill="#ffffff"/>')
    s.append('<text x="24" y="34" font-size="16" font-weight="bold" fill="#15171c">96-well plate layout — treatment groups (n=3)</text>')
    for c in range(cols):
        gi = c // 3
        color = groups[gi][1]
        s.append(f'<text x="{x0+c*dx}" y="{y0-14}" font-size="10" fill="#666" text-anchor="middle">{c+1}</text>')
        for rr in range(rows):
            cx, cy = x0 + c * dx, y0 + rr * dy
            s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="0.85" stroke="#ffffff"/>')
    for i, (name, color) in enumerate(groups):
        ly = 70 + i * 22
        s.append(f'<rect x="500" y="{ly-11}" width="14" height="14" rx="3" fill="{color}"/>')
        s.append(f'<text x="520" y="{ly}" font-size="12" fill="#333">{name}</text>')
    s.append('<text x="576" y="366" font-size="10" fill="#9a968c" text-anchor="end">dose series across rows · synthetic demo</text>')
    s.append('</svg>')
    (OUT / "plate_map.svg").write_text("\n".join(s))


if __name__ == "__main__":
    western(); immunofluor(); plate()
    print("✓ demo images ->", OUT)
    for f in sorted(OUT.glob("*.svg")):
        print("  ", f.name)
