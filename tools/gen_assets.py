#!/usr/bin/env python3
# Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
# Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
"""Asset generator for SEACREST RACER (Genesis). Produces tiles, maps, sprite frames,
palettes and model tables. All art is original and generated procedurally."""
import math, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from font5x7 import GLYPHS, CHARS

OUT = sys.argv[1] if len(sys.argv) > 1 else "build"
os.makedirs(OUT, exist_ok=True)

# ---------------- shared constants ----------------
HZ = 96          # horizon scanline
D = 127          # road lines (d = 1..127 -> y = HZ+d)
CAMH = 2.4       # camera height (world units)
F = 220.0        # focal length (pixels)
ZCAR = 7.0       # player car distance ahead of camera
ROADW = 5.5      # road half width
RUMB = 0.7
LANE = 0.13
SAND = 15.0
PLANE_W, PLANE_H = 1024, 256
ROW_T = 255      # fully transparent plane row
CAR_BW, CAR_BH = 120, 64  # player car buffer (pixels): 15x8 cells, two bands of 4 sprites
CAR_TOP = 137             # screen y of car buffer top

# ---------------- palettes (levels 0..7) ----------------
def cram(r, g, b):
    return (b << 9) | (g << 5) | (r << 1)

PAL0 = [(0,0,0),
        (0,2,5),(0,3,6),            # 1-2 sea
        (7,6,4),(6,5,3),            # 3-4 sand
        (2,5,1),(1,4,1),            # 5-6 grass
        (3,3,3),(2,2,3),            # 7-8 road
        (7,7,7),(7,1,1),            # 9-10 rumble
        (7,7,5),                    # 11 lane
        (7,7,7),(7,7,0),(0,0,0),    # 12 white 13 yellow 14 black
        (0,0,2)]                    # 15 HUD navy
PAL1 = [(0,0,0),
        (1,3,7),(2,4,7),(3,5,7),(4,6,7),(5,6,7),(6,7,7),  # 1-6 sky
        (3,4,6),(2,4,3),            # 7 far hills 8 near hills
        (7,7,5),                    # 9 sun
        (0,2,5),(1,4,6),            # 10-11 sea at horizon
        (7,7,7),                    # 12 cloud
        (0,3,1),(4,2,1),(1,6,1)]    # 13 frond dark 14 trunk 15 frond light
PAL2 = [(0,0,0),
        (4,0,0),(6,0,0),(7,1,1),(7,4,3),   # 1-4 red body (player car, helicopter, outfit)
        (0,1,2),(1,2,3),(2,3,5),           # 5-7 cabin glass
        (0,0,0),(2,2,2),(7,0,0),           # 8 black 9 grey 10 tail light
        (7,5,4),(7,7,7),(6,4,3),(0,0,0),(3,1,0)]  # 11 skin 12 white 13 skin shade 14 black 15 hair
PAL3 = [(0,0,0),
        (4,3,0),(5,4,0),(6,5,0),(7,6,1),   # 1-4 yellow body (rivals)
        (0,1,2),(1,2,3),(2,3,5),           # 5-7 cabin
        (0,0,0),(3,3,3),(7,0,0),           # 8 black 9 grey 10 tail
        (0,1,4),(0,2,5),(1,3,7),(3,5,7),   # 11-14 blue body
        (5,7,7)]                           # 15 heli glass
PALS = [PAL0, PAL1, PAL2, PAL3]

