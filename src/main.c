/* Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
 * Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE). */
/* SEACREST RACER - arcade racer demo for Sega Genesis / Mega Drive.
 * Road: per-line scrolled plane (fake 3D). Player car: flat-shaded polygons
 * rasterised by the 68000 into sprite tiles (9 steering angles, rendered at boot).
 * Rivals/palms/helicopter/boats/flag girl: pre-rendered sprite frames. */
#include "md.h"
#include "../build/assets.h"

extern const u8 tiles_bin[], tiles_bin_end[];
extern const u16 mapa_bin[], mapb_bin[];
extern const u8 dial_bin[];
extern const u16 hi_bin[];
extern const u16 title_bin[];
extern const u8 pool_bin[];
extern void irq_enable(void);

/* ---------------- tuning ---------------- */
/* Everything editable lives in a data block at a fixed ROM address (see
 * docs/data_format.md). The track/car editors patch it; no recompiling needed. */
#define DB          ((const u8 *)0x030000)
#define TRK_OFF(i)  (0x0100 + (u16)(i) * 0x2000)
#define CAR_OFF     0x8100
static inline u16 rd16(u32 off) { return (u16)((DB[off] << 8) | DB[off + 1]); }
static inline s16 rds16(u32 off) { return (s16)rd16(off); }
static u16 nsegs = 192;
static s32 track_len = (s32)192 << 12;       /* 8.8 units */
#define TRACK_LEN   track_len
#define SEGS        256
static s16 car_top = 371, car_accel = 128, car_steer = 30, car_drift = 50, car_brake = 5, car_grip = 100;
#define TOPSPEED    car_top
#define XLIMIT      1088           /* 4.25 units */
static s16 n_laps = 3;
#define LAPS        n_laps
#define NRIVALS     3
static s16 fuel_start, fuel_cp, fuel_lap, fuel_cap;
static u16 cp_seg, heli_seg[2];
static u8 cur_track, n_tracks;
static char track_name[17];
#define MAX_OBJ 128
static s32 ob_pos[MAX_OBJ];
static s16 ob_x[MAX_OBJ];
static u8  ob_type[MAX_OBJ], ob_fl[MAX_OBJ];
static u8  nob;
static s32 girl_pos = 14 * 256;
static s16 girl_x = 6 * 256 + 160;
static u8  has_girl;
#define T_GIRL 7
static u16 ftb[sizeof(frames) / sizeof(frames[0])];   /* VRAM tile base per frame (pool frames set per track) */

/* ---------------- shared with interrupts ---------------- */
volatile u16 vcount;
volatile u16 game_frames;
volatile u16 pad, pad_prev;
volatile u16 pad_hit;   /* buttons newly pressed since main last looked */
register u16 *hint_a5 __asm__("a5");
#define HINT_K 47   /* must match FIRST_LINE in crt0.s; 2K+1 = HZ-1 */
static volatile u8 frame_ready;
static volatile u8 ready_idx;

/* double buffered per-frame data */
static u16 hs_buf[2][224 * 2];
static u16 vs_buf[2][232];
static u16 spr_buf[2][80 * 4];
static u8  spr_count[2];
#define CAR_LONGS ((CAR_BW / 8) * (CAR_BH / 8) * 8)
#define NANG 9
static const s8 car_angles[NANG] = { -18, -12, -7, -3, 0, 3, 7, 12, 18 };
static u32 car_cache[NANG][CAR_LONGS];   /* rendered once at boot from the 3D model */
static u32 dial_buf[2][DIAL_W / 8 * DIAL_H / 8 * 8];
static volatile u8 car_show, car_new;
static u8  back;                 /* index being built by main */
static u8  front;                /* index shown */

static u16 whud[3][64];          /* window HUD shadow */
static volatile u8 whud_dirty;

static s16 curv[SEGS];
static s16 xline[DLINES + 1];

/* ---------------- game state ---------------- */
enum { ST_TITLE, ST_COUNT, ST_RACE, ST_FINISH, ST_TIMEUP };
u8 state;
static s16 state_t;
static s32 pos;          /* 8.8 track position of camera */
static s16 speed;        /* 8.8 units/frame */
s16 px;           /* player lateral, 8.8 */
static s16 camx;
static s16 yaw;          /* 8.8 angle units (256 = full turn) */
static u8  drifting;
s16 laps;
static s16 timer;        /* frames */
static u8  cp_done;
static s32 bgscroll;
static u16 frame;
u8  place;
static s16 msg_t;
static const char *msg;
static u8  scrape;
static s16 lat;          /* lateral velocity, 8.8 per frame */
static s16 steer_hold;   /* frames the stick has been held at speed */
static u8  skid;         /* frames of skid effect remaining */
static u8  slip;         /* frames of oil-slick slide remaining */
static s8  slip_dir;
static u8  bump_cd;      /* cooldown after hitting a loose tyre */
#define T_OIL  8
#define T_TYRE 9
static u8  skid_phase;
#define MAX_FUEL fuel_cap
typedef struct { s16 x, y, vx, vy; u8 age, on; } Puff;
#define NPUFF 6
static Puff puffs[NPUFF];
static s16 wheel_lx, wheel_rx;   /* rear wheel screen x, for skid/smoke */
static s32 rv_prevz[3];
/* sound parameters read by the driver in music.c */
extern volatile s16 snd_speed, snd_eng_hz;
extern volatile u8 snd_eng_att, snd_skid, snd_scrape, snd_riv_att;
extern volatile u16 snd_riv_div;

typedef struct { s32 pos; s16 x, speed, target, lane; s16 laps; u8 pal, yellow; } Rival;
static Rival rv[NRIVALS];

typedef struct { s16 x, y, dir, t; u8 on; } Heli;
static Heli heli;
static u8 heli_flags;

/* ---------------- small helpers ---------------- */
static inline s32 mul16(s16 a, s16 b) { return (s32)a * (s32)b; }
/* 32/16 signed divide; caller guarantees the quotient fits in 16 bits */
static inline s16 divs16(s32 a, s16 b) { __asm__("divs.w %1,%0" : "+d"(a) : "d"(b)); return (s16)a; }
static inline u16 divu16(u32 a, u16 b) { __asm__("divu.w %1,%0" : "+d"(a) : "d"(b)); return (u16)a; }
static inline s16 isin(u8 a) { return sintab[a]; }
static inline s16 icos(u8 a) { return sintab[(u8)(a + 64)]; }

static u8 fidx_w[128], fidx_y[128];

static void vdp_init(void) {
    static const u8 regs[24] = {
        0x14, 0x14, VR_PLANE_A >> 10, VR_WINDOW >> 10, VR_PLANE_B >> 13, VR_SPRITES >> 9, 0x00, 0x0F,
        0x00, 0x00, 0x00, 0x03, 0x81, VR_HSCROLL >> 10, 0x00, 0x02,
        0x03, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00 };
    for (u8 i = 0; i < 24; i++) vdp_reg(i, regs[i]);
}

static void vram_fill0(void) {
    VDP_CTRL32 = VRAM_W(0);
    for (u16 i = 0; i < 0x4000; i++) VDP_DATA32 = 0;
}

static void vram_copy(u16 dst, const u16 *src, u16 words) {
    VDP_CTRL32 = VRAM_W(dst);
    for (u16 i = 0; i < words; i++) VDP_DATA = src[i];
}

static void dma_vram(const void *src, u16 dst, u16 words) {
    u32 s = ((u32)src) >> 1;
    vdp_reg(19, words & 0xFF);
    vdp_reg(20, words >> 8);
    vdp_reg(21, s & 0xFF);
    vdp_reg(22, (s >> 8) & 0xFF);
    vdp_reg(23, (s >> 16) & 0x7F);
    u32 cmd = VRAM_W(dst) | 0x80;
    VDP_CTRL = cmd >> 16;
    VDP_CTRL = cmd & 0xFFFF;
}

