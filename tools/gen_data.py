#!/usr/bin/env python3
# Seacrest Racer - Copyright 2026 Fernand Gouveia / PlayableFX.com
# Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
"""Builds the default editable data block (see docs/data_format.md): tracks + car.
The editors read and rewrite exactly this layout inside the ROM."""
import json, os, struct, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "build"
meta = json.load(open(os.path.join(OUT, "meta.json")))

BLOCK_ROM_OFFSET = 0x30000
BLOCK_SIZE = 0x10000
TRACK_OFFS = [0x0100, 0x2100, 0x4100, 0x6100]
CAR_OFF = 0x8100
MAX_OBJ = 128
T_PALM, T_BOAT, T_BILL, T_LAMP, T_CONE, T_STAND, T_ROCK, T_GIRL = range(8)
T_OIL, T_TYRE, T_SHRUB, T_TWALL, T_DRUM, T_UMB = range(8, 14)

def cram(r, g, b):
    return (b << 9) | (g << 5) | (r << 1)

def u32(x):
    return x & 0xFFFFFFFF

# ---------------- track 1: Seacrest Coast (the original course) ----------------
coast_def = [(10, 0), (14, 260), (6, 0), (18, -560), (8, 0), (12, 420), (10, -380), (10, 380),
             (10, 0), (22, -300), (6, 0), (14, 600), (10, 0), (12, -450), (8, 120), (12, 0)]
def expand(defs, nsegs):
    c = []
    for n, k in defs:
        c += [k] * n
    return (c + [0] * nsegs)[:nsegs]