# ---------------- tile helpers ----------------
def img_tiles(px, w, h):
    """px: list of rows of palette indices. returns list of 32-byte tiles, row-major cells."""
    tiles = []
    for cy in range(h // 8):
        for cx in range(w // 8):
            tiles.append(tile_at(px, cx * 8, cy * 8))
    return tiles

def tile_at(px, x0, y0):
    b = bytearray()
    for y in range(8):
        row = px[y0 + y]
        for x in range(0, 8, 2):
            b.append(((row[x0 + x] & 15) << 4) | (row[x0 + x + 1] & 15))
    return bytes(b)

class TileBank:
    def __init__(self):
        self.tiles = [bytes(32)]
        self.index = {bytes(32): 0}
    def add_dedup(self, t):
        if t in self.index:
            return self.index[t]
        self.index[t] = len(self.tiles)
        self.tiles.append(t)
        return self.index[t]
    def add_raw(self, ts):
        base = len(self.tiles)
        self.tiles.extend(ts)
        return base
    def reserve(self, n):
        base = len(self.tiles)
        self.tiles.extend([bytes(32)] * n)
        return base

bank = TileBank()

class HiBank:
    """Spare VRAM between the screen tables (window rows 3+, after the sprite table,
    after the scroll table). Tile indices are absolute VRAM tile numbers."""
    def __init__(self, regions):
        self.regions = [[a, b, []] for a, b in regions]
    def add_raw(self, ts):
        for r in self.regions:
            if r[0] + len(r[2]) + len(ts) <= r[1]:
                base = r[0] + len(r[2])
                r[2].extend(ts)
                return base
        return bank.add_raw(ts)          # fall back to the main area
    def reserve(self, n):
        return self.add_raw([bytes(32)] * n)

hi = HiBank([(1804, 1920), (1940, 1952), (1980, 2048)])

def nt(tile, pal=0, prio=0, hf=0, vf=0):
    return (prio << 15) | (pal << 13) | (vf << 12) | (hf << 11) | tile

# ---------------- plane A: road rows ----------------
def road_row(d, phase):
    k = d / CAMH
    row = []
    for x in range(PLANE_W):
        wx = (x - PLANE_W // 2 + 0.5) / k
        a = abs(wx)
        if a < LANE and phase == 0:
            c = 11
        elif a < ROADW:
            c = 7 if phase == 0 else 8
        elif a < ROADW + RUMB:
            c = 9 if phase == 0 else 10
        elif wx > 0:
            c = 5 if phase == 0 else 6
        elif wx > -(ROADW + RUMB + SAND):
            c = 3 if phase == 0 else 4
        else:
            c = 1 if phase == 0 else 2
        row.append(c)
    return row

planeA = [[0] * PLANE_W for _ in range(PLANE_H)]
for d in range(1, D + 1):
    planeA[d - 1] = road_row(d, 0)
    planeA[127 + d] = road_row(d, 1)
# row 127 (between phases) and 255 transparent already

mapA = []
for cy in range(PLANE_H // 8):
    for cx in range(PLANE_W // 8):
        mapA.append(nt(bank.add_dedup(tile_at(planeA, cx * 8, cy * 8)), 0))
n_road = len(bank.tiles)

# ---------------- plane B: panorama ----------------
PB_H = 104
pb = Image.new("P", (PLANE_W, 256), 0)
dr = ImageDraw.Draw(pb)
bands = [0, 22, 40, 56, 70, 82]
for y in range(PB_H):
    b = sum(1 for t in bands if y >= t)
    dr.line([(0, y), (PLANE_W, y)], fill=b)
# sea strip along horizon
dr.rectangle([0, HZ - 6, PLANE_W, PB_H], fill=10)
dr.rectangle([0, HZ - 6, PLANE_W, HZ - 5], fill=11)
dr.rectangle([0, HZ - 2, PLANE_W, HZ - 2], fill=11)
# sun
dr.ellipse([300, 20, 322, 42], fill=9)
# clouds
def cloud(x, y, w):
    for i, (ox, oy, r) in enumerate([(0, 4, 0.30), (0.25, 0, 0.35), (0.55, 2, 0.30), (0.8, 5, 0.22)]):
        rw = w * r
        dr.ellipse([x + ox * w, y + oy, x + ox * w + rw * 2, y + oy + rw * 0.7], fill=12)
    dr.rectangle([x + 4, y + w * 0.18, x + w * 1.1, y + w * 0.24], fill=12)
cloud(40, 14, 46); cloud(200, 30, 34); cloud(330, 10, 50)
# far + near hills (right half of panorama), island on the sea side
def ridge(x0, x1, base, amp, seed, col, step=4):
    pts = [(x0, HZ - 4)]
    for x in range(x0, x1 + 1, step):
        t = (x - x0) / (x1 - x0)
        env = math.sin(t * math.pi) ** 0.7
        h = base + env * amp * (0.65 + 0.2 * math.sin(x / 23.0 + seed) + 0.15 * math.sin(x / 9.0 + seed * 2))
        pts.append((x, HZ - 4 - h))
    pts.append((x1, HZ - 4))
    dr.polygon(pts, fill=col)
ridge(220, 500, 6, 30, 1.3, 7)
ridge(290, 470, 2, 16, 4.1, 8, 3)
ridge(60, 130, 1, 7, 2.0, 13, 2)
for bx0, by0 in ((170, HZ - 7), (420, HZ - 6)):        # distant sailboats on the horizon
    dr.polygon([(bx0, by0 - 7), (bx0, by0 - 1), (bx0 + 4, by0 - 1)], fill=12)
    dr.rectangle([bx0 - 2, by0, bx0 + 4, by0], fill=14)
pbpx = [[pb.getpixel((x % 512, y)) if y <= HZ else 0 for x in range(PLANE_W)] for y in range(256)]
mapB = []
for cy in range(32):
    for cx in range(PLANE_W // 8):
        if cy * 8 <= HZ:
            mapB.append(nt(bank.add_dedup(tile_at(pbpx, cx * 8, cy * 8)), 1))
        else:
            mapB.append(nt(0, 1))
n_back = len(bank.tiles) - n_road

# ---------------- fonts ----------------
def glyph_px(ch, ink, shadow, scale=1):
    g = GLYPHS[ch]
    W = 8 * scale
    px = [[15] * W for _ in range(W)]
    for yy in range(7):
        for xx in range(5):
            if g[yy][xx] == '#':
                for sy in range(scale):
                    for sx in range(scale):
                        X, Y = 1 + xx * scale + sx, yy * scale + sy
                        if scale == 2:
                            X, Y = 2 + xx * 2 + sx, 1 + yy * 2 + sy
                        if Y + 1 < W and X + 1 < W and px[Y + 1][X + 1] == 15:
                            px[Y + 1][X + 1] = shadow
                        px[Y][X] = ink
    return px

FONT_W = bank.add_raw([tile_at(glyph_px(c, 12, 14), 0, 0) for c in CHARS])
YCHARS = " ACEFHIKLMNOPRSTU/<>"
FONT_Y = bank.add_raw([tile_at(glyph_px(c, 13, 14), 0, 0) for c in YCHARS])
# big digits 16x16, column-major 2x2 (sprite & window usable)
big = []
for c in "1234":            # race position only
    px = glyph_px(c, 12, 14, 2)
    big += [tile_at(px, 0, 0), tile_at(px, 0, 8), tile_at(px, 8, 0), tile_at(px, 8, 8)]
BIGDIG = bank.add_raw(big)


# ---------------- sprite frame helper ----------------
frames = []   # (name, w_cells, h_cells, ox, oy, chunks[(dx,dy,size,tileoff)], tilebase)

class PoolBank:
    """Roadside-object art: kept in ROM, copied into a shared VRAM pool when a track loads."""
    def __init__(self):
        self.tiles = []
    def add_raw(self, ts):
        off = len(self.tiles)
        self.tiles.extend(ts)
        return off
pool = PoolBank()
frame_pooled = {}

def add_sprite_frame(name, img, ox, oy, target=None):
    """img: PIL P image (any size). ox,oy: anchor inside image. Splits into <=32x32 chunks."""
    w = (img.width + 7) // 8 * 8
    h = (img.height + 7) // 8 * 8
    px = [[0] * w for _ in range(h)]
    for y in range(img.height):
        for x in range(img.width):
            px[y][x] = img.getpixel((x, y))
    chunks = []
    tiles = []
    for cy0 in range(0, h // 8, 4):
        for cx0 in range(0, w // 8, 4):
            cw = min(4, w // 8 - cx0)
            ch = min(4, h // 8 - cy0)
            # skip empty chunks
            empty = all(px[y][x] == 0 for y in range(cy0 * 8, (cy0 + ch) * 8) for x in range(cx0 * 8, (cx0 + cw) * 8))
            if empty:
                continue
            off = len(tiles)
            for cx in range(cx0, cx0 + cw):
                for cy in range(cy0, cy0 + ch):
                    tiles.append(tile_at(px, cx * 8, cy * 8))
            chunks.append((cx0 * 8 - ox, cy0 * 8 - oy, ((cw - 1) << 2) | (ch - 1), off))
    base = (target or bank).add_raw(tiles)
    frames.append((name, chunks, base))
    if target is pool:
        frame_pooled[len(frames) - 1] = len(tiles)
    return len(frames) - 1

# ---------------- car model (parametric; the car editor uses the same formula) ----------------
MAT_SHADOW, MAT_BODY, MAT_CABIN, MAT_TYRE, MAT_GREY, MAT_TAIL = range(6)
DEFAULT_CAR = dict(
    half_len=1.90, half_width=0.86, ride=0.15, deck=0.62, nose=0.40, top_inset=0.04,
    cab_rear=-0.85, cab_front=0.80, cab_width=0.74, roof_h=0.98, roof_width=0.56,
    roof_rear=-0.50, roof_front=0.25,
    wing_h=0.80, wing_width=0.88, wing_depth=0.34,
    wheel_h=0.47, wheel_len=0.36, wheel_out=0.95, wheel_in=0.68, axle_rear=-1.20, axle_front=1.25,
    shadow_w=1.00)

def build_car(P):
    """Returns (verts, faces) where faces = [(idx4, material, always_draw)] in painter's order.
    Winding: right-hand rule gives the outward normal."""
    V = []
    F_ = []
    def v(x, y, z):
        V.append((x, y, z)); return len(V) - 1
    def face(idx, mat, always=False):
        F_.append((idx, mat, always))
    def boxfaces(x0, x1, y0, y1, z0, z1, mat, which):
        a = [v(x0, y0, z0), v(x1, y0, z0), v(x1, y0, z1), v(x0, y0, z1),
             v(x0, y1, z0), v(x1, y1, z0), v(x1, y1, z1), v(x0, y1, z1)]
        if 'k' in which: face([a[0], a[4], a[5], a[1]], mat)
        if 'l' in which: face([a[0], a[3], a[7], a[4]], mat)
        if 'r' in which: face([a[1], a[5], a[6], a[2]], mat)
        if 't' in which: face([a[4], a[7], a[6], a[5]], mat)
        if 'f' in which: face([a[3], a[2], a[6], a[7]], mat)
    L, W = P["half_len"], P["half_width"]
    def body_y(z):
        return P["deck"] + (z + L) / (2 * L) * (P["nose"] - P["deck"])
    sw = P["shadow_w"]
    s = [v(-sw, 0.0, -L - 0.15), v(sw, 0.0, -L - 0.15), v(sw, 0.0, L + 0.1), v(-sw, 0.0, L + 0.1)]
    face([s[0], s[3], s[2], s[1]], MAT_SHADOW, True)
    for sx in (-1, 1):
        for zc in (P["axle_rear"], P["axle_front"]):
            x0, x1 = (P["wheel_in"], P["wheel_out"]) if sx > 0 else (-P["wheel_out"], -P["wheel_in"])
            boxfaces(x0, x1, 0.0, P["wheel_h"], zc - P["wheel_len"], zc + P["wheel_len"], MAT_TYRE, "lrtkf")
    tw = W - P["top_inset"]
    b0, b1, b2, b3 = v(-W, P["ride"], -L), v(W, P["ride"], -L), v(W, P["ride"], L), v(-W, P["ride"], L)
    t0, t1, t2, t3 = v(-tw, P["deck"], -L), v(tw, P["deck"], -L), v(tw, P["nose"], L), v(-tw, P["nose"], L)
    face([b0, b3, t3, t0], MAT_BODY)
    face([b1, t1, t2, b2], MAT_BODY)
    face([b0, t0, t1, b1], MAT_BODY)
    face([b3, b2, t2, t3], MAT_BODY)
    face([t0, t3, t2, t1], MAT_BODY)
    zr = -L - 0.005
    ty0 = P["ride"] + (P["deck"] - P["ride"]) * 0.53
    ty1 = P["ride"] + (P["deck"] - P["ride"]) * 0.81
    for x0, x1 in ((0.47 * W, 0.88 * W), (-0.88 * W, -0.47 * W)):
        face([v(x0, ty0, zr), v(x0, ty1, zr), v(x1, ty1, zr), v(x1, ty0, zr)], MAT_TAIL)
    gy0 = P["ride"] + (P["deck"] - P["ride"]) * 0.15
    gy1 = P["ride"] + (P["deck"] - P["ride"]) * 0.40
    face([v(-0.35 * W, gy0, zr), v(-0.35 * W, gy1, zr), v(0.35 * W, gy1, zr), v(0.35 * W, gy0, zr)], MAT_TYRE)
    zb0, zb1, cw = P["cab_rear"], P["cab_front"], P["cab_width"]
    zr0, zr1, rw, rh = P["roof_rear"], P["roof_front"], P["roof_width"], P["roof_h"]
    c0, c1 = v(-cw, body_y(zb0), zb0), v(cw, body_y(zb0), zb0)
    c2, c3 = v(cw, body_y(zb1), zb1), v(-cw, body_y(zb1), zb1)
    r0, r1, r2, r3 = v(-rw, rh, zr0), v(rw, rh, zr0), v(rw, rh, zr1), v(-rw, rh, zr1)
    face([c0, r0, r1, c1], MAT_CABIN)
    face([c0, c3, r3, r0], MAT_CABIN)
    face([c1, r1, r2, c2], MAT_CABIN)
    face([c3, c2, r2, r3], MAT_CABIN)
    face([r0, r3, r2, r1], MAT_BODY)
    if P["wing_h"] > P["deck"] + 0.02:
        zw0, zw1 = -L, -L + P["wing_depth"]
        zs = -L + 0.12
        for xs in (-0.58 * P["wing_width"], 0.58 * P["wing_width"]):
            boxfaces(xs - 0.05, xs + 0.05, P["deck"] - 0.02, P["wing_h"], zs, zs + 0.10, MAT_GREY, "lrk")
        boxfaces(-P["wing_width"], P["wing_width"], P["wing_h"], P["wing_h"] + 0.07, zw0, zw1, MAT_BODY, "lrtk")
    return V, F_

def face_normal(Vs, idx):
    p = [Vs[i] for i in idx]
    u = [p[2][k] - p[0][k] for k in range(3)]
    w = [p[3][k] - p[1][k] for k in range(3)]
    n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
    l = math.sqrt(sum(a * a for a in n)) or 1
    return tuple(a / l for a in n)

V, _faces = build_car(DEFAULT_CAR)
faces = [(idx, mat, face_normal(V, idx), not always) for idx, mat, always in _faces]

LIGHT = (-0.45, 0.78, -0.43)
ll = math.sqrt(sum(a * a for a in LIGHT)); LIGHT = tuple(a / ll for a in LIGHT)

def shade_index(n, mat, pal_body):
    d = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]
    if mat == MAT_SHADOW: return 8
    if mat == MAT_TYRE: return 8
    if mat == MAT_GREY: return 9
    if mat == MAT_TAIL: return 10
    if mat == MAT_CABIN:
        return 5 + (0 if d < 0.15 else (1 if d < 0.55 else 2))
    sh = 0 if d < 0.1 else (1 if d < 0.4 else (2 if d < 0.7 else 3))
    return pal_body + sh

def project(p, camx=0.0):
    x, y, z = p
    return (160 + (x - camx) * F / z, HZ - (y - CAMH) * F / z)

def render_car(zc, xoff, yaw, pal_body, ox_screen=None):
    """Render car with ground centre at (xoff, 0, zc). Returns P image + anchor."""
    cs, sn = math.cos(yaw), math.sin(yaw)
    img = Image.new("P", (320, 224), 0)
    d = ImageDraw.Draw(img)
    for idx, mat, n, cull in faces:
        pts = []
        for i in idx:
            x, y, z = V[i]
            X = x * cs + z * sn
            Z = -x * sn + z * cs
            pts.append((X + xoff, y, Z + zc))
        if cull:
            nx = n[0] * cs + n[2] * sn
            nz = -n[0] * sn + n[2] * cs
            cx = sum(p[0] for p in pts) / 4; cy = sum(p[1] for p in pts) / 4; cz = sum(p[2] for p in pts) / 4
            if nx * (0 - cx) + n[1] * (CAMH - cy) + nz * (0 - cz) <= 0:
                continue
        sp = [project(p) for p in pts]
        nn = (n[0] * cs + n[2] * sn, n[1], -n[0] * sn + n[2] * cs)
        d.polygon(sp, fill=shade_index(nn, mat, pal_body))
    bb = img.getbbox()
    ax, ay = project((xoff, 0, zc))
    crop = img.crop(bb)
    return crop, int(round(ax)) - bb[0], int(round(ay)) - bb[1]

# screen-space winding sign of a visible face (rear body face) for C culling
def area(sp):
    return sum(sp[i][0] * sp[(i + 1) % 4][1] - sp[(i + 1) % 4][0] * sp[i][1] for i in range(4))
rear = [f for f in faces if f[1] == MAT_BODY][2]
VIS_SIGN = 1 if area([project((V[i][0], V[i][1], V[i][2] + ZCAR)) for i in rear[0]]) > 0 else -1

# ---------------- rival car frames ----------------
RIVAL_Z = [7.0, 9.0, 12.0, 16.0, 22.0, 31.0, 45.0, 70.0]
rival_red, rival_blue = [], []
RIVAL_T0 = len(bank.tiles)
for zc in RIVAL_Z[1:]:
    img, ax, ay = render_car(zc, 0.0, 0.0, 1)
    rival_red.append(add_sprite_frame("red%g" % zc, img, ax, ay))
rival_red.insert(0, rival_red[0])
for zc in RIVAL_Z[1:]:
    img, ax, ay = render_car(zc, 0.0, 0.0, 11)
    rival_blue.append(add_sprite_frame("blue%g" % zc, img, ax, ay))
rival_blue.insert(0, rival_blue[0])
RIVAL_NT = len(bank.tiles) - RIVAL_T0

# ---------------- title logo + credit: borrow the rival tiles while the title is up ----------------
class TitleBank:
    def __init__(self, t0, n):
        self.t0, self.n, self.tiles = t0, n, []
    def add_raw(self, ts):
        base = self.t0 + len(self.tiles)
        self.tiles.extend(ts)
        assert len(self.tiles) <= self.n, "title art (%d tiles) doesn't fit the rival tiles (%d)" % (len(self.tiles), self.n)
        return base
title_bank = TitleBank(RIVAL_T0, RIVAL_NT)
_art = os.path.join(os.path.dirname(__file__), "art")
_logo = Image.open(os.path.join(_art, "logo.png"))
_credit = Image.open(os.path.join(_art, "credit.png"))
LOGO_PAL = [0] * 16
_lp = _logo.getpalette()[:30]
for i in range(1, 10):
    r, g_, b = _lp[i * 3:i * 3 + 3]
    lv = lambda v: min(range(8), key=lambda k: abs([0, 52, 87, 116, 144, 172, 206, 255][k] - v))
    LOGO_PAL[i] = (lv(b) << 9) | (lv(g_) << 5) | (lv(r) << 1)
FR_LOGO = add_sprite_frame("logo", _logo, _logo.width // 2, 0, title_bank)      # centre anchor: chunk offsets are s8
FR_CREDIT = add_sprite_frame("credit", _credit, _credit.width // 2, 0, title_bank)
LOGO_W, LOGO_H = _logo.size
CREDIT_W = _credit.width

# ---------------- roadside objects (pooled per track) ----------------
# Each type: draw(img, s) where s = pixels per world unit, anchor at bottom centre.
OTYPES = []   # dict(name, pal, height, frames[(frame_idx, z)], zmin, zmax, tiles, where)

def make_type(name, pal, height, width, heights, draw, where, zmax_units=176):
    fl, tiles = [], 0
    for hpx in heights:
        sc = hpx / height
        Wc, Hc = int(width * sc) + 6, int(height * sc) + 4
        img = Image.new("P", (Wc, Hc), 0)
        ax, ay = draw(img, sc)
        bb = img.getbbox()
        if not bb:
            continue
        fi = add_sprite_frame("%s%d" % (name, hpx), img.crop(bb), int(ax) - bb[0], int(ay) - bb[1], pool)
        fl.append((fi, F * height / hpx))
        tiles += frame_pooled[fi]
    zmin = fl[0][1] * 0.92
    OTYPES.append(dict(name=name, pal=pal, height=height, frames=fl, zmin=zmin,
                       zmax=min(zmax_units, fl[-1][1] * 1.6), tiles=tiles, where=where))

def draw_palm(img, s):
    dd = ImageDraw.Draw(img)
    W, H = img.size
    bx, by = W * 0.42, H - 2
    th = 7.0 * s
    lean = 0.9 * s
    for i in range(6):
        t0, t1 = i / 6, (i + 1) / 6
        x0 = bx + lean * t0 * t0; x1 = bx + lean * t1 * t1
        w0 = max(1.0, 0.32 * s * (1 - 0.4 * t0)); w1 = max(1.0, 0.32 * s * (1 - 0.4 * t1))
        dd.polygon([(x0 - w0, by - th * t0), (x0 + w0, by - th * t0), (x1 + w1, by - th * t1), (x1 - w1, by - th * t1)], fill=14)
    tx, ty = bx + lean, by - th
    for ang, ln in [(-170, 3.0), (-140, 2.6), (-100, 1.6), (-60, 2.4), (-25, 3.0), (10, 2.6), (170, 2.4), (200, 2.0), (-200, 2.2)]:
        a = math.radians(ang)
        ex, ey = tx + math.cos(a) * ln * s, ty + math.sin(a) * 0.7 * ln * s + 1.1 * s
        mx, my = tx + math.cos(a) * ln * 0.5 * s, ty + math.sin(a) * 0.7 * ln * 0.5 * s - 0.25 * s
        wv = max(0.8, 0.28 * s)
        dd.polygon([(tx, ty), (mx, my - wv), (ex, ey), (mx, my + wv)], fill=15 if (ang // 30) % 2 else 13)
    return bx, by

def draw_boat(img, s):
    dd = ImageDraw.Draw(img)
    h = 4.6 * s
    w = h * 0.9
    mx = 2 + w * 0.45
    hull = 2 + h * 0.80
    dd.polygon([(mx, 2), (mx, hull - 1), (3, hull - 1)], fill=12)
    dd.polygon([(mx + 1, 2 + h * 0.15), (mx + 1, hull - 1), (2 + w - 1, hull - 1)], fill=5)
    dd.line([(mx, 2), (mx, hull)], fill=14)
    dd.polygon([(2, hull), (2 + w, hull), (2 + w - max(1, h / 8), 2 + h), (2 + max(1, h / 8), 2 + h)], fill=14)
    return mx, 2 + h

def draw_billboard(img, s):          # pal0: posts grey, yellow frame, red panel, white chevrons
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    pw, ph, py = 5.0 * s, 2.4 * s, 4.2 * s
    for px_ in (cx - pw * 0.32, cx + pw * 0.32):
        dd.rectangle([px_ - max(0.5, 0.1 * s), by - py + ph * 0.5, px_ + max(0.5, 0.1 * s), by], fill=7)
    x0, y0 = cx - pw / 2, by - py
    dd.rectangle([x0, y0, x0 + pw, y0 + ph], fill=13)
    m = max(1, 0.18 * s)
    dd.rectangle([x0 + m, y0 + m, x0 + pw - m, y0 + ph - m], fill=10)
    if s > 3:
        for k in range(3):
            xx = x0 + pw * (0.25 + k * 0.22)
            dd.polygon([(xx, y0 + ph * 0.25), (xx + 0.5 * s, y0 + ph * 0.5), (xx, y0 + ph * 0.75),
                        (xx + 0.25 * s, y0 + ph * 0.5)], fill=12)
    return cx, by

def draw_lamp(img, s):               # pal0: pole on the left of the canvas, arm reaching right
    dd = ImageDraw.Draw(img)
    W, H = img.size
    bx, by = 3 + 0.2 * s, H - 2
    top = by - 6.0 * s
    dd.rectangle([bx - max(0.5, 0.12 * s), top, bx + max(0.5, 0.12 * s), by], fill=7)
    dd.line([(bx, top), (bx + 1.6 * s, top + 0.25 * s)], fill=7, width=max(1, int(0.18 * s)))
    hx = bx + 1.6 * s
    dd.rectangle([hx - 0.45 * s, top, hx + 0.45 * s, top + max(1, 0.3 * s)], fill=8)
    dd.rectangle([hx - 0.35 * s, top + max(1, 0.3 * s), hx + 0.35 * s, top + max(2, 0.45 * s)], fill=13)
    dd.rectangle([bx - 0.3 * s, by - 0.4 * s, bx + 0.3 * s, by], fill=8)
    return bx, by

def draw_cone(img, s):               # pal0: red cone with white band
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    h = 0.8 * s
    dd.polygon([(cx - 0.32 * s, by - 0.08 * s), (cx + 0.32 * s, by - 0.08 * s), (cx + 0.06 * s, by - h), (cx - 0.06 * s, by - h)], fill=10)
    if h > 6:
        dd.rectangle([cx - 0.2 * s, by - h * 0.6, cx + 0.2 * s, by - h * 0.45], fill=12)
    dd.rectangle([cx - 0.42 * s, by - max(1, 0.08 * s), cx + 0.42 * s, by], fill=8)
    return cx, by

def draw_stand(img, s):              # pal0: grandstand seen from the road
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    w, h = 10.0 * s, 5.0 * s
    x0 = cx - w / 2
    dd.rectangle([x0, by - h, x0 + w, by], fill=8)
    rows = max(2, int(h / max(2, 0.7 * s)))
    cols_ = [10, 12, 13, 11, 12, 10, 13]
    for r in range(rows):
        yy = by - h + 2 + r * (h - 3) / rows
        dd.line([(x0 + 1, yy), (x0 + w - 1, yy)], fill=7)
        if s > 2.5:
            for k in range(int(w / max(2, 0.6 * s))):
                xx = x0 + 2 + k * max(2, 0.6 * s)
                if xx < x0 + w - 2:
                    img.putpixel((int(xx), int(yy) - 1), cols_[(k + r) % len(cols_)])
    dd.polygon([(x0 - 0.3 * s, by - h), (x0 + w + 0.3 * s, by - h), (x0 + w, by - h - 0.8 * s), (x0, by - h - 0.8 * s)], fill=9)
    dd.rectangle([x0, by - h, x0 + max(1, 0.15 * s), by], fill=14)
    dd.rectangle([x0 + w - max(1, 0.15 * s), by - h, x0 + w, by], fill=14)
    return cx, by

def draw_rock(img, s):               # pal0: grey boulder
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    w, h = 3.0 * s, 2.0 * s
    pts = [(cx - w / 2, by), (cx - w * 0.45, by - h * 0.5), (cx - w * 0.15, by - h), (cx + w * 0.25, by - h * 0.9),
           (cx + w / 2, by - h * 0.35), (cx + w * 0.42, by)]
    dd.polygon(pts, fill=7)
    dd.polygon([(cx + w * 0.05, by - h * 0.95), (cx + w * 0.25, by - h * 0.9), (cx + w / 2, by - h * 0.35),
                (cx + w * 0.42, by), (cx + w * 0.1, by)], fill=8)
    if s > 4:
        dd.line([(cx - w * 0.2, by - h * 0.6), (cx, by - h * 0.3)], fill=14)
    return cx, by


def draw_oil(img, s):                # pal0 locked colours: flat black pool with a dark sheen, lies on the road
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    w, h = 2.6 * s, max(2, 0.55 * s)
    dd.ellipse([cx - w / 2, by - h, cx + w / 2, by], fill=14)
    dd.ellipse([cx - w * 0.62, by - h * 0.7, cx - w * 0.15, by - h * 0.05], fill=14)
    dd.ellipse([cx + w * 0.05, by - h * 1.05, cx + w * 0.55, by - h * 0.35], fill=14)
    if s > 3:
        dd.line([(cx - w * 0.25, by - h * 0.55), (cx + w * 0.1, by - h * 0.65)], fill=15)
        dd.line([(cx + w * 0.15, by - h * 0.35), (cx + w * 0.32, by - h * 0.3)], fill=15)
    return cx, by

def draw_tyre(img, s):               # a loose tyre standing on its tread, seen face-on
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    r = 0.36 * s
    dd.ellipse([cx - r * 0.75, by - 2 * r, cx + r * 0.75, by], fill=14)
    if s > 4:
        dd.ellipse([cx - r * 0.35, by - r * 1.4, cx + r * 0.35, by - r * 0.6], fill=7)
        dd.ellipse([cx - r * 0.18, by - r * 1.2, cx + r * 0.18, by - r * 0.8], fill=8)
    return cx, by

def draw_shrub(img, s):              # pal1: clumps in the palm greens
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    w, h = 2.4 * s, 1.5 * s
    blobs = [(-0.32, 0.45, 0.42), (0.3, 0.5, 0.4), (0.0, 0.75, 0.48), (-0.15, 0.3, 0.35), (0.22, 0.25, 0.33)]
    for k, (bx, byf, r) in enumerate(blobs):
        x0, y0 = cx + bx * w, by - byf * h
        rr = r * w * 0.5
        dd.ellipse([x0 - rr, y0 - rr * 0.8, x0 + rr, y0 + rr * 0.8], fill=13)
    for bx, byf, r in blobs[:3]:
        x0, y0 = cx + bx * w + 0.1 * s, by - byf * h - 0.15 * s
        rr = r * w * 0.28
        if rr >= 1:
            dd.ellipse([x0 - rr, y0 - rr * 0.7, x0 + rr, y0 + rr * 0.7], fill=15)
    dd.rectangle([cx - w * 0.42, by - max(1, 0.12 * s), cx + w * 0.42, by], fill=13)
    return cx, by

def draw_tyrewall(img, s):           # trackside barrier: three stacks of tyres, white paint on top
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    tw, th = 0.75 * s, max(1.5, 0.3 * s)
    for col in range(3):
        x0 = cx - 1.5 * tw + col * tw
        for row in range(4):
            y1 = by - row * th
            dd.ellipse([x0, y1 - th, x0 + tw - max(1, 0.06 * s), y1], fill=12 if row == 3 else 14)
            if s > 5 and row < 3:
                dd.line([(x0 + tw * 0.3, y1 - th * 0.55), (x0 + tw * 0.6, y1 - th * 0.55)], fill=7)
    return cx, by

def draw_drum(img, s):               # oil drum: kerb-red body, white band, dark rims
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    w, h = 0.6 * s, 0.9 * s
    dd.rectangle([cx - w / 2, by - h, cx + w / 2, by], fill=10)
    dd.rectangle([cx + w * 0.15, by - h, cx + w / 2, by], fill=8 if s < 6 else 10)
    if s > 3:
        dd.rectangle([cx - w / 2, by - h * 0.62, cx + w / 2, by - h * 0.5], fill=12)
    dd.rectangle([cx - w / 2, by - h, cx + w / 2, by - h + max(1, 0.06 * s)], fill=14)
    dd.rectangle([cx - w / 2, by - max(1, 0.05 * s), cx + w / 2, by], fill=14)
    return cx, by

def draw_umbrella(img, s):           # striped beach umbrella in the kerb colours
    dd = ImageDraw.Draw(img)
    W, H = img.size
    cx, by = W / 2, H - 2
    hgt, r = 2.6 * s, 1.5 * s
    top = by - hgt
    dd.line([(cx, top), (cx, by)], fill=7, width=max(1, int(0.08 * s)))
    n = 6
    for k in range(n):
        a0, a1 = -r + 2 * r * k / n, -r + 2 * r * (k + 1) / n
        dd.polygon([(cx, top - 0.45 * s), (cx + a0, top + 0.25 * s), (cx + a1, top + 0.25 * s)], fill=10 if k % 2 else 9)
    dd.rectangle([cx - r, top + 0.2 * s, cx + r, top + max(0.25 * s, 0.2 * s + 1)], fill=10)
    return cx, by

make_type("palm", 1, 8.2, 7.0, [72, 52, 40, 30, 22, 16, 11], draw_palm, "side")
make_type("sailboat", 1, 4.6, 4.2, [26, 18, 12, 8], draw_boat, "sea")
make_type("billboard", 0, 4.6, 5.4, [40, 28, 20, 14, 10], draw_billboard, "side")
make_type("lamp post", 0, 6.2, 2.2, [52, 38, 27, 19, 13], draw_lamp, "side")
make_type("cone", 0, 0.9, 0.9, [16, 11, 7, 5], draw_cone, "edge", 90)
make_type("grandstand", 0, 5.9, 10.8, [40, 28, 20, 14, 10], draw_stand, "side")
make_type("rock", 0, 2.1, 3.1, [28, 19, 13, 9, 6], draw_rock, "side")
# type 7 is the flag girl: she is drawn from her own resident frames, so her table slot is empty
OTYPES.append(dict(name="flag girl", pal=2, height=0, frames=[], zmin=0, zmax=0, tiles=0, where="start", girl=True))
make_type("oil slick", 0, 0.6, 2.8, [9, 6, 4], draw_oil, "road", 120)
make_type("tyre", 0, 0.8, 0.7, [14, 9, 6, 4], draw_tyre, "road", 100)
make_type("shrub", 1, 1.6, 2.6, [26, 17, 11, 7, 5], draw_shrub, "side")
make_type("tyre wall", 0, 1.3, 2.4, [22, 15, 10, 6], draw_tyrewall, "edge", 140)
make_type("oil drum", 0, 1.0, 0.7, [18, 12, 8, 5], draw_drum, "edge", 110)
make_type("beach umbrella", 0, 2.9, 3.2, [36, 24, 16, 11, 7], draw_umbrella, "side")

# ---------------- helicopter (pal2, red), side view facing left ----------------
heli_frames = []   # [body_big, body_small, rotor_big0..2, rotor_small0..2]
def heli_canvas(scale):
    return Image.new("P", (int(72 * scale) + 2, int(36 * scale) + 2), 0)
def crop_anchor(img, ax, ay):
    bb = img.getbbox()
    return img.crop(bb), int(ax) - bb[0], int(ay) - bb[1]
for size, scale in (("big", 1.0), ("small", 0.5)):
    img = heli_canvas(scale); dd = ImageDraw.Draw(img)
    def P(pts):
        return [(x * scale, y * scale) for x, y in pts]
    dd.polygon(P([(30, 15), (62, 13), (62, 16), (30, 20)]), fill=2)          # tail boom
    dd.polygon(P([(58, 6), (64, 6), (65, 16), (60, 16)]), fill=3)            # fin
    dd.polygon(P([(8, 16), (14, 9), (30, 8), (36, 11), (38, 20), (32, 25), (12, 25)]), fill=3)
    dd.polygon(P([(12, 25), (32, 25), (38, 20), (36, 23), (30, 27), (14, 27)]), fill=1)
    dd.polygon(P([(14, 9), (30, 8), (34, 11), (16, 12)]), fill=4)
    dd.polygon(P([(8, 16), (14, 9), (19, 9), (17, 17)]), fill=7)            # glass
    dd.polygon(P([(20, 11), (26, 11), (26, 16), (20, 16)]), fill=7)
    dd.line(P([(10, 31), (36, 31)]), fill=8, width=max(1, int(2 * scale)))   # skids
    dd.line(P([(16, 27), (15, 31)]), fill=8, width=1)
    dd.line(P([(30, 27), (31, 31)]), fill=8, width=1)
    dd.rectangle(P([(22, 5), (24, 8)]), fill=8)                              # mast
    dd.line(P([(63, 9), (63, 13)]), fill=9, width=1)                         # tail rotor
    im, ax, ay = crop_anchor(img, 23 * scale, 5 * scale)
    heli_frames.append(add_sprite_frame("heli_" + size, im, ax, ay))
for size, scale in (("big", 1.0), ("small", 0.5)):
    for fr, half in enumerate((28, 15, 5)):
        img = Image.new("P", (int(64 * scale) + 4, 8), 0); dd = ImageDraw.Draw(img)
        cx = img.width // 2
        dd.line([(cx - half * scale, 2), (cx + half * scale, 2)], fill=9, width=max(1, int(2 * scale)))
        dd.point((cx, 3), fill=8)
        im, ax, ay = crop_anchor(img, cx, 3)
        heli_frames.append(add_sprite_frame("rotor_%s%d" % (size, fr), im, ax, ay))

# ---------------- flag girl (pal2), original hand-placed pixel art in tools/girl_art.py ----------------
import girl_art
def draw_girl(pose):
    return girl_art.girl(pose)

girl_frames = []
for pose in range(3):
    im, ax, ay = draw_girl(pose)
    bb = im.getbbox()
    girl_frames.append(add_sprite_frame("girl%d" % pose, im.crop(bb), ax - bb[0], ay - bb[1], hi))

# ---------------- start light (pal0 housing, lamp overlays) ----------------
img = Image.new("P", (16, 32), 0)
d = ImageDraw.Draw(img)
d.rounded_rectangle([0, 0, 15, 31], radius=3, fill=14, outline=7)
for i in range(3):
    d.ellipse([4, 3 + i * 9, 11, 10 + i * 9], fill=8)
LIGHT_BOX = add_sprite_frame("lightbox", img, 0, 0, hi)
lamp_tiles = []
for col in (10, 13, 15):
    px = [[0] * 8 for _ in range(8)]
    im = Image.new("P", (8, 8), 0); dd = ImageDraw.Draw(im)
    dd.ellipse([0, 0, 7, 7], fill=col)
    for y in range(8):
        for x in range(8):
            px[y][x] = im.getpixel((x, y))
    px[2][2] = px[2][3] = px[3][2] = 12 if col != 15 else 12   # highlight
    lamp_tiles.append(tile_at(px, 0, 0))
LAMP_T = hi.add_raw(lamp_tiles)

# ---------------- tyre smoke (pal1, dithered so it reads as translucent) ----------------
smoke_frames = []
for r in (3, 5, 7):
    n = 2 * r + 2
    img = Image.new("P", (n, n), 0)
    d = ImageDraw.Draw(img)
    d.ellipse([0, n // 4, n - 1, n - 1], fill=12)
    d.ellipse([n // 4, 0, n - 2, n * 3 // 4], fill=12)
    for y in range(n):
        for x in range(n):
            v = img.getpixel((x, y))
            if v and y > n * 0.55:
                img.putpixel((x, y), 6)
            if v and r >= 5 and (x + y) % 2 == 0:
                img.putpixel((x, y), 0)          # 50% dither: reads as translucent smoke
    bb = img.getbbox()
    smoke_frames.append(add_sprite_frame("smoke%d" % r, img.crop(bb), (bb[2] - bb[0]) // 2, (bb[3] - bb[1]) // 2, hi))

# ---------------- skid streaks (pal0 black), two phases ----------------
skid_tiles = []
for ph in range(2):
    px = [[0] * 8 for _ in range(16)]
    for y in range(16):
        if ((y + ph * 3) % 6) < 4:
            for x in (2, 3, 4, 5):
                px[y][x] = 14 if x in (3, 4) else 8 if False else 14
    skid_tiles += [tile_at(px, 0, 0), tile_at(px, 0, 8)]
SKID_T = hi.add_raw(skid_tiles)

# ---------------- analog speedometer template (pal0), 64x32 ----------------
DIAL_W, DIAL_H, DIAL_CX, DIAL_CY, DIAL_R = 64, 32, 32, 31, 30
dimg = Image.new("P", (DIAL_W, DIAL_H), 0)
d = ImageDraw.Draw(dimg)
d.pieslice([DIAL_CX - DIAL_R, DIAL_CY - DIAL_R, DIAL_CX + DIAL_R, DIAL_CY + DIAL_R], 180, 360, fill=14, outline=12)
for i in range(11):                      # ticks every 18 degrees, red zone at the top end
    ang = math.radians(180 + i * 18)
    r0 = DIAL_R - (5 if i % 2 == 0 else 3)
    col = 10 if i >= 9 else 12
    d.line([(DIAL_CX + math.cos(ang) * r0, DIAL_CY + math.sin(ang) * r0),
            (DIAL_CX + math.cos(ang) * (DIAL_R - 1), DIAL_CY + math.sin(ang) * (DIAL_R - 1))], fill=col)
d.arc([DIAL_CX - DIAL_R + 2, DIAL_CY - DIAL_R + 2, DIAL_CX + DIAL_R - 2, DIAL_CY + DIAL_R - 2], 324, 360, fill=10)
dpx = [[dimg.getpixel((x, y)) for x in range(DIAL_W)] for y in range(DIAL_H)]
dial_tpl = []
for cx in range(DIAL_W // 8):            # column-major, 4 cells tall
    for cy in range(DIAL_H // 8):
        dial_tpl.append(tile_at(dpx, cx * 8, cy * 8))

# ---------------- fuel gauge tiles for the HUD bar (pal0, opaque) ----------------
def fuel_tile(level, col, cap=0):
    px = [[15] * 8 for _ in range(8)]
    for x in range(8):
        px[1][x] = 12; px[6][x] = 12
        for y in range(2, 6):
            px[y][x] = col if x < level else 14
    if cap == 1:
        for y in range(1, 7): px[y][0] = 12
        for y in range(2, 6): px[y][1] = 14
    if cap == 2:
        for y in range(1, 7): px[y][7] = 12
    return tile_at(px, 0, 0)
fuel = [fuel_tile(l, 5) for l in range(9)] + [fuel_tile(l, 10) for l in range(9)]
FUEL_T = hi.add_raw(fuel)

# ---------------- dynamic slots ----------------
DIAL_SLOT = hi.reserve(len(dial_tpl))
CAR_SLOT = bank.reserve((CAR_BW // 8) * (CAR_BH // 8))
NTILES = len(bank.tiles)
assert NTILES <= 1280, "VRAM tile budget exceeded: %d" % NTILES
TACH_SLOT = CAR_SLOT   # main-area ROM tiles end where the car slot starts
# object pool: whatever VRAM is left in the main area and the spare gaps
POOL_REGIONS = [(NTILES, 1280)] + [(r[0] + len(r[2]), r[1]) for r in hi.regions if r[0] + len(r[2]) < r[1]]
POOL_SIZE = sum(b - a for a, b in POOL_REGIONS)

# ---------------- write binaries ----------------
def wbin(name, data):
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(data)

def words(ws):
    return b"".join(bytes([(w >> 8) & 255, w & 255]) for w in ws)

wbin("tiles.bin", b"".join(bank.tiles[:TACH_SLOT]))
wbin("mapa.bin", words(mapA))
wbin("title.bin", b"".join(title_bank.tiles))
wbin("mapb.bin", words(mapB))
wbin("dial.bin", b"".join(dial_tpl))
hib, hit = b"", []
for r0, r1, ts in hi.regions:
    if ts:
        hit.append((r0, len(ts), len(hib) // 2))
        hib += b"".join(ts)
wbin("hi.bin", hib)
wbin("pool.bin", b"".join(pool.tiles))

# ---------------- header ----------------
L = []
L.append("/* generated by gen_assets.py - do not edit */")
L.append("#pragma once")
for k, val in [("HZ", HZ), ("DLINES", D), ("ROW_T", ROW_T), ("CAR_BW", CAR_BW), ("CAR_BH", CAR_BH),
               ("CAR_TOP", CAR_TOP), ("NTILES_ROM", CAR_SLOT), ("CAR_SLOT", CAR_SLOT), ("DIAL_SLOT", DIAL_SLOT),
               ("DIAL_W", DIAL_W), ("DIAL_H", DIAL_H), ("DIAL_CX", DIAL_CX), ("DIAL_CY", DIAL_CY), ("DIAL_R", DIAL_R),
               ("LIGHT_BOX", LIGHT_BOX), ("LAMP_T", LAMP_T), ("SKID_T", SKID_T), ("FUEL_T", FUEL_T),
               ("N_OTYPES", len(OTYPES)), ("N_POOL_REGIONS", len(POOL_REGIONS)), ("MAXV", 128), ("MAXF", 96),
               ("FONT_W", FONT_W), ("FONT_Y", FONT_Y), ("BIGDIG", BIGDIG), ("VIS_SIGN", VIS_SIGN),
               ("N_RIVAL_Z", len(RIVAL_Z))]:
    L.append("#define %s %d" % (k, val))
L.append('#define FONT_CHARS "%s"' % CHARS)
L.append("#define RIVAL_T0 %d\n#define RIVAL_NT %d\n#define TITLE_NT %d\n#define FR_LOGO %d\n#define FR_CREDIT %d\n#define LOGO_W %d\n#define LOGO_H %d\n#define CREDIT_W %d"
         % (RIVAL_T0, RIVAL_NT, len(title_bank.tiles), FR_LOGO, FR_CREDIT, LOGO_W, LOGO_H, CREDIT_W))
L.append("static const u16 logo_pal[16] = {%s};" % ",".join(map(str, LOGO_PAL)))
L.append('#define FONTY_CHARS "%s"' % YCHARS)
L.append("#define FIX_CAMH %d   /* 8.8 */" % round(CAMH * 256))
L.append("#define FIX_F %d" % round(F))
L.append("#define FIX_ZCAR %d" % round(ZCAR * 256))
L.append("#define FIX_ROADW %d" % round(ROADW * 256))
for i, p in enumerate(PALS):
    L.append("static const u16 pal%d[16] = {%s};" % (i, ",".join("0x%03X" % cram(*c) for c in p)))
# line tables: z per line (8.8 world units), k per line (px per unit, 8.8), dz
zl = [0] + [round(CAMH * F / d * 256) for d in range(1, D + 1)]
kl = [0] + [round(d / CAMH * 256) for d in range(1, D + 1)]
L.append("static const s32 zline[%d] = {%s};" % (D + 1, ",".join(map(str, zl))))
L.append("static const u16 kline[%d] = {%s};" % (D + 1, ",".join(map(str, kl))))
zf = [0] + [CAMH * F / d for d in range(1, D + 1)] + [0.0]
dz = [0] + [round((zf[d] - zf[d + 1]) * 16) for d in range(1, D + 1)]
L.append("static const s16 dz16[%d] = {%s};" % (D + 1, ",".join(map(str, dz))))
L.append("static const s16 sintab[256] = {%s};" % ",".join(str(round(math.sin(i * 2 * math.pi / 256) * 16384)) for i in range(256)))
# sprite frames
allch = []
fr_rows = []
for fi, (name, chunks, base) in enumerate(frames):
    fr_rows.append("{%d,%d,%d,%d}" % (len(allch), len(chunks), base, frame_pooled.get(fi, 0)))
    allch.extend(chunks)
L.append("typedef struct { s8 dx, dy; u8 size, pad; u16 toff; } Chunk;")
L.append("typedef struct { u16 first, count, tbase, pooled_tiles; } Frame;   /* pooled: tbase = offset in pool.bin */")
L.append("static const Chunk chunks[%d] = {%s};" % (len(allch), ",".join("{%d,%d,%d,0,%d}" % (max(-128, min(127, dx)), max(-128, min(127, dy)), sz, off) for dx, dy, sz, off in allch)))
assert all(-128 <= c[0] <= 127 and -128 <= c[1] <= 127 for c in allch), "chunk offset overflow"
L.append("static const Frame frames[%d] = {%s};" % (len(frames), ",".join(fr_rows)))
L.append("static const u8 fr_red[%d] = {%s};" % (len(rival_red), ",".join(map(str, rival_red))))
L.append("static const u8 fr_blue[%d] = {%s};" % (len(rival_blue), ",".join(map(str, rival_blue))))
L.append("static const u8 fr_heli[%d] = {%s};" % (len(heli_frames), ",".join(map(str, heli_frames))))
L.append("static const u8 fr_girl[3] = {%s};" % ",".join(map(str, girl_frames)))
L.append("static const u8 fr_smoke[%d] = {%s};" % (len(smoke_frames), ",".join(map(str, smoke_frames))))
# roadside object types: frames + depth thresholds (choose frame i while z < thr[i])
L.append("typedef struct { u8 first, n, pal, pad; u16 zmin, zmax, tiles; u16 thr[8]; } OType;")
rows = []
for t in OTYPES:
    if not t["frames"]:
        rows.append("{0,0,%d,0,0,0,0,{%s}}" % (t["pal"], ",".join(["65535"] * 8)))
        continue
    zs = [z for _, z in t["frames"]]
    th = [round(math.sqrt(zs[i] * zs[i + 1]) * 256) for i in range(len(zs) - 1)] + [round(t["zmax"] * 256)]
    th += [65535] * (8 - len(th))
    rows.append("{%d,%d,%d,0,%d,%d,%d,{%s}}" % (t["frames"][0][0], len(t["frames"]), t["pal"], round(t["zmin"] * 256),
                min(65535, round(t["zmax"] * 256)), t["tiles"], ",".join(map(str, th))))
    assert [f for f, _ in t["frames"]] == list(range(t["frames"][0][0], t["frames"][0][0] + len(t["frames"])))
L.append("static const OType otypes[%d] = {%s};" % (len(OTYPES), ",".join(rows)))
L.append("static const u16 pool_regions[%d][2] = {%s};" % (len(POOL_REGIONS), ",".join("{%d,%d}" % r for r in POOL_REGIONS)))
L.append("#define N_HI_RANGES %d" % len(hit))
L.append("static const u16 hi_ranges[%d][3] = {%s};" % (max(1, len(hit)), ",".join("{%d,%d,%d}" % r for r in hit)))
# bucket thresholds: choose bucket i if z < thr[i] (geometric midpoints), in 8.8
def thr(zs):
    return [round(math.sqrt(zs[i] * zs[i + 1]) * 256) for i in range(len(zs) - 1)] + [round(zs[-1] * 1.4 * 256)]
L.append("static const s32 rival_thr[%d] = {%s};" % (len(RIVAL_Z), ",".join(map(str, thr(RIVAL_Z)))))
L.append("static const s8 light[3] = {%d,%d,%d};" % tuple(round(c * 64) for c in LIGHT))
with open(os.path.join(OUT, "assets.h"), "w") as f:
    f.write("\n".join(L) + "\n")

print("tiles: road %d, backdrop %d, main %d / 1280; spare regions used %s" % (n_road, n_back, NTILES, [(r[0], len(r[2]), r[1]-r[0]) for r in hi.regions]))
print("frames %d, chunks %d, verts %d, faces %d, VIS_SIGN %d" % (len(frames), len(allch), len(V), len(faces), VIS_SIGN))
print("object pool %d tiles in %s; type costs %s" % (POOL_SIZE, POOL_REGIONS, [(t['name'], t['tiles']) for t in OTYPES]))

# ---------------- metadata for gen_data.py and the editors ----------------
import json, base64, io
def any_tile(i):
    if i < len(bank.tiles):
        return bank.tiles[i]
    for r0, r1, ts in hi.regions:
        if r0 <= i < r0 + len(ts):
            return ts[i - r0]
    raise IndexError(i)
def frame_png(fi, pal):
    name, chunks, base = frames[fi]
    src = pool.tiles if fi in frame_pooled else None
    xs = [c[0] for c in chunks] + [c[0] + (((c[2] >> 2) & 3) + 1) * 8 for c in chunks]
    ys = [c[1] for c in chunks] + [c[1] + ((c[2] & 3) + 1) * 8 for c in chunks]
    x0, y0 = min(xs), min(ys)
    img = Image.new("RGBA", (max(xs) - x0, max(ys) - y0), (0, 0, 0, 0))
    for dx, dy, sz, off in chunks:
        cw, ch = ((sz >> 2) & 3) + 1, (sz & 3) + 1
        for cx in range(cw):
            for cy in range(ch):
                t = (src[base + off + cx * ch + cy] if src is not None else any_tile(base + off + cx * ch + cy))
                for yy in range(8):
                    for xx in range(8):
                        b = t[yy * 4 + xx // 2]
                        c = (b >> 4) if xx % 2 == 0 else (b & 15)
                        if c:
                            img.putpixel((dx - x0 + cx * 8 + xx, dy - y0 + cy * 8 + yy), (pal, c, 0, 255))
    buf = io.BytesIO(); img.save(buf, "PNG")
    return dict(png=base64.b64encode(buf.getvalue()).decode(), ax=-x0, ay=-y0, w=img.width, h=img.height)
meta = dict(
    consts=dict(HZ=HZ, D=D, CAMH=CAMH, F=F, ZCAR=ZCAR, ROADW=ROADW, RUMB=RUMB, LANE=LANE, SAND=SAND,
                CAR_BW=CAR_BW, CAR_BH=CAR_BH, CAR_TOP=CAR_TOP, VIS_SIGN=VIS_SIGN, POOL_SIZE=POOL_SIZE,
                LIGHT=LIGHT, MAXV=128, MAXF=96, POOL_REGIONS=[list(r) for r in POOL_REGIONS]),
    default_car=DEFAULT_CAR,
    car_vertices=[[round(c * 256) for c in p] for p in V],
    car_faces=[[list(idx), mat, 1 if always else 0] for idx, mat, always in _faces],
    pal0=[cram(*c) for c in PAL0], pal1=[cram(*c) for c in PAL1], pal2=[cram(*c) for c in PAL2], pal3=[cram(*c) for c in PAL3],
    otypes=[dict(name=t["name"], pal=t["pal"], height=t["height"], zmin=t["zmin"], zmax=t["zmax"], tiles=t["tiles"],
                 where=t["where"], girl=bool(t.get("girl")),
                 frames=[dict(z=z, tiles=frame_pooled.get(fi, 0), **frame_png(fi, t["pal"])) for fi, z in t["frames"]]) for t in OTYPES],
    girl=frame_png(girl_frames[0], 2),
    sky_png=None,
)
# sky panorama and road-row index maps for the editor's driver's-view preview
sky = Image.new("L", (512, HZ + 1))
for y in range(HZ + 1):
    for x in range(512):
        sky.putpixel((x, y), pbpx[y][x])
buf = io.BytesIO(); sky.save(buf, "PNG"); meta["sky_png"] = base64.b64encode(buf.getvalue()).decode()
with open(os.path.join(OUT, "meta.json"), "w") as f:
    json.dump(meta, f)
# preview images
prev = Image.new("RGB", (PLANE_W, 256))
for y in range(256):
    for x in range(PLANE_W):
        c = PAL0[planeA[y][x]]
        prev.putpixel((x, y), tuple(v * 36 for v in c))
prev.save(os.path.join(OUT, "preview_planeA.png"))
prevb = Image.new("RGB", (PLANE_W, PB_H))
for y in range(PB_H):
    for x in range(PLANE_W):
        prevb.putpixel((x, y), tuple(v * 36 for v in PAL1[pbpx[y][x]]))
prevb.save(os.path.join(OUT, "preview_planeB.png"))