static u16 read_pad(void) {
    volatile u8 *d = (volatile u8 *)0xA10003;
    *d = 0x40;
    u8 a = *d; a = *d;
    *d = 0x00;
    u8 b = *d; b = *d;
    return (u16)(~((a & 0x3F) | ((b & 0x30) << 2))) & 0xFF;
}

/* ---------------- V-int ---------------- */
void vblank_c(void) {
    if (frame_ready) {
        front = ready_idx;
        frame_ready = 0;
    }
    u8 f = front;
    dma_vram(hs_buf[f], VR_HSCROLL, 224 * 2);
    dma_vram(spr_buf[f], VR_SPRITES, (u16)spr_count[f] * 4);
    if (car_new) { dma_vram(car_cache[car_show], CAR_SLOT * 32, CAR_LONGS * 2); car_new = 0; }
    dma_vram(dial_buf[f], DIAL_SLOT * 32, sizeof(dial_buf[0]) / 2);
    if (whud_dirty) {
        dma_vram(whud, VR_WINDOW, 3 * 64);
        whud_dirty = 0;
    }
    /* road vscroll: sky lines via VSRAM now, road lines from H-int */
    VDP_CTRL32 = VSRAM_W(0);
    VDP_DATA = 0;                     /* plane A (sky) */
    VDP_DATA = vs_buf[f][0];          /* plane B (road): constant above the horizon */
    vdp_reg(10, HINT_K);
    hint_a5 = &vs_buf[f][2 * HINT_K + 2];
    pad_prev = pad;
    pad = read_pad();
    pad_hit |= pad & ~pad_prev;
    vcount++;
    enable_hint_in_isr();
    music_tick();
}

/* ---------------- HUD text ---------------- */
static void hud_text(u8 row, u8 col, const char *s, u8 yellow) {
    while (*s) {
        u8 c = (u8)*s++;
        u16 t = yellow ? (FONT_Y + fidx_y[c & 127]) : (FONT_W + fidx_w[c & 127]);
        whud[row][col++] = 0x8000 | t;
    }
    whud_dirty = 1;
}
static void hud_big(u8 col, u8 digit) {   /* digits 1..4 */
    u16 b = BIGDIG + (digit - 1) * 4;
    whud[1][col] = 0x8000 | b;      whud[2][col] = 0x8000 | (b + 1);
    whud[1][col + 1] = 0x8000 | (b + 2); whud[2][col + 1] = 0x8000 | (b + 3);
    whud_dirty = 1;
}
static void hud_clear(void) {
    for (u8 r = 0; r < 3; r++)
        for (u8 c = 0; c < 64; c++) whud[r][c] = 0x8000 | FONT_W;
    whud_dirty = 1;
}

/* ---------------- loading tracks and the car from the data block ---------------- */
static u16 pool_next[N_POOL_REGIONS];

/* The title logo borrows the rival cars' tiles and palette 3 (rivals are hidden on the title). */
static u8 title_art;
static void title_art_on(void) {
    if (title_art) return;
    u16 sr;
    __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
    vram_copy(RIVAL_T0 * 32, title_bin, TITLE_NT * 16);
    VDP_CTRL32 = CRAM_W(96 + 2);
    for (u8 k = 1; k < 15; k++) VDP_DATA = logo_pal[k];
    __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
    title_art = 1;
}
static void title_art_off(void) {
    if (!title_art) return;
    u16 sr;
    __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
    vram_copy(RIVAL_T0 * 32, (const u16 *)(tiles_bin + RIVAL_T0 * 32), RIVAL_NT * 16);
    VDP_CTRL32 = CRAM_W(96);
    for (u8 k = 0; k < 16; k++) VDP_DATA = rd16(CAR_OFF + 0x30 + k * 2);
    __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
    title_art = 0;
}

static void load_track(u8 i) {
    u32 t = TRK_OFF(i);
    for (u8 k = 0; k < 16; k++) { char c = (char)DB[t + k]; track_name[k] = (c >= ' ' && c < 127) ? c : ' '; }
    track_name[16] = 0;
    for (s8 k = 15; k >= 0 && track_name[k] == ' '; k--) track_name[k] = 0;
    nsegs = rd16(t + 0x10);
    if (nsegs < 32) nsegs = 32;
    if (nsegs > 256) nsegs = 256;
    track_len = (s32)nsegs << 12;
    n_laps = rds16(t + 0x12); if (n_laps < 1) n_laps = 1; if (n_laps > 9) n_laps = 9;
    fuel_start = rds16(t + 0x14); fuel_cp = rds16(t + 0x16); fuel_lap = rds16(t + 0x18);
    if (fuel_start < 600) fuel_start = 600;
    fuel_cap = fuel_start > 3600 ? fuel_start : 3600;
    cp_seg = rd16(t + 0x1A); if (cp_seg >= nsegs) cp_seg = nsegs / 2;
    heli_seg[0] = rd16(t + 0x1C); heli_seg[1] = rd16(t + 0x1E);
    for (u16 k = 0; k < 256; k++) curv[k] = k < nsegs ? rds16(t + 0x400 + k * 2) : 0;
    /* objects */
    u16 n = rd16(t + 0x60); if (n > MAX_OBJ) n = MAX_OBJ;
    nob = 0; has_girl = 0;
    u16 used = 0;
    for (u16 k = 0; k < n; k++) {
        u32 o = t + 0x64 + k * 6;
        u16 p = rd16(o);
        s16 x = rds16(o + 2);
        u8 ty = DB[o + 4], fl = DB[o + 5];
        if ((s32)p * 256 >= track_len) continue;
        if (ty == T_GIRL) { has_girl = 1; girl_pos = (s32)p << 8; girl_x = x; continue; }
        if (ty >= N_OTYPES) continue;
        ob_pos[nob] = (s32)p << 8; ob_x[nob] = x; ob_type[nob] = ty; ob_fl[nob] = fl; nob++;
        used |= (u16)1 << ty;
    }
    /* palettes + roadside art pool: written with interrupts masked (VDP is shared with H-int) */
    u16 sr;
    __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
    VDP_CTRL32 = CRAM_W(0);
    for (u8 k = 0; k < 16; k++) VDP_DATA = rd16(t + 0x20 + k * 2);
    for (u8 k = 0; k < 16; k++) VDP_DATA = rd16(t + 0x40 + k * 2);
    for (u8 r = 0; r < N_POOL_REGIONS; r++) pool_next[r] = pool_regions[r][0];
    for (u8 ty = 0; ty < N_OTYPES; ty++) {
        const OType *ot = &otypes[ty];
        for (u8 f = 0; f < ot->n; f++) {
            u16 fi = ot->first + f;
            ftb[fi] = 0;                               /* not loaded */
            if (!(used & (1 << ty))) continue;
            u16 nt = frames[fi].pooled_tiles;
            for (u8 r = 0; r < N_POOL_REGIONS; r++) {
                if (pool_next[r] + nt <= pool_regions[r][1]) {
                    ftb[fi] = pool_next[r];
                    vram_copy(pool_next[r] * 32, (const u16 *)(pool_bin + frames[fi].tbase * 32), nt * 16);
                    pool_next[r] += nt;
                    break;
                }
            }
        }
    }
    __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
}

/* car model (from the data block) */
static s16 mv[MAXV][3];
static u8  mfv[MAXF][4], mfmat[MAXF], mfcull[MAXF];
static s8  mfn[MAXF][3];
static u16 nvert, nface;

