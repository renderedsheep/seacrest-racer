# Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
# Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
"""Flag girl: original hand-placed pixel art (palette 2).
Letters: . clear, k black(8), g grey(9), w white(12), s skin(11), S skin shade(13), h hair(15),
1-4 jacket reds (shared with the player car body), 5-7 dark blues (shared with the car glass)."""
from PIL import Image, ImageDraw

KEY = {'.': 0, 'k': 8, 'g': 9, 'w': 12, 's': 11, 'S': 13, 'h': 15,
       '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7}

# head (rows 0-10), hand-placed; the body below is built from per-row extents so shading stays even
HEAD = [
    "..........hhhh..........",   # 0
    "........hhhhhhhh........",
    ".......hhhhhhhhhh.......",
    ".......hhhhssssssh......",
    ".......hhSkkkkkksh......",
    ".......hhsssssssSh......",   # 5
    ".......hhssssSssSh......",
    ".......hhsss33ssSh......",
    "......hhh.SsssssS.......",
    "......hhh..sssS.........",
    "......hhh..sSsS.........",   # 10
]
TORSO = {11: (7, 16), 12: (5, 18), 13: (5, 18), 14: (5, 18), 15: (6, 17), 16: (6, 17), 17: (7, 16), 18: (7, 16),
         19: (8, 15), 20: (8, 15), 21: (8, 15)}
HIPS = {22: (8, 15), 23: (7, 16), 24: (7, 16), 25: (7, 16), 26: (7, 16), 27: (7, 16)}
LEGS = {}
for y in range(28, 34): LEGS[y] = ((7, 11), (13, 16))
for y in range(34, 36): LEGS[y] = ((8, 11), (13, 15))
for y in range(36, 42): LEGS[y] = ((8, 10), (13, 15))
# her right arm (screen left): long red sleeve bent to a hand on the hip
LEFT_ARM = {12: "4:12", 13: "4:12", 14: "3:12", 15: "3:12", 16: "3:11", 17: "3:12", 18: "4:12", 19: "5:12", 20: "6:sS", 21: "7:S"}

def _body_rows():
    rows = [list(r) for r in HEAD] + [list("." * 24) for _ in range(34)]
    for y, (l, r) in TORSO.items():
        for x in range(l, r + 1):
            f = (x - l) / max(1, r - l)
            rows[y][x] = '1' if f < 0.12 else '2' if f < 0.35 else '3' if f < 0.62 else '4' if f < 0.8 else '3' if f < 0.92 else '2'
        if y >= 13: rows[y][12] = '1'                      # zip
    rows[11][10] = rows[11][14] = 'w'; rows[11][11] = rows[11][12] = rows[11][13] = 's'; rows[12][12] = 's'
    rows[12][11] = rows[12][13] = 'w'
    for y, (l, r) in HIPS.items():
        for x in range(l, r + 1):
            rows[y][x] = 'w' if y == 22 else ('5' if x < 10 else '6' if x < 14 else '7')
    rows[22][11] = rows[22][12] = 'g'                      # buckle
    for y, legs in LEGS.items():
        for k, (l, r) in enumerate(legs):
            for x in range(l, r + 1):
                rows[y][x] = ('5' if x == l else '6') if k == 0 else ('7' if x == r else '6')
    for y in (42, 43):
        for x in list(range(7, 12)) + list(range(13, 18)): rows[y][x] = 'k'
    for x in list(range(7, 12)) + list(range(13, 18)): rows[44][x] = 'g'
    for y, spec in LEFT_ARM.items():
        x0, cols = spec.split(":")
        for i, c in enumerate(cols): rows[y][int(x0) + i] = c
    return ["".join(r) for r in rows]

BODY = _body_rows()
SHOULDER = (17, 12)
FEET_Y = len(BODY) - 1

def body_image(pad_top=24, pad_side=26):
    W, H = 24 + 2 * pad_side, len(BODY) + pad_top
    img = Image.new("P", (W, H), 0)
    for y, row in enumerate(BODY):
        for x, ch in enumerate(row):
            if ch != '.':
                img.putpixel((x + pad_side, y + pad_top), KEY[ch])
    return img, pad_side, pad_top

def draw_flag(img, x0, y0, w, h, phase, flip):
    """checkered flag cloth whose free edge ripples; pole side at x0"""
    import math
    for xx in range(w):
        wave = int(round(math.sin(phase + xx * 0.55) * (xx / w) * 2.2))
        for yy in range(h):
            c = 8 if ((xx // 3) + (yy // 3)) % 2 else 12
            X = x0 + (-xx - 1 if flip else xx)
            Y = y0 + yy + wave
            if 0 <= X < img.width and 0 <= Y < img.height:
                img.putpixel((X, Y), c)

def arm(d, sh, el, ha):
    """long red sleeve from shoulder to wrist, then a 2x2 hand"""
    d.line([sh, el], fill=2, width=3)
    d.line([el, ha], fill=3, width=2)
    d.line([(sh[0] + 1, sh[1]), (el[0] + 1, el[1])], fill=4)
    d.rectangle([ha[0] - 1, ha[1] - 1, ha[0], ha[1]], fill=11)
    d.point([(ha[0], ha[1])], fill=13)

def girl(pose):
    img, ox, oy = body_image()
    d = ImageDraw.Draw(img)
    sx, sy = SHOULDER[0] + ox, SHOULDER[1] + oy
    if pose == 0:      # flag high, cloth streaming right
        elbow, hand = (sx + 4, sy - 7), (sx + 5, sy - 16)
        tip = (hand[0] + 3, hand[1] - 9)
        arm(d, (sx, sy), elbow, hand)
        d.line([hand, tip], fill=9)
        draw_flag(img, tip[0], tip[1], 15, 10, 0.0, False)
    elif pose == 1:    # flag high, cloth swung over her head
        elbow, hand = (sx + 2, sy - 8), (sx - 1, sy - 17)
        tip = (hand[0] - 2, hand[1] - 9)
        arm(d, (sx, sy), elbow, hand)
        d.line([hand, tip], fill=9)
        draw_flag(img, tip[0], tip[1], 15, 10, 1.6, True)
    else:              # GO: flag swept down and out
        elbow, hand = (sx + 5, sy + 4), (sx + 11, sy + 9)
        tip = (hand[0] + 9, hand[1] + 3)
        arm(d, (sx, sy), elbow, hand)
        d.line([hand, tip], fill=9)
        draw_flag(img, tip[0] - 1, tip[1] - 1, 14, 10, 0.8, False)
    return img, ox + 12, oy + FEET_Y

if __name__ == "__main__":
    import json, sys
    pal = json.load(open(sys.argv[1]))["pal2"]
    rgb = []
    GL = [0, 52, 87, 116, 144, 172, 206, 255]
    for w in pal:
        rgb += [GL[(w >> 1) & 7], GL[(w >> 5) & 7], GL[(w >> 9) & 7]]
    sheet = Image.new("RGB", (3 * 80 * 5, 80 * 5), (90, 150, 70))
    for p in range(3):
        im, ax, ay = girl(p)
        a = Image.new("L", im.size, 0); a.putdata([255 if v else 0 for v in im.getdata()])
        im.putpalette(rgb + [0] * (768 - len(rgb)))
        rgba = im.convert("RGBA")
        big = rgba.resize((im.width * 5, im.height * 5), Image.NEAREST)
        sheet.paste(big, (p * 80 * 5, 0), a.resize(big.size, Image.NEAREST))
    sheet.save(sys.argv[2])
