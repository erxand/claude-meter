#!/usr/bin/env python3
"""Generate icon.icns — an original "spark" mark inspired by Claude's sunburst,
recolored so it's its own thing (violet→indigo tile, cream→amber burst).

Requires Pillow (dev-only) and macOS `iconutil`. The resulting icon.icns is
committed, so a normal build doesn't need to re-run this.

    python make_icon.py
"""

import math
import os
import shutil
import subprocess

from PIL import Image, ImageDraw

SS = 2                 # supersample factor for anti-aliasing
S = 1024               # final master size
N = S * SS             # drawing canvas

# Palette — deliberately not Claude's terracotta-on-cream.
BG_TOP = (109, 40, 217)     # violet-600  #6d28d9
BG_BOT = (30, 27, 75)       # indigo-950  #1e1b4b
BURST_TOP = (255, 247, 237)  # cream       #fff7ed
BURST_BOT = (251, 191, 36)   # amber-400   #fbbf24

MARGIN = 0.085 * N                       # native "floating rounded square" inset
CONTENT = N - 2 * MARGIN
CORNER = 0.2235 * CONTENT                 # macOS Big Sur corner radius ratio
CX = CY = N / 2
PETALS = 12


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _vgradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=_lerp(top, bottom, y / (h - 1)))
    return img


def render_master():
    # Rounded-rect tile mask
    tile = Image.new("L", (N, N), 0)
    ImageDraw.Draw(tile).rounded_rectangle(
        [MARGIN, MARGIN, N - MARGIN, N - MARGIN], radius=CORNER, fill=255
    )

    # Burst silhouette: 12 tapered petals converging at a small hub
    burst = Image.new("L", (N, N), 0)
    bd = ImageDraw.Draw(burst)
    outer = 0.40 * CONTENT
    rmid = 0.205 * CONTENT
    hw = 0.052 * CONTENT
    for k in range(PETALS):
        a = math.radians(k * (360 / PETALS) - 90)
        dx, dy = math.cos(a), math.sin(a)
        px, py = -math.sin(a), math.cos(a)
        tip = (CX + outer * dx, CY + outer * dy)
        inner = (CX, CY)
        lm = (CX + rmid * dx + hw * px, CY + rmid * dy + hw * py)
        rm = (CX + rmid * dx - hw * px, CY + rmid * dy - hw * py)
        bd.polygon([inner, lm, tip, rm], fill=255)
    hub = 0.085 * CONTENT
    bd.ellipse([CX - hub, CY - hub, CX + hub, CY + hub], fill=255)

    # Compose: gradient tile, then gradient burst through its mask
    canvas = _vgradient(N, N, BG_TOP, BG_BOT)
    canvas.paste(_vgradient(N, N, BURST_TOP, BURST_BOT), (0, 0), burst)

    out = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    out.paste(canvas, (0, 0), tile)
    return out.resize((S, S), Image.LANCZOS)


def build_icns(master):
    iconset = "icon.iconset"
    if os.path.isdir(iconset):
        shutil.rmtree(iconset)
    os.makedirs(iconset)
    specs = [
        (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
    ]
    for size, name in specs:
        img = master if size == S else master.resize((size, size), Image.LANCZOS)
        img.save(os.path.join(iconset, name))
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", "icon.icns"], check=True)
    master.resize((512, 512), Image.LANCZOS).save("icon_preview.png")
    shutil.rmtree(iconset)
    print("wrote icon.icns and icon_preview.png")


if __name__ == "__main__":
    build_icns(render_master())