static u16 isqrt32(u32 x) {
    u32 r = 0, bit = 1UL << 30;
    while (bit > x) bit >>= 2;
    while (bit) {
        if (x >= r + bit) { x -= r + bit; r = (r >> 1) + bit; } else r >>= 1;
        bit >>= 2;
    }
    return (u16)r;
}

static void load_car(void) {
    u32 c = CAR_OFF;
    nvert = rd16(c); nface = rd16(c + 2);
    if (nvert > MAXV) nvert = MAXV;
    if (nface > MAXF) nface = MAXF;
    car_top = rds16(c + 4); car_accel = rds16(c + 6); car_steer = rds16(c + 8);
    car_drift = rds16(c + 10); car_brake = rds16(c + 12); car_grip = rds16(c + 14);
    if (car_top < 100) car_top = 100;
    if (car_top > 600) car_top = 600;
    if (car_accel < 16) car_accel = 16;
    if (car_grip < 20) car_grip = 20;
    for (u16 i = 0; i < nvert; i++)
        for (u8 k = 0; k < 3; k++) mv[i][k] = rds16(c + 0x50 + i * 6 + k * 2);
    for (u16 f = 0; f < nface; f++) {
        u32 o = c + 0x350 + f * 8;
        for (u8 k = 0; k < 4; k++) { u8 vi = DB[o + k]; mfv[f][k] = vi < nvert ? vi : 0; }
        mfmat[f] = DB[o + 4] > 5 ? 1 : DB[o + 4];
        mfcull[f] = (DB[o + 5] & 1) ? 0 : 1;
        /* normal from the quad's diagonals, normalised to length 64 */
        const s16 *p0 = mv[mfv[f][0]], *p1 = mv[mfv[f][1]], *p2 = mv[mfv[f][2]], *p3 = mv[mfv[f][3]];
        s32 ux = (p2[0] - p0[0]) >> 2, uy = (p2[1] - p0[1]) >> 2, uz = (p2[2] - p0[2]) >> 2;
        s32 wx = (p3[0] - p1[0]) >> 2, wy = (p3[1] - p1[1]) >> 2, wz = (p3[2] - p1[2]) >> 2;
        s32 nx = (uy * wz - uz * wy) >> 4, ny = (uz * wx - ux * wz) >> 4, nz = (ux * wy - uy * wx) >> 4;
        u16 l = isqrt32((u32)(nx * nx + ny * ny + nz * nz));
        if (l == 0) l = 1;
        mfn[f][0] = (s8)(nx * 64 / l); mfn[f][1] = (s8)(ny * 64 / l); mfn[f][2] = (s8)(nz * 64 / l);
    }
    VDP_CTRL32 = CRAM_W(64);
    for (u8 k = 0; k < 16; k++) VDP_DATA = rd16(c + 0x10 + k * 2);
    for (u8 k = 0; k < 16; k++) VDP_DATA = rd16(c + 0x30 + k * 2);
}

static inline s16 seg_curve(s32 p) {
    while (p >= TRACK_LEN) p -= TRACK_LEN;
    while (p < 0) p += TRACK_LEN;
    return curv[p >> 12];
}

/* ---------------- road tables ---------------- */
static void build_road(u16 *hs, u16 *vs) {
    s32 dx = 0, x = 0;
    s16 sky = (s16)(-(bgscroll >> 8));
    for (u16 y = 0; y <= HZ; y++) {
        hs[y * 2] = sky;
        hs[y * 2 + 1] = 0;
        vs[y] = (u16)(ROW_T - y);
    }
    vs[0] = 0;   /* above the horizon plane B is hidden behind sky/HUD */
    for (s16 d = DLINES; d >= 1; d--) {
        s32 z = zline[d];
        s32 tp = pos + z;
        if (tp >= TRACK_LEN) tp -= TRACK_LEN;
        s16 c = curv[tp >> 12];
        s16 dzz = dz16[d];
        dx += mul16(c, dzz) >> 4;
        x += mul16((s16)(dx >> 6), dzz) >> 6;
        xline[d] = (s16)x;
        s32 rel = x - camx;
        if (rel > 32767) rel = 32767;
        if (rel < -32767) rel = -32767;
        s16 pxl = (s16)(mul16((s16)rel, (s16)kline[d]) >> 16);
        u16 y = HZ + d;
        hs[y * 2] = sky;
        hs[y * 2 + 1] = (u16)(160 - 512 + pxl);
        u16 row = (tp >> 10) & 1 ? (u16)(127 + d) : (u16)(d - 1);
        vs[y] = (u16)(row - y);
    }
    vs[224] = vs[225] = vs[226] = vs[223];
}

/* ---------------- sprites ---------------- */
static u16 *spr;
static u8 nspr;

static void spr_add(s16 x, s16 y, u8 size, u16 attr) {
    if (nspr >= 80) return;
    if (x <= -32 || x >= 320 || y <= -32 || y >= 224) return;
    u16 *e = spr + nspr * 4;
    e[0] = (u16)(y + 128);
    e[1] = ((u16)size << 8);
    e[2] = attr;
    u16 hx = (u16)(x + 128);
    if (hx == 0) hx = 1;
    e[3] = hx;
    nspr++;
}

static void spr_frame(u8 fi, s16 sx, s16 sy, u16 pal, u8 hflip) {
    const Frame *fr = &frames[fi];
    for (u16 i = 0; i < fr->count; i++) {
        const Chunk *c = &chunks[fr->first + i];
        s16 w = (((c->size >> 2) & 3) + 1) * 8;
        s16 x = hflip ? (s16)(sx - c->dx - w) : (s16)(sx + c->dx);
        spr_add(x, sy + c->dy, c->size, (pal << 13) | (hflip ? 0x0800 : 0) | (ftb[fi] + c->toff));
    }
}

static void spr_finish(void) {
    if (nspr == 0) {
        spr[0] = 0; spr[1] = 0; spr[2] = 0; spr[3] = 0;
        nspr = 1;
    }
    for (u8 i = 0; i < nspr; i++)
        spr[i * 4 + 1] = (spr[i * 4 + 1] & 0xFF00) | (i + 1 < nspr ? i + 1 : 0);
}

/* objects for depth sorting */
typedef struct { s32 z; u8 kind, idx; } Obj;
#define MAXOBJS 30
static Obj objs[MAXOBJS + 2];
static u8 nobj;

/* project ground point at relative depth relz (8.8), lateral wx (8.8) */
static u8 project(s32 relz, s16 wx, s16 *sx, s16 *sy) {
    if (relz < zline[DLINES] || relz > zline[3] || relz > 65535) return 0;
    s16 d = (s16)divu16((u32)528 << 8, (u16)relz);
    if (d < 1) d = 1;
    if (d > DLINES) d = DLINES;
    s32 rel = (s32)xline[d] + wx - camx;
    if (rel > 32767) rel = 32767;
    if (rel < -32767) rel = -32767;
    *sx = 160 + (s16)(mul16((s16)rel, (s16)kline[d]) >> 16);
    *sy = HZ + d;
    return 1;
}

static s32 wrap_rel(s32 p) {
    s32 r = p - pos;
    while (r > TRACK_LEN / 2) r -= TRACK_LEN;
    while (r < -TRACK_LEN / 2) r += TRACK_LEN;
    return r;
}

/* ---------------- player car rasteriser ---------------- */
/* The car buffer is 120x64 pixels laid out as sprite tiles: two 15x4-cell bands
 * (rows 0-31 and 32-63), each column-major so every 32-pixel column is one sprite. */
