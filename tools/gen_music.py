#!/usr/bin/env python3
# Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
# Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
"""Composes the original SEACREST RACER theme (150 BPM arcade techno) and emits
patterns + FM patches as a C header for the 68000-side sound driver."""
import os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "build"

# channels: 0 kick(FM1) 1 bass(FM2) 2-3 brass chord(FM3-4) 4 = player engine (FM5, not music)
#           5 lead(FM6) 6 arp(PSG1) 7 unused (PSG2 = rival engine) 8 noise drums(PSG noise)
NCH = 9
KOFF = 0xFF
HAT, OHAT, SNARE = 1, 2, 3

# ---------------- FM patches ----------------
# op order in registers: S1, S3, S2, S4 ; we describe ops as op1..op4 and map.
# each op: (dt, mul, tl, rs, ar, am, d1r, d2r, d1l, rr, ssg)
PATCHES = {
 "kick": dict(alg=7, fb=0, ops=[
    (0, 1, 127, 0, 31, 0, 0, 0, 15, 15, 0),
    (0, 1, 127, 0, 31, 0, 0, 0, 15, 15, 0),
    (0, 1, 127, 0, 31, 0, 0, 0, 15, 15, 0),
    (0, 1, 2, 2, 31, 0, 14, 8, 2, 12, 0)]),
 "bass": dict(alg=0, fb=5, ops=[
    (3, 1, 30, 1, 31, 0, 14, 4, 3, 10, 0),
    (0, 2, 38, 1, 31, 0, 12, 4, 4, 10, 0),
    (0, 1, 26, 1, 31, 0, 10, 2, 3, 10, 0),
    (0, 1, 4, 1, 31, 0, 8, 2, 2, 12, 0)]),
 "brass": dict(alg=4, fb=6, ops=[
    (3, 1, 28, 1, 24, 0, 6, 2, 3, 8, 0),
    (0, 1, 10, 1, 25, 0, 7, 2, 3, 9, 0),
    (7, 2, 34, 1, 24, 0, 6, 2, 3, 8, 0),
    (0, 1, 12, 1, 25, 0, 7, 2, 3, 9, 0)]),
 "engine": dict(alg=0, fb=6, ops=[
    (0, 1, 24, 0, 31, 0, 0, 0, 0, 15, 0),
    (0, 1, 30, 0, 31, 0, 0, 0, 0, 15, 0),
    (3, 2, 36, 0, 31, 0, 0, 0, 0, 15, 0),
    (0, 1, 8, 0, 31, 0, 0, 0, 0, 15, 0)]),
 "lead": dict(alg=4, fb=7, ops=[
    (3, 1, 24, 1, 31, 0, 4, 1, 2, 7, 0),
    (0, 1, 8, 1, 31, 0, 3, 1, 1, 7, 0),
    (5, 3, 40, 1, 31, 0, 5, 1, 3, 7, 0),
    (0, 2, 14, 1, 31, 0, 3, 1, 1, 7, 0)]),
}
CH_PATCH = ["kick", "bass", "brass", "brass", "engine", "lead"]
CH_VOL = [0, 2, 10, 11, 0, 6]     # extra attenuation on carriers

# ---------------- harmony ----------------
CHORDS = {   # (bass root midi, triad midi)
    "Am": (45, (69, 72, 76)), "F": (41, (69, 72, 77)), "G": (43, (71, 74, 79)),
    "Em": (40, (67, 71, 76)), "E": (40, (68, 71, 76)), "C": (48, (67, 72, 76)),
    "Dm": (38, (69, 74, 77)),
}
INTRO = ["Am", "F", "G", "E"]
SEC_A = ["Am", "F", "G", "Em", "Am", "F", "G", "E"]
SEC_B = ["F", "G", "Am", "Am", "F", "G", "E", "E"]
SEC_C = ["Dm", "Am", "F", "E", "Dm", "Am", "F", "E"]   # breakdown-ish bridge

