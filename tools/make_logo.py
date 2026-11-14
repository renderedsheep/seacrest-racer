#!/usr/bin/env python3
# Seacrest Racer - Copyright 2026 Fernand Gouveia / PlayableFX.com
# Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
"""Draws the Seacrest Racer title logo and the credit strip as indexed PNGs (tools/art/).
Only needs re-running to change the logo; ./build.sh uses the PNGs it wrote.

Typefaces (SIL Open Font License 1.1, rendered to pixels here, not shipped):
  Racing Sans One (Hector Gatti), Russo One (Jovanny Lemonad)
Get them with:  npm i @fontsource/racing-sans-one @fontsource/russo-one
Usage: python3 tools/make_logo.py <dir containing the .woff files>"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(__file__))
import font5x7

FD = sys.argv[1] if len(sys.argv) > 1 else "fonts/"
OUT = os.path.join(os.path.dirname(__file__), "art")
GL = [0, 52, 87, 116, 144, 172, 206, 255]
def g(r, gg, b): return (GL[r], GL[gg], GL[b])
# logo palette (loaded into palette 3 while the title is up), Genesis 3-bit RGB
LOGO_PAL = [None, (2, 0, 3), (7, 7, 7), (7, 7, 2), (7, 5, 1), (7, 3, 1), (6, 1, 3), (4, 0, 4), (0, 0, 1), (6, 0, 0)]
S = 4

def text_mask(txt, font, size, track=0, shear=0.0, wscale=1.0):
    f = ImageFont.truetype(os.path.join(FD, font), size * S)
    w = sum(f.getbbox(c)[2] for c in txt) + track * S * len(txt)
    m = Image.new("L", (w + size * S, int(size * S * 1.4)), 0)
    d = ImageDraw.Draw(m); x = 0
    for c in txt:
        d.text((x, 0), c, font=f, fill=255); x += f.getbbox(c)[2] + track * S
    m = m.crop(m.getbbox())
    if wscale != 1.0: m = m.resize((int(m.width * wscale), m.height), Image.LANCZOS)
    if shear:
        W, H = m.size; extra = int(H * shear)
        m = m.transform((W + extra, H), Image.AFFINE, (1, -shear, extra, 0, 1, 0), Image.BICUBIC)
    m = m.resize((max(1, m.width // S), max(1, m.height // S)), Image.BOX)
    return m.point(lambda v: 255 if v >= 110 else 0)

dilate = lambda m, r=1: m.filter(ImageFilter.MaxFilter(2 * r + 1))
def paste(img, m, xy, col): img.paste(Image.new("RGBA", m.size, g(*col) + (255,)), xy, m)
def grad(img, m, xy, stops):
    W, H = m.size; layer = Image.new("RGBA", (W, H))
    for y in range(H):
        t = y / max(1, H - 1); c = stops[0][1]
        for f, col in stops:
            if t >= f: c = col
        ImageDraw.Draw(layer).line([(0, y), (W, y)], fill=g(*c) + (255,))
    img.paste(layer, xy, m)

def logo():
    W, H = 256, 64
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy, R = 206, 24, 22                                  # striped sun behind the lettering
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=g(7, 5, 1))
    for k, y in enumerate(range(cy + 2, cy + R, 5)):
        d.rectangle([cx - R, y, cx + R, y + 1 + k // 2], fill=(0, 0, 0, 0))
    m = text_mask("SEACREST", "racing-sans-one-latin-400-normal.woff", 34, shear=0.12)
    ox, oy = (W - m.width) // 2, 2
    sh = dilate(m, 1)
    paste(img, sh, (ox + 2, oy + 2), (2, 0, 3))
    paste(img, sh, (ox - 1, oy - 1), (7, 7, 7))
    grad(img, m, (ox, oy), [(0, (7, 7, 2)), (0.3, (7, 5, 1)), (0.55, (7, 3, 1)), (0.75, (6, 1, 3)), (0.9, (4, 0, 4))])
    for y in (oy + int(m.height * 0.62), oy + int(m.height * 0.8)):   # stripe cuts through the letters
        for x in range(ox, ox + m.width):
            if m.getpixel((x - ox, y - oy)): img.putpixel((x, y), g(2, 0, 3) + (255,))
    # red RACER tag with speed lines
    r = text_mask("RACER", "russo-one-latin-400-normal.woff", 14, track=4, shear=0.2, wscale=1.1)
    bx0, by0 = ox + m.width - r.width - 30, oy + m.height + 5
    d.polygon([(bx0 - 10, by0 + r.height + 5), (bx0 - 2, by0 - 3), (bx0 + r.width + 16, by0 - 3), (bx0 + r.width + 8, by0 + r.height + 5)], fill=g(0, 0, 1))
    d.polygon([(bx0 - 8, by0 + r.height + 4), (bx0 - 1, by0 - 2), (bx0 + r.width + 14, by0 - 2), (bx0 + r.width + 7, by0 + r.height + 4)], fill=g(6, 0, 0))
    paste(img, r, (bx0 + 3, by0 + 1), (7, 7, 7))
    for k, (x0, x1) in enumerate([(-58, -14), (-70, -14), (-50, -14)]):
        y = by0 + 1 + k * 5
        d.line([(bx0 + x0, y), (bx0 + x1 - k * 2, y)], fill=g(7, 7, 7) if k != 1 else g(6, 0, 0), width=2)
    return img.crop(img.getbbox())

def credit(*lines):
    """credit lines in the game's own 5x7 font, white with a navy shadow; '@' draws a (c) sign.
    Each line is 8 pixels tall, so every line costs exactly one row of tiles."""
    glyphs = dict(font5x7.GLYPHS)
    glyphs['@'] = [" ### ", "#   #", "# ###", "# #  ", "# ###", "#   #", " ### "]   # copyright sign
    W = max(len(t) for t in lines) * 6 + 2
    img = Image.new("RGBA", (W, 8 * len(lines)), (0, 0, 0, 0))
    for colour, dx, dy in ((g(0, 0, 1), 1, 1), (g(7, 7, 7), 0, 0)):
        for ln, text in enumerate(lines):
            for i, ch in enumerate(text):
                for y, row in enumerate(glyphs.get(ch) or []):
                    for x, c in enumerate(row):
                        if c == '#':
                            img.putpixel((i * 6 + x + dx, ln * 8 + y + dy), colour + (255,))
    return img

def to_indexed(img):
    lut = {g(*c): i for i, c in enumerate(LOGO_PAL) if c}
    out = Image.new("P", img.size, 0)
    for y in range(img.height):
        for x in range(img.width):
            p = img.getpixel((x, y))
            if p[3]:
                out.putpixel((x, y), lut[p[:3]])
    flat = [0, 0, 0]
    for c in LOGO_PAL[1:]: flat += list(g(*c))
    out.putpalette(flat + [0] * (768 - len(flat)))
    return out

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    lg = to_indexed(logo()); lg.save(os.path.join(OUT, "logo.png"), transparency=0)
    cr = to_indexed(credit("@ 2026 FERNAND GOUVEIA", "PLAYABLEFX.COM")); cr.save(os.path.join(OUT, "credit.png"), transparency=0)
    print("logo", lg.size, "credit", cr.size)