static u32 *cbuf;
static s16 sv_x[MAXV], sv_y[MAXV];   /* screen coords, 4 fractional bits */
static s16 edge_l[CAR_BH], edge_r[CAR_BH];
static u16 rowofs[CAR_BH];             /* long offset of pixel row y in its first cell */
static u16 colofs[CAR_BW / 8];         /* long offset of cell column c (both bands) */
static s16 car_ox[NANG];               /* buffer x where the model origin landed, per pose */
static const u32 lmask[8] = { 0xFFFFFFFF, 0x0FFFFFFF, 0x00FFFFFF, 0x000FFFFF, 0x0000FFFF, 0x00000FFF, 0x000000FF, 0x0000000F };
static const u32 rmask[8] = { 0xF0000000, 0xFF000000, 0xFFF00000, 0xFFFF0000, 0xFFFFF000, 0xFFFFFF00, 0xFFFFFFF0, 0xFFFFFFFF };
static const u32 colpat[16] = {
    0x00000000, 0x11111111, 0x22222222, 0x33333333, 0x44444444, 0x55555555, 0x66666666, 0x77777777,
    0x88888888, 0x99999999, 0xAAAAAAAA, 0xBBBBBBBB, 0xCCCCCCCC, 0xDDDDDDDD, 0xEEEEEEEE, 0xFFFFFFFF };

static void raster_init(void) {
    for (u16 y = 0; y < CAR_BH; y++)
        rowofs[y] = y < 32 ? (u16)((y >> 3) * 8 + (y & 7)) : (u16)((CAR_BW / 8) * 4 * 8 + ((y - 32) >> 3) * 8 + (y & 7));
    for (u16 c = 0; c < CAR_BW / 8; c++) colofs[c] = c * 32;
}

static void fill_rows(s16 r0, s16 r1, u32 pat) {
    for (s16 y = r0; y <= r1; y++) {
        s16 x0 = edge_l[y], x1 = edge_r[y];
        if (x0 < 0) x0 = 0;
        if (x1 > CAR_BW - 1) x1 = CAR_BW - 1;
        if (x0 > x1) continue;
        u32 *row = cbuf + rowofs[y];
        const u16 *co = colofs;
        s16 c0 = x0 >> 3, c1 = x1 >> 3;
        u32 lm = lmask[x0 & 7], rm = rmask[x1 & 7];
        u32 *p = row + co[c0];
        if (c0 == c1) {
            u32 m = lm & rm;
            *p = (*p & ~m) | (pat & m);
            continue;
        }
        *p = (*p & ~lm) | (pat & lm);
        for (s16 c = c0 + 1; c < c1; c++) row[co[c]] = pat;
        p = row + co[c1];
        *p = (*p & ~rm) | (pat & rm);
    }
}

static void edge(s16 xa, s16 ya, s16 xb, s16 yb) {
    /* coords with 4 fractional bits; records x for pixel rows whose top lies in [ya, yb) */
    if (ya > yb) { s16 t = ya; ya = yb; yb = t; t = xa; xa = xb; xb = t; }
    s16 y0 = (ya + 15) >> 4, y1 = (yb - 1) >> 4;
    if (y1 < 0 || y0 >= CAR_BH || y0 > y1) return;
    s16 dy = yb - ya, dx = xb - xa;
    /* slope in pixels per row, 8.8 fixed (clamped: near-horizontal edges cover <= 1 row) */
    s16 adx = dx < 0 ? -dx : dx;
    s16 slope = (adx >= dy * 120) ? (dx < 0 ? -30720 : 30720) : divs16((s32)dx << 8, dy);
    s32 xx = ((s32)xa << 12) + mul16(slope, (s16)((y0 << 4) - ya)) * 16;   /* 16.16 pixels */
    s32 step = (s32)slope << 8;
    if (y0 < 0) { xx += step * (-y0); y0 = 0; }
    if (y1 >= CAR_BH) y1 = CAR_BH - 1;
    s16 *el = edge_l + y0, *er = edge_r + y0;
    for (s16 y = y0; y <= y1; y++) {
        s16 xi = (s16)(xx >> 16);
        if (xi < *el) *el = xi;
        if (xi > *er) *er = xi;
        el++; er++;
        xx += step;
    }
}

static s16 rc_cs, rc_sn;

static void car_face(u16 f) {
    const u8 *v = mfv[f];
    const s8 *nrm = mfn[f];
    s16 cs = rc_cs, sn = rc_sn;
    s16 x0 = sv_x[v[0]], y0 = sv_y[v[0]], x1 = sv_x[v[1]], y1 = sv_y[v[1]];
    s16 x2 = sv_x[v[2]], y2 = sv_y[v[2]], x3 = sv_x[v[3]], y3 = sv_y[v[3]];
    if (mfcull[f]) {
        s32 ar = mul16((x2 - x0) >> 2, (y3 - y1) >> 2) - mul16((x3 - x1) >> 2, (y2 - y0) >> 2);
        if (VIS_SIGN > 0 ? ar <= 0 : ar >= 0) return;
    }
    u8 col;
    switch (mfmat[f]) {
    case 0: col = 8; break;
    case 3: col = 8; break;
    case 4: col = 9; break;
    case 5: col = 10; break;
    default: {
        s16 nx = (s16)((mul16(nrm[0], cs) + mul16(nrm[2], sn)) >> 14);
        s16 nz = (s16)((mul16(nrm[2], cs) - mul16(nrm[0], sn)) >> 14);
        s16 dt = (s16)(mul16(nx, light[0]) + mul16(nrm[1], light[1]) + mul16(nz, light[2]));
        if (mfmat[f] == 2) col = 5 + (dt < 614 ? 0 : (dt < 2253 ? 1 : 2));
        else col = 1 + (dt < 410 ? 0 : (dt < 1638 ? 1 : (dt < 2867 ? 2 : 3)));
    } }
    s16 ymin = y0, ymax = y0;
    if (y1 < ymin) ymin = y1;
    if (y1 > ymax) ymax = y1;
    if (y2 < ymin) ymin = y2;
    if (y2 > ymax) ymax = y2;
    if (y3 < ymin) ymin = y3;
    if (y3 > ymax) ymax = y3;
    s16 r0 = (ymin + 15) >> 4, r1 = (ymax - 1) >> 4;
    if (r0 < 0) r0 = 0;
    if (r1 >= CAR_BH) r1 = CAR_BH - 1;
    if (r0 > r1) return;
    for (s16 y = r0; y <= r1; y++) { edge_l[y] = 32767; edge_r[y] = -32768; }
    edge(x0, y0, x1, y1);
    edge(x1, y1, x2, y2);
    edge(x2, y2, x3, y3);
    edge(x3, y3, x0, y0);
    fill_rows(r0, r1, colpat[col]);
}

/* Render the player car from its polygon model at one yaw angle into buf. */
static void render_car_angle(u32 *buf, u8 ai) {
    s16 yq = car_angles[ai];
    cbuf = buf;
    for (u16 i = 0; i < CAR_LONGS; i++) buf[i] = 0;
    rc_cs = icos((u8)yq); rc_sn = isin((u8)yq);
    const s16 oy = (HZ - CAR_TOP) * 16;
    s16 xmin = 32767, xmax = -32768;
    for (u16 i = 0; i < nvert; i++) {
        s16 mx = mv[i][0], my = mv[i][1], mz = mv[i][2];
        s16 X = (s16)((mul16(mx, rc_cs) + mul16(mz, rc_sn)) >> 14);
        s16 Z = (s16)((mul16(mz, rc_cs) - mul16(mx, rc_sn)) >> 14);
        s16 Zw = Z + FIX_ZCAR;
        sv_x[i] = divs16(mul16(X, 220) << 4, Zw);
        sv_y[i] = oy + divs16(mul16((s16)(FIX_CAMH - my), 220) << 4, Zw);
        if (sv_x[i] < xmin) xmin = sv_x[i];
        if (sv_x[i] > xmax) xmax = sv_x[i];
    }
    /* centre this pose in the box; the sprite is shifted back on screen by the same amount */
    s16 ox = ((CAR_BW / 2) << 4) - ((xmin + xmax) >> 1);
    ox &= ~15;
    for (u16 i = 0; i < nvert; i++) sv_x[i] += ox;
    car_ox[ai] = ox >> 4;
    for (u16 f = 0; f < nface; f++) car_face(f);
}