LEAD_B = [  # (step, midi, dur) per bar, original melody
    [(0, 81, 4), (4, 79, 2), (6, 77, 2), (8, 76, 4), (12, 77, 2), (14, 79, 2)],
    [(0, 74, 6), (6, 76, 2), (8, 79, 4), (12, 81, 4)],
    [(0, 84, 6), (6, 83, 2), (8, 81, 4), (12, 76, 4)],
    [(0, 81, 12), (12, 83, 2), (14, 84, 2)],
    [(0, 86, 4), (4, 84, 2), (6, 81, 2), (8, 77, 4), (12, 81, 2), (14, 84, 2)],
    [(0, 83, 6), (6, 79, 2), (8, 74, 4), (12, 79, 2), (14, 83, 2)],
    [(0, 80, 6), (6, 83, 2), (8, 88, 6), (14, 86, 2)],
    [(0, 83, 8), (8, 80, 4), (12, 76, 4)],
]
LEAD_C = [
    [(0, 77, 2), (2, 76, 2), (4, 74, 4), (8, 69, 8)],
    [(0, 72, 2), (2, 74, 2), (4, 76, 4), (8, 72, 4), (12, 69, 4)],
    [(0, 72, 4), (4, 74, 4), (8, 77, 4), (12, 81, 4)],
    [(0, 80, 8), (8, 76, 8)],
    [(0, 77, 2), (2, 79, 2), (4, 81, 4), (8, 86, 8)],
    [(0, 84, 4), (4, 81, 4), (8, 76, 4), (12, 81, 4)],
    [(0, 84, 4), (4, 86, 4), (8, 89, 4), (12, 88, 4)],
    [(0, 88, 12), (12, KOFF, 4)],
]
BASS_RIFF = [0, 0, 12, 0, 0, 12, 0, 7, 0, 0, 12, 0, 0, 12, 7, 12]
STAB_STEPS = {0: 5, 3: 3, 6: 5, 10: 3, 12: 5}      # step -> gate (frames)
STAB_STEPS_B = {0: 10, 6: 4, 10: 4}

def bar(chord, kick=True, bass=True, hats=True, snare=True, stabs=None, arp=False,
        lead=None, ohat=True, fill=False):
    root, triad = CHORDS[chord]
    rows = [[0] * NCH for _ in range(16)]
    gates = [[0] * NCH for _ in range(16)]
    for s in range(16):
        if kick and s % 4 == 0:
            rows[s][0] = 36; gates[s][0] = 5
        if bass:
            rows[s][1] = root + BASS_RIFF[s]; gates[s][1] = 4
        if stabs:
            if s in stabs:
                for v in range(2):
                    rows[s][2 + v] = triad[v + 1]; gates[s][2 + v] = stabs[s]
        if arp:
            seq = [triad[0] + 12, triad[1] + 12, triad[2] + 12, triad[1] + 12]
            rows[s][6] = seq[s % 4]; gates[s][6] = 5
        drum = 0
        if hats:
            drum = OHAT if (ohat and s % 4 == 2) else HAT
        if snare and s in (4, 12):
            drum = SNARE
        if fill and s >= 12:
            drum = SNARE
        rows[s][8] = drum
    if lead:
        for st, n, du in lead:
            rows[st][5] = n
            gates[st][5] = du * 6 - 1 if n != KOFF else 0
    return rows, gates

patterns = []
order = []
def add(rows_gates):
    patterns.append(rows_gates); order.append(len(patterns) - 1)

# intro: drums + bass, arps join
for i, c in enumerate(INTRO):
    add(bar(c, snare=False, ohat=i >= 1, arp=i >= 2, fill=(i == 3)))