def coast_objects(nsegs):
    L = nsegs * 16                       # units
    objs = []
    seed = 12345
    for i in range(64):                  # same placement the game used to generate
        seed = u32(seed * 1103515245 + 12345)
        p = (i * (L * 256 // 64) + ((seed >> 16) & 0x7FF)) >> 8
        side = 1 if ((seed >> 12) & 3) == 0 else -1
        objs.append((p % L, side * 15 * 256, T_PALM, 1 if side > 0 else 0))
    for i in range(8):
        seed = u32(seed * 1103515245 + 12345)
        p = (i * (L * 256 // 8) + ((seed >> 14) & 0x3FFF)) >> 8
        x = -(28 * 256 + ((seed >> 8) & 0xFFF))
        objs.append((p % L, x, T_BOAT, i & 1))
    objs.append((14, 6 * 256 + 160, T_GIRL, 0))
    for p in (40, 520, 1100, 1900, 2600):
        objs.append((p, 11 * 256, T_BILL, 0))
    for p in (24, 32, 40, 48):
        objs.append((p, -6 * 256 - 100, T_CONE, 0))
        objs.append((p, 6 * 256 + 100, T_CONE, 0))
    return objs

PAL0 = meta["pal0"]
PAL1 = meta["pal1"]

coast = dict(name="SEACREST COAST", nsegs=192, laps=3, fuel=50 * 60, fuel_cp=22 * 60, fuel_lap=30 * 60,
             cp=96, heli=(20, 112), pal0=PAL0, pal1=PAL1, curv=expand(coast_def, 192),
             objs=coast_objects(192))

# ---------------- track 2: Sunset Bay (dusk colours, lamp-lit, grandstand) ----------------
sunset_def = [(8, 0), (10, -420), (6, 0), (16, 520), (6, 0), (8, -650), (8, 650), (10, 0),
              (20, 280), (6, 0), (12, -520), (10, 0), (14, 380), (12, -240), (14, 0)]
p0 = list(PAL0)
for i, c in {1: (1, 1, 3), 2: (1, 1, 4), 3: (6, 4, 3), 4: (5, 3, 2), 5: (1, 3, 1), 6: (1, 2, 1),
             7: (2, 2, 3), 8: (1, 1, 2), 9: (7, 6, 1), 10: (1, 1, 1), 11: (7, 6, 2)}.items():
    p0[i] = cram(*c)
p1 = list(PAL1)
for i, c in {1: (2, 0, 3), 2: (3, 1, 4), 3: (5, 1, 4), 4: (6, 2, 3), 5: (7, 3, 2), 6: (7, 5, 2),
             7: (3, 1, 3), 8: (2, 1, 2), 9: (7, 6, 3), 10: (2, 1, 4), 11: (5, 2, 4), 12: (7, 5, 5),
             13: (1, 2, 1), 14: (3, 1, 1), 15: (2, 4, 1)}.items():
    p1[i] = cram(*c)

def sunset_objects(nsegs):
    L = nsegs * 16
    objs = [(14, -6 * 256 - 160, T_GIRL, 1)]
    objs.append((60, 16 * 256, T_STAND, 0))
    objs.append((150, 16 * 256, T_STAND, 0))
    k = 0
    for p in range(80, L, 56):
        objs.append((p, (8 * 256) if k % 2 else (-8 * 256), T_LAMP, 0 if k % 2 else 1))
        k += 1
    for i, p in enumerate(range(200, L, 170)):
        objs.append((p, -(13 * 256 + (i % 3) * 300), T_ROCK, i & 1))
    for i, p in enumerate(range(90, L, 330)):
        objs.append((p, -(30 * 256 + (i % 4) * 600), T_BOAT, i & 1))
    for p in (30, 38, 46, 54):
        objs.append((p, 6 * 256 + 100, T_CONE, 0))
    return objs

sunset = dict(name="SUNSET BAY", nsegs=160, laps=3, fuel=45 * 60, fuel_cp=20 * 60, fuel_lap=26 * 60,
              cp=80, heli=(30, 0xFFFF), pal0=p0, pal1=p1, curv=expand(sunset_def, 160),
              objs=sunset_objects(160))

TRACKS = [coast, sunset]

# ---------------- car ----------------
p2 = meta["pal2"]
p3 = meta["pal3"]
PARAM_KEYS = ["half_len", "half_width", "ride", "deck", "nose", "top_inset", "cab_rear", "cab_front", "cab_width",
              "roof_h", "roof_width", "roof_rear", "roof_front", "wing_h", "wing_width", "wing_depth", "wheel_h",
              "wheel_len", "wheel_out", "wheel_in", "axle_rear", "axle_front", "shadow_w"]
car = dict(params=meta["default_car"], top=371, accel=128, steer=30, drift=50, brake=5, grip=100, pal2=p2, pal3=p3,
           verts=meta["car_vertices"], faces=meta["car_faces"])

# ---------------- pack ----------------
def pack_track(t):
    b = bytearray(0x2000)
    name = t["name"].upper().encode("ascii")[:16].ljust(16, b" ")
    b[0:16] = name
    struct.pack_into(">HHHHHHHH", b, 0x10, t["nsegs"], t["laps"], t["fuel"], t["fuel_cp"], t["fuel_lap"],
                     t["cp"], t["heli"][0], t["heli"][1])
    struct.pack_into(">16H", b, 0x20, *t["pal0"])
    struct.pack_into(">16H", b, 0x40, *t["pal1"])
    objs = sorted(t["objs"], key=lambda o: o[0])[:MAX_OBJ]
    struct.pack_into(">H", b, 0x60, len(objs))
    for i, (p, x, ty, fl) in enumerate(objs):
        struct.pack_into(">HhBB", b, 0x64 + i * 6, p, x, ty, fl)
    struct.pack_into(">256h", b, 0x400, *(t["curv"] + [0] * (256 - len(t["curv"]))))
    return b

def pack_car(c):
    b = bytearray(0x800)
    struct.pack_into(">HHHHHHHH", b, 0, len(c["verts"]), len(c["faces"]), c["top"], c["accel"], c["steer"],
                     c["drift"], c["brake"], c["grip"])
    struct.pack_into(">16H", b, 0x10, *c["pal2"])
    struct.pack_into(">16H", b, 0x30, *c["pal3"])
    for i, (x, y, z) in enumerate(c["verts"]):
        struct.pack_into(">hhh", b, 0x50 + i * 6, x, y, z)
    for i, (idx, mat, always) in enumerate(c["faces"]):
        struct.pack_into(">BBBBBBH", b, 0x350 + i * 8, *idx, mat, always, 0)
    # shape-slider values the mesh was built from (only the editors read this; the game ignores it)
    b[0x700:0x704] = b"PRM1"
    for i, k in enumerate(PARAM_KEYS):
        struct.pack_into(">h", b, 0x704 + i * 2, round(c["params"][k] * 256))
    return b

def pack_block(tracks, car):
    blk = bytearray(BLOCK_SIZE)
    blk[0:4] = b"SCRD"
    struct.pack_into(">HH4HH", blk, 4, 1, len(tracks), *TRACK_OFFS, CAR_OFF)
    for i, t in enumerate(tracks):
        blk[TRACK_OFFS[i]:TRACK_OFFS[i] + 0x2000] = pack_track(t)
    blk[CAR_OFF:CAR_OFF + 0x800] = pack_car(car)
    return blk

if __name__ == "__main__":
    for t in TRACKS:
        assert len(t["objs"]) <= MAX_OBJ, (t["name"], len(t["objs"]))
        used = {o[2] for o in t["objs"] if o[2] != T_GIRL}
        cost = sum(meta["otypes"][u]["tiles"] for u in used)
        assert cost <= meta["consts"]["POOL_SIZE"], (t["name"], cost)
        print("track %-16s segs %3d objects %3d art pool %d/%d" % (t["name"], t["nsegs"], len(t["objs"]), cost,
                                                                 meta["consts"]["POOL_SIZE"]))
    with open(os.path.join(OUT, "cdata.bin"), "wb") as f:
        f.write(pack_block(TRACKS, car))