/* pick the cached angle nearest the current visual yaw; upload only on change */
static void select_car_angle(void) {
    s16 yq = yaw >> 8;
    u8 best = 4; s16 bd = 999;
    for (u8 i = 0; i < NANG; i++) {
        s16 dd = yq - car_angles[i]; if (dd < 0) dd = -dd;
        if (dd < bd) { bd = dd; best = i; }
    }
    if (best != car_show) { car_show = best; car_new = 1; }
}

/* ---------------- analog speedometer ---------------- */
static void dial_pixel(u8 *t, s16 x, s16 y, u8 c) {
    if (x < 0 || x >= DIAL_W || y < 0 || y >= DIAL_H) return;
    u8 *p = t + (((x >> 3) * (DIAL_H / 8) + (y >> 3)) << 5) + ((y & 7) << 2) + ((x & 7) >> 1);
    if (x & 1) *p = (*p & 0xF0) | c; else *p = (*p & 0x0F) | (c << 4);
}

static void build_dial(u32 *d) {
    const u32 *tpl = (const u32 *)dial_bin;
    for (u16 i = 0; i < DIAL_W / 8 * DIAL_H / 8 * 8; i++) d[i] = tpl[i];
    /* needle: 0 km/h points left (angle 128), top speed +10% points right (256) */
    s16 a = 128 + (s16)(((s32)speed * 128) / (TOPSPEED + TOPSPEED / 10));
    if (a > 255) a = 255;
    s16 cs = icos((u8)a), sn = isin((u8)a);
    u8 *t = (u8 *)d;
    for (s16 r = 2; r < DIAL_R - 3; r++) {
        s16 x = DIAL_CX + (s16)(mul16(cs, r) >> 14);
        s16 y = DIAL_CY + (s16)(mul16(sn, r) >> 14);
        dial_pixel(t, x, y, 13);
        dial_pixel(t, x + 1, y, 13);
        if (r < 6) dial_pixel(t, x, y - 1, 13);
    }
    for (s16 yy = -1; yy <= 0; yy++)
        for (s16 xx = -1; xx <= 1; xx++) dial_pixel(t, DIAL_CX + xx, DIAL_CY + yy, 12);
}

/* ---------------- rivals ---------------- */
static void reset_race(void) {
    pos = 0; speed = 0; px = -2 * 256 + 128; camx = px; yaw = 0; drifting = 0;
    laps = 0; timer = fuel_start; cp_done = 0; heli_flags = 0; heli.on = 0;
    lat = 0; steer_hold = 0; skid = 0; slip = 0; bump_cd = 0;
    for (u8 i = 0; i < NPUFF; i++) puffs[i].on = 0;
    static const s16 lanes[NRIVALS] = { 2 * 256 + 128, -2 * 256 - 128, 2 * 256 + 128 };
    s16 targets[NRIVALS] = { TOPSPEED * 82 / 100, TOPSPEED * 88 / 100, TOPSPEED * 93 / 100 };
    for (u8 i = 0; i < NRIVALS; i++) {
        rv[i].pos = ((s32)(i + 1) * 9 << 8) + FIX_ZCAR;
        rv[i].lane = rv[i].x = lanes[i];
        rv[i].speed = 0;
        rv[i].target = targets[i];
        rv[i].laps = 0;
        rv[i].yellow = (i != 1);
        rv[i].pal = 3;
    }
}

static void update_rivals(u8 dt) {
    for (u8 i = 0; i < NRIVALS; i++) {
        Rival *r = &rv[i];
        /* arcade catch-up: rivals far behind speed up, rivals far ahead ease off */
        s32 gap = ((s32)(r->laps - laps) * (TRACK_LEN >> 8)) + ((r->pos - FIX_ZCAR - pos) >> 8);
        s16 tgt = r->target;
        if (gap < -60) tgt = TOPSPEED * 110 / 100;
        else if (gap < -20) tgt = TOPSPEED * 104 / 100;
        else if (gap > 90) tgt = r->target - 30;
        for (u8 k = 0; k < dt; k++) {
            if (state == ST_RACE || state == ST_FINISH || state == ST_TIMEUP || state == ST_TITLE) {
                if (r->speed < tgt) r->speed += 2;
                if (r->speed > tgt) r->speed -= 1;
            }
            r->pos += r->speed;
            if (r->pos >= TRACK_LEN) { r->pos -= TRACK_LEN; r->laps++; }
        }
        /* lane keeping with a gentle weave, dodge the player if right behind */
        s32 rel = wrap_rel(r->pos) - FIX_ZCAR;
        s16 goal = r->lane + (isin((u8)(frame + i * 80)) >> 7);
        if (rel > 0 && rel < 12 * 256 && (r->x - px) < 400 && (px - r->x) < 400)
            goal = (px > 0) ? -2 * 256 : 2 * 256;
        if (r->x < goal) r->x += 6 * dt; else if (r->x > goal) r->x -= 6 * dt;
        /* collisions with the player */
        if (rel > -3 * 256 - 200 && rel < 3 * 256 + 200) {
            s16 dxl = r->x - px;
            if (dxl > -450 && dxl < 450) {
                if (rel > 0) { if (speed > r->speed - 10) speed = r->speed - 30; }
                else { if (r->speed > speed - 10) r->speed = speed - 30; }
                if (speed < 0) speed = 0;
                if (dxl > 0) { r->x += 24; px -= 24; } else { r->x -= 24; px += 24; }
                sfx_noise(1);
            }
        }
    }
}

/* ---------------- player ---------------- */
static void spawn_puff(s16 x, s16 y) {
    for (u8 i = 0; i < NPUFF; i++) if (!puffs[i].on) {
        Puff *p = &puffs[i];
        p->on = 1; p->age = 0;
        p->x = x << 4; p->y = y << 4;
        p->vx = (x < 160 ? -6 : 6) + ((frame * 13) & 7) - 3;
        p->vy = 10 + (frame & 3);
        return;
    }
}