loop_start = len(order)
for rep in range(2):
    for i, c in enumerate(SEC_A):
        add(bar(c, stabs=STAB_STEPS, arp=True, fill=(i == 7)))
    for i, c in enumerate(SEC_B):
        add(bar(c, stabs=STAB_STEPS_B, arp=False, lead=LEAD_B[i], fill=(i == 7)))
    if rep == 0:
        for i, c in enumerate(SEC_C):
            add(bar(c, kick=(i >= 4), hats=(i >= 2), snare=(i >= 4), stabs=None if i < 4 else {0: 20},
                    arp=True, lead=LEAD_C[i], fill=(i == 7)))

# ---------------- tables ----------------
def fnum(n):
    f = 440.0 * 2 ** ((n - 69) / 12)
    blk = max(0, min(7, n // 12 - 1))
    fn = round(f * (1 << 20) / (7670453 / 144) / (1 << (blk - 1)) if blk > 0 else f * (1 << 21) / (7670453 / 144))
    while fn > 2047 and blk < 7:
        blk += 1; fn = round(f * (1 << 20) / (7670453 / 144) / (1 << (blk - 1)))
    return (blk << 11) | fn

def psgdiv(n):
    f = 440.0 * 2 ** ((n - 69) / 12)
    return max(1, min(1023, round(3579545 / (32 * f))))

L = ["/* generated by gen_music.py */", "#pragma once",
     "#define M_NCH %d" % NCH, "#define M_NPAT %d" % len(patterns),
     "#define M_NORDER %d" % len(order), "#define M_LOOP %d" % loop_start,
     "#define M_STEP_FRAMES 6"]
L.append("static const u16 m_fnum[128] = {%s};" % ",".join(str(fnum(n)) for n in range(128)))
L.append("static const u16 m_psg[128] = {%s};" % ",".join(str(psgdiv(n)) for n in range(128)))
slot_order = [0, 2, 1, 3]   # register slot index for op1..op4 (S1,S3,S2,S4 -> +0,+4,+8,+12)
carriers = {0: [3], 1: [3], 2: [3], 3: [3], 4: [1, 3], 5: [1, 2, 3], 6: [1, 2, 3], 7: [0, 1, 2, 3]}
pl = []
for ch in range(6):
    p = PATCHES[CH_PATCH[ch]]
    regs = []
    regs.append((0xB0, (p["fb"] << 3) | p["alg"]))
    regs.append((0xB4, 0xC0))
    for oi, op in enumerate(p["ops"]):
        dt, mul, tl, rs, ar, am, d1r, d2r, d1l, rr, ssg = op
        if oi in carriers[p["alg"]]:
            tl = min(127, tl + CH_VOL[ch])
        off = [0, 8, 4, 12][oi]
        regs += [(0x30 + off, (dt << 4) | mul), (0x40 + off, tl), (0x50 + off, (rs << 6) | ar),
                 (0x60 + off, (am << 7) | d1r), (0x70 + off, d2r), (0x80 + off, (d1l << 4) | rr), (0x90 + off, ssg)]
    pl.append(regs)
L.append("#define M_PATCH_REGS %d" % len(pl[0]))
L.append("static const u8 m_patch[6][%d][2] = {%s};" % (len(pl[0]), ",".join(
    "{%s}" % ",".join("{0x%02X,0x%02X}" % r for r in regs) for regs in pl)))
data = []
for rows, gates in patterns:
    for s in range(16):
        for c in range(NCH):
            data.append(rows[s][c]); data.append(min(255, gates[s][c]))
L.append("static const u8 m_pat[%d] = {%s};" % (len(data), ",".join(map(str, data))))
L.append("static const u8 m_order[%d] = {%s};" % (len(order), ",".join(map(str, order))))
with open(os.path.join(OUT, "music.h"), "w") as f:
    f.write("\n".join(L) + "\n")
print("music: %d patterns, %d bars, loop at %d, %.1f s loop" % (len(patterns), len(order), loop_start,
      (len(order) - loop_start) * 16 * 6 / 60))