static void update_player(u8 dt) {
    u16 p = pad;
    s8 steer = 0;
    u8 gas = 0, brake = 0;
    if (state == ST_RACE) {
        if (p & PAD_LEFT) steer = -1;
        if (p & PAD_RIGHT) steer = 1;
        gas = (p & (PAD_A | PAD_C)) != 0;
        brake = (p & PAD_B) != 0;
    } else if (state == ST_TITLE) {
        /* attract mode: simple autopilot */
        s16 c = seg_curve(pos + 20 * 256);
        s16 goal = (s16)(-c * 2);
        if (px < goal - 64) steer = 1; else if (px > goal + 64) steer = -1;
        gas = speed < TOPSPEED * 3 / 4;
    } else if (state == ST_COUNT) {
        gas = (p & (PAD_A | PAD_C)) != 0;     /* rev the engine on the grid */
    }
    s16 speed_before = speed;
    /* hazards placed on the road: oil slicks make the car fishtail, a loose tyre costs speed */
    if (state == ST_RACE && speed > 40) {
        for (u8 i = 0; i < nob; i++) {
            u8 ty = ob_type[i];
            if (ty != T_OIL && ty != T_TYRE) continue;
            if (!ftb[otypes[ty].first]) continue;                 /* art didn't fit: no invisible hazards */
            s32 r = wrap_rel(ob_pos[i]) - FIX_ZCAR;
            if (r < -2 * 256 || r > 2 * 256) continue;
            s16 dxo = ob_x[i] - (s16)px; if (dxo < 0) dxo = -dxo;
            if (ty == T_OIL && dxo < 2 * 256 + 64 && !slip) { slip = 48; slip_dir = (frame & 2) ? 1 : -1; }
            if (ty == T_TYRE && dxo < 300 && !bump_cd) { speed -= speed >> 3; bump_cd = 40; scrape = 8; }
        }
    }
    if (bump_cd) bump_cd = bump_cd > dt ? bump_cd - dt : 0;
    if (slip) {
        u8 before = slip;
        slip = slip > dt ? slip - dt : 0;
        if ((before & ~15) != (slip & ~15)) slip_dir = -slip_dir;    /* fishtail */
    }
    drifting = brake && steer && speed > TOPSPEED / 2;
    if (steer && speed > TOPSPEED * 7 / 10) steer_hold += dt; else steer_hold = 0;
    for (u8 k = 0; k < dt; k++) {
        if (state == ST_COUNT) speed = 0;
        else if (state == ST_FINISH || state == ST_TIMEUP) { speed -= speed >> 6; if (speed < 4) speed = 0; }
        else if (drifting) speed -= 1;
        else if (brake) speed -= car_brake;
        else if (gas) speed += divs16((s32)(TOPSPEED - speed), car_accel) + 1;
        else speed -= (speed >> 8) + 1;
        if (speed < 0) speed = 0;
        if (speed > TOPSPEED) speed = TOPSPEED;
        /* steering: lateral velocity eases quickly toward a speed-dependent target */
        s16 rate = speed > 16 ? 12 + (s16)(mul16(speed, car_steer) >> 8) : 0;  /* ~0.2 units/frame at top */
        if (drifting) rate += divs16(mul16(rate, car_drift), 100);
        s16 want = steer * rate;
        if (slip) { want = (want >> 2) + slip_dir * rate; speed -= speed >> 8; }
        if (lat < want) { lat += 14; if (lat > want) lat = want; }
        else if (lat > want) { lat -= 14; if (lat < want) lat = want; }
        s16 c = seg_curve(pos + FIX_ZCAR);
        s16 cent = (s16)((mul16((s16)((mul16(c, speed)) >> 8), speed)) >> 15);
        if (drifting) cent += cent >> 1;
        cent = divs16(mul16(cent, 100), car_grip);
        px += lat - cent;
        if (px > XLIMIT) { px = XLIMIT; speed -= speed >> 6; scrape = 4; lat = 0; }
        if (px < -XLIMIT) { px = -XLIMIT; speed -= speed >> 6; scrape = 4; lat = 0; }
        pos += speed;
        if (pos >= TRACK_LEN) {
            pos -= TRACK_LEN;
            if (state == ST_RACE) {
                laps++; cp_done = 0; heli_flags = 0;
                if (laps >= LAPS) { state = ST_FINISH; state_t = 0; msg = "FINISH!"; msg_t = 300; }
                else { timer += fuel_lap; msg = laps == LAPS - 1 ? "FINAL LAP" : "REFUEL!"; msg_t = 120; }
                if (timer > MAX_FUEL) timer = MAX_FUEL;
            } else heli_flags = 0;
        }
        if (state == ST_RACE && !cp_done && (pos >> 12) >= cp_seg) {
            cp_done = 1; timer += fuel_cp; if (timer > MAX_FUEL) timer = MAX_FUEL;
            msg = "CHECKPOINT"; msg_t = 120;
        }
    }
    if (scrape) scrape--;
    /* visual yaw follows the stick almost immediately */
    s16 target = slip ? slip_dir * 18 * 256 : drifting ? steer * 18 * 256 : (steer_hold > 20 ? steer * 12 * 256 : steer * 7 * 256);
    yaw += (target - yaw) >> 1;
    camx += (px - camx) >> 1;
    bgscroll += (s32)seg_curve(pos + 40 * 256) * speed >> 9;

    /* skid marks and smoke: drift, long hard cornering, hard braking, wheelspin launch */
    u8 hard = drifting || steer_hold > 36 || (brake && speed_before > TOPSPEED / 2)
              || (gas && state == ST_RACE && speed < TOPSPEED / 4);
    if (hard || slip) skid = 8;
    (void)0;
    if (skid) {
        skid = skid > dt ? skid - dt : 0;
        skid_phase ^= 1;
        if ((frame & 3) < dt) spawn_puff((frame & 4) ? wheel_lx : wheel_rx, 194);
    }
    for (u8 i = 0; i < NPUFF; i++) {
        Puff *q = &puffs[i];
        if (!q->on) continue;
        q->age += dt;
        q->x += q->vx * dt; q->y += q->vy * dt;
        if (q->age > 14 || q->y > (230 << 4)) q->on = 0;
    }
}

/* ---------------- helicopter ---------------- */
static void update_heli(u8 dt) {
    u16 seg = pos >> 12;
    if (!(heli_flags & 1) && seg >= heli_seg[0] && seg < heli_seg[0] + 4) {
        heli_flags |= 1; heli.on = 1; heli.dir = -1; heli.x = 360 << 4; heli.t = 0;
    }
    if (!(heli_flags & 2) && seg >= heli_seg[1] && seg < heli_seg[1] + 4) {
        heli_flags |= 2; heli.on = 1; heli.dir = 1; heli.x = -60 * 16; heli.t = 0;
    }
    if (!heli.on) return;
    heli.t += dt;
    heli.x += heli.dir * 26 * dt;
    heli.x -= (s16)(((s32)seg_curve(pos + 40 * 256) * speed >> 9) >> 4) * dt;
    heli.y = 44 + (isin((u8)(heli.t * 3)) >> 12) - (heli.t > 200 ? (heli.t - 200) >> 3 : 0);
    if (heli.x < (-100 * 16) || heli.x > (420 << 4)) heli.on = 0;
}

/* ---------------- sound parameters (engine, rival Doppler) ---------------- */
static void update_sound(u8 dt) {
    /* player engine: rpm climbs through 5 gears, with a dip at each shift */
    static const s16 gear_top[6] = { 0, 95, 175, 250, 315, 400 };
    s16 sp = speed;
    u8 g = 1; while (g < 5 && sp > gear_top[g]) g++;
    s16 lo = gear_top[g - 1], hi = gear_top[g];
    s16 frac = (s16)(((s32)(sp - lo) * 256) / (hi - lo));       /* 0..256 */
    s16 hz = 46 + (s16)((mul16(frac, 74)) >> 8) + g * 4;
    u8 gas = (pad & (PAD_A | PAD_C)) != 0;
    if (state == ST_COUNT && gas) hz = 60 + ((frame * 7) & 31) + 50;   /* revving on the grid */
    if (sp < 8 && !(state == ST_COUNT && gas)) hz = 42 + ((frame >> 1) & 1) * 2;
    snd_eng_hz = hz;
    u8 att = (state == ST_RACE || state == ST_COUNT) ? (gas ? 0 : 2) : 4;
    if (state == ST_FINISH || state == ST_TIMEUP) att = speed > 20 ? 3 : 6;
    snd_eng_att = att;
    snd_speed = speed;
    snd_skid = skid != 0 && speed > 40;
    snd_scrape = scrape != 0;

    /* nearest rival: volume by distance, pitch by Doppler (exaggerated arcade-style) */
    s32 bestd = 0x7FFFFFFF; s16 vc = 0; u8 bi = 0xFF;
    for (u8 i = 0; i < NRIVALS; i++) {
        s32 r = wrap_rel(rv[i].pos);
        s32 closing = (rv_prevz[i] - r) / (dt ? dt : 1);    /* + when approaching the camera */
        rv_prevz[i] = r;
        s32 ad = r < 0 ? -r : r;
        if (ad < bestd) { bestd = ad; bi = i; vc = (s16)(closing > 200 ? 200 : (closing < -200 ? -200 : closing)); }
    }
    if (bi != 0xFF && bestd < 48 * 256) {
        s32 fsrc = 120 + (rv[bi].speed >> 2);                       /* ~120-215 Hz */
        s32 fobs = (fsrc * 1220) / (1220 - (s32)vc * 4);            /* c = 1220 (8.8 units/frame) */
        if (fobs < 110) fobs = 110;
        if (fobs > 900) fobs = 900;
        snd_riv_div = (u16)(111861 / fobs);
        s16 a2 = 4 + (s16)(bestd / (4 * 256));
        snd_riv_att = a2 > 15 ? 15 : (u8)a2;
    } else snd_riv_att = 15;
}

/* ---------------- frame build ---------------- */
static const char *place_sfx[5] = { "", "ST", "ND", "RD", "TH" };

static void text_spr(s16 x, s16 y, const char *t, u8 yellow) {
    for (u8 i = 0; t[i]; i++)
        spr_add(x + i * 8, y, 0, yellow ? FONT_Y + fidx_y[(u8)t[i]] : FONT_W + fidx_w[(u8)t[i]]);
}

static void build_frame(void) {
    u8 b = back;
    build_road(hs_buf[b], vs_buf[b]);
    build_dial(dial_buf[b]);
    select_car_angle();

    spr = spr_buf[b];
    nspr = 0;
    /* HUD sprites first (on top): analog speedometer + small digital readout */
    const s16 gx = 250, gy = 188;
    spr_add(gx, gy, 0xF, DIAL_SLOT);
    spr_add(gx + 32, gy, 0xF, DIAL_SLOT + 16);
    s16 sp = (s16)(((s32)speed * 128) / 253);   /* km/h */
    char num[4] = { (char)('0' + sp / 100), (char)('0' + (sp / 10) % 10), (char)('0' + sp % 10), 0 };
    if (sp < 100) num[0] = ' ';
    if (sp < 10) num[1] = ' ';
    text_spr(220, 200, num, 0);
    text_spr(214, 210, "KM/H", 1);

    /* start light: red, amber, then green with GO */
    if (state == ST_COUNT || (state == ST_RACE && state_t < 70 && laps == 0)) {
        const s16 lx = 152, ly = 30;
        s8 lamp = state == ST_RACE ? 2 : (state_t < 120 ? 0 : 1);
        u16 pal = lamp == 2 ? 1 : 0;
        spr_add(lx + 4, ly + 3 + lamp * 9, 0, (pal << 13) | (LAMP_T + lamp));   /* lamp above housing */
        spr_frame(LIGHT_BOX, lx, ly, 0, 0);
    }
    if (msg && msg_t > 0 && ((msg_t & 8) || msg_t > 60 || msg[0] == 'G')) {
        u8 len = 0; while (msg[len]) len++;
        text_spr(160 - len * 4, 68, msg, 0);
    }
    if (state == ST_TITLE) {
        spr_frame(FR_LOGO, 160, 28, 3, 0);
        spr_frame(FR_CREDIT, 4 + CREDIT_W / 2, 214, 3, 0);
        {
            u8 len = 0; while (track_name[len]) len++;
            s16 tx = 160 - len * 4;
            if (n_tracks > 1) { text_spr(tx - 16, 82, "<", 1); text_spr(tx + len * 8 + 8, 82, ">", 1); }
            text_spr(tx, 82, track_name, 0);
        }
        if (frame & 32) text_spr(116, 98, "PRESS START", 0);
    }

    /* tyre smoke in front of the car (it is closer to the camera), skid streaks under it */
    for (u8 i = 0; i < NPUFF; i++) {
        Puff *q = &puffs[i];
        if (!q->on) continue;
        u8 fi = q->age < 4 ? 0 : (q->age < 9 ? 1 : 2);
        spr_frame(fr_smoke[fi], q->x >> 4, q->y >> 4, 1, 0);
    }

    /* gather world objects */
    nobj = 0;
    objs[nobj].z = FIX_ZCAR; objs[nobj].kind = 0; objs[nobj].idx = 0; nobj++;
    for (u8 i = 0; i < NRIVALS && state != ST_TITLE; i++) {      /* the title logo borrows the rival art */
        s32 r = wrap_rel(rv[i].pos);
        if (r > zline[DLINES] && r < zline[3]) { objs[nobj].z = r; objs[nobj].kind = 1; objs[nobj].idx = i; nobj++; }
    }
    if (has_girl && (state == ST_COUNT || (state == ST_RACE && laps == 0))) {
        s32 r = wrap_rel(girl_pos);
        if (r > 7 * 256 && r < 80 * 256) { objs[nobj].z = r; objs[nobj].kind = 4; objs[nobj].idx = 0; nobj++; }
    }
    for (u8 i = 0; i < nob && nobj < MAXOBJS; i++) {      /* roadside objects from the track data */
        const OType *ot = &otypes[ob_type[i]];
        s32 r = wrap_rel(ob_pos[i]);
        if (r > (s32)ot->zmin && r < (s32)ot->zmax) { objs[nobj].z = r; objs[nobj].kind = 2; objs[nobj].idx = i; nobj++; }
    }
    /* insertion sort by depth, nearest first */
    for (u8 i = 1; i < nobj; i++) {
        Obj t = objs[i]; s8 j = i - 1;
        while (j >= 0 && objs[j].z > t.z) { objs[j + 1] = objs[j]; j--; }
        objs[j + 1] = t;
    }
    for (u8 i = 0; i < nobj; i++) {
        Obj *o = &objs[i];
        s16 sx, sy;
        if (o->kind == 0) {
            s16 cx = 160 + (s16)((mul16(px - camx, 31 * 8)) >> 11);   /* screen x of the car's centre line */
            s16 bx = cx - car_ox[car_show];
            s16 by = CAR_TOP + ((speed > 60 && (frame & 4)) ? 1 : 0);
            /* rear wheels on screen (for smoke/skids), shifted by the car's yaw */
            s16 shift = (s16)(mul16(car_angles[car_show], -11) >> 3);
            wheel_lx = cx - 31 + shift;
            wheel_rx = cx + 31 + shift;
            if (skid) {
                u16 t = SKID_T + skid_phase * 2;
                spr_add(wheel_lx - 4, 196, 0x1, t);
                spr_add(wheel_rx - 4, 196, 0x1, t);
                spr_add(wheel_lx - 4, 210, 0x1, t);
                spr_add(wheel_rx - 4, 210, 0x1, t);
            }
            for (u8 band = 0; band < 2; band++) {
                u16 t0 = CAR_SLOT + band * (CAR_BW / 8) * 4;
                for (u8 k = 0; k < 3; k++) spr_add(bx + k * 32, by + band * 32, 0xF, (2 << 13) | (t0 + k * 16));
                spr_add(bx + 96, by + band * 32, 0xB, (2 << 13) | (t0 + 48));   /* last column is 24 px wide */
            }
        } else if (o->kind == 1) {
            Rival *r = &rv[o->idx];
            if (!project(o->z, r->x, &sx, &sy)) continue;
            u8 bk = 0; while (bk < N_RIVAL_Z - 1 && o->z > rival_thr[bk]) bk++;
            spr_frame(r->yellow ? fr_red[bk] : fr_blue[bk], sx, sy, 3, 0);
        } else if (o->kind == 2) {
            u8 ty = ob_type[o->idx];
            const OType *ot = &otypes[ty];
            if (!project(o->z, ob_x[o->idx], &sx, &sy)) continue;
            u8 bk = 0; while (bk < ot->n - 1 && o->z > (s32)ot->thr[bk]) bk++;
            u8 fi = ot->first + bk;
            if (!ftb[fi]) continue;                                  /* art not in the pool */
            if (ty == 1) sy += (isin((u8)(frame * 2 + o->idx * 50)) >> 13);   /* boats bob */
            spr_frame(fi, sx, sy, ot->pal, ob_fl[o->idx] & 1);
        } else {
            if (!project(o->z, girl_x, &sx, &sy)) continue;
            u8 pose = (state == ST_RACE && state_t < 50) ? 2 : ((frame >> 3) & 1);
            spr_frame(fr_girl[pose], sx, sy, 2, 0);
        }
    }
    /* helicopter in the sky, behind everything else */
    if (heli.on) {
        s16 hxp = heli.x >> 4;
        u8 flip = heli.dir > 0;
        spr_frame(fr_heli[2 + ((frame >> 1) % 3)], hxp, heli.y, 2, flip);
        spr_frame(fr_heli[0], hxp, heli.y, 2, flip);
    }
    spr_finish();
    spr_count[b] = nspr;
}

/* ---------------- HUD (window) ---------------- */
static s16 last_fuel = -1, last_lap = -1, last_place = -1;
static void update_hud(void) {
    s16 lvl = (s16)(((s32)timer * 80) / MAX_FUEL);          /* 0..80 pixels */
    u8 low = timer < MAX_FUEL / 5;
    if (low && (frame & 16) && state == ST_RACE) lvl = -1;   /* blink when low */
    if (lvl != last_fuel) {
        last_fuel = lvl;
        for (u8 c = 0; c < 10; c++) {
            s16 l = lvl < 0 ? 0 : lvl - c * 8;
            if (l < 0) l = 0;
            if (l > 8) l = 8;
            whud[1][2 + c] = 0x8000 | (FUEL_T + (low ? 9 : 0) + l);
        }
        whud_dirty = 1;
    }
    s16 lp = laps + 1 > LAPS ? LAPS : laps + 1;
    if (lp != last_lap) {
        last_lap = lp;
        char s[4] = { (char)('0' + lp), '/', (char)('0' + LAPS), 0 };
        hud_text(1, 18, s, 0);
    }
    if (place != last_place) {
        last_place = place;
        hud_big(33, place);
        hud_text(2, 35, place_sfx[place], 0);
    }
}

static void compute_place(void) {
    if (state == ST_FINISH) return;          /* finishing position is final */
    s32 me = (s32)laps * (TRACK_LEN >> 8) + (pos >> 8);
    u8 p = 1;
    for (u8 i = 0; i < NRIVALS; i++) {
        s32 o = (s32)rv[i].laps * (TRACK_LEN >> 8) + ((rv[i].pos - FIX_ZCAR) >> 8);
        if (o > me) p++;
    }
    place = p;
}

/* ---------------- main ---------------- */
int main(void) {
    for (u8 i = 0; i < 128; i++) { fidx_w[i] = 0; fidx_y[i] = 0; }
    { const char *s = FONT_CHARS; for (u8 i = 0; s[i]; i++) fidx_w[(u8)s[i]] = i; }
    { const char *s = FONTY_CHARS; for (u8 i = 0; s[i]; i++) fidx_y[(u8)s[i]] = i; }
    *(volatile u8 *)0xA10009 = 0x40;   /* pad 1: TH pin as output */
    *(volatile u8 *)0xA10003 = 0x40;
    vdp_init();
    vram_fill0();
    vram_copy(0, (const u16 *)tiles_bin, (u16)((tiles_bin_end - tiles_bin) / 2));
    vram_copy(VR_PLANE_A, mapb_bin, 128 * 32);   /* sky */
    vram_copy(VR_PLANE_B, mapa_bin, 128 * 32);   /* road */
    for (u8 i = 0; i < N_HI_RANGES; i++)          /* sprites kept in spare VRAM gaps */
        vram_copy(hi_ranges[i][0] * 32, hi_bin + hi_ranges[i][2], hi_ranges[i][1] * 16);
    VDP_CTRL32 = VSRAM_W(0);
    for (u8 i = 0; i < 40; i++) VDP_DATA = 0;
    for (u16 i = 0; i < sizeof(ftb) / 2; i++) ftb[i] = frames[i].pooled_tiles ? 0 : frames[i].tbase;
    n_tracks = (DB[0] == 'S' && DB[1] == 'C' && DB[2] == 'R' && DB[3] == 'D') ? (u8)rd16(6) : 1;
    if (n_tracks < 1) n_tracks = 1;
    if (n_tracks > 4) n_tracks = 4;
    load_car();
    load_track(0);
    raster_init();
    for (u8 i = 0; i < NANG; i++)                 /* render the 3D car at every steering angle */
        render_car_angle(car_cache[i], i);
    car_show = 4; car_new = 1;
    music_init();
    hud_clear();
    hud_text(0, 1, "FUEL", 1);
    whud[1][1] = 0x8000 | (FUEL_T + 0);
    hud_text(0, 17, "LAP", 1);
    hud_text(0, 33, "POS", 1);

    state = ST_TITLE; state_t = 0;
    title_art_on();
    reset_race();
    speed = TOPSPEED / 2;
    for (u8 i = 0; i < NRIVALS; i++) rv[i].speed = rv[i].target;
    compute_place();
    update_hud();
    back = 0; front = 0;
    build_frame();
    ready_idx = 0; frame_ready = 1; back = 1;

    vdp_reg(1, 0x74);        /* display on, V-int on, DMA on */
    irq_enable();
#ifndef NO_MUSIC
    music_start();
#endif

    u16 last = vcount;
    for (;;) {
        u16 now;
        do { now = vcount; } while ((u16)(now - last) < 2 || frame_ready);   /* 30 fps */
        u8 dt = (u8)(now - last);
        if (dt > 3) dt = 3;
        last = now;
        frame += dt;

        u16 hit = pad_hit;
        __asm__ volatile("and.w %0,pad_hit" :: "d"((u16)~hit) : "memory");   /* atomic vs. V-int */
        switch (state) {
        case ST_TITLE:
            if (n_tracks > 1 && (hit & (PAD_LEFT | PAD_RIGHT))) {
                cur_track = (u8)((cur_track + ((hit & PAD_RIGHT) ? 1 : n_tracks - 1)) % n_tracks);
                load_track(cur_track);
                reset_race(); speed = TOPSPEED / 2;
                for (u8 i = 0; i < NRIVALS; i++) rv[i].speed = rv[i].target;
                last_lap = -1;
            }
            if (hit & PAD_START) {
                title_art_off();
                reset_race(); state = ST_COUNT; state_t = 0; msg = 0;
            }
            break;
        case ST_COUNT:
            state_t += dt;
            if (state_t >= 180) { state = ST_RACE; state_t = 0; msg = "GO!"; msg_t = 60; }
            break;
        case ST_RACE:
            if (state_t < 30000) state_t += dt;
            timer -= dt;
            if (timer <= 0) { timer = 0; state = ST_TIMEUP; state_t = 0; msg = "OUT OF FUEL"; msg_t = 300; }
            break;
        case ST_FINISH:
        case ST_TIMEUP:
            state_t += dt;
            if (state_t > 360 || ((hit & PAD_START) && state_t > 60)) {
                state = ST_TITLE; msg = 0; speed = TOPSPEED / 2;
                title_art_on();
            }
            break;
        }
        if (msg_t > 0) msg_t -= dt;
        update_player(dt);
        update_rivals(dt);
        update_heli(dt);
        update_sound(dt);
        compute_place();
        update_hud();
        build_frame();
        game_frames++;
        ready_idx = back;
        frame_ready = 1;
        back ^= 1;
    }
    return 0;
}
