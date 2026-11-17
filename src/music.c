/* Seacrest Racer - Copyright 2026 Fernand Gouveia / PlayableFX.com
 * Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE). */
/* 68000-side sound driver: YM2612 FM + SN76489 PSG, ticked from V-int.
 * The Z80 is parked (bus held), so the 68000 writes the FM chip directly. */
#include "md.h"
#include "../build/music.h"

#define YM ((volatile u8 *)0xA04000)

static u8 playing;
static u8 tick, step;
static u8 ord;
static u8 gate[M_NCH];
static u8 psg_att[4], psg_rate[4], psg_cnt[4];
static u8 kick_t = 0xFF;
static u8 sfx_t;
volatile s16 snd_speed, snd_eng_hz = 42;
volatile u8 snd_eng_att = 6, snd_skid, snd_scrape, snd_riv_att = 15;
volatile u16 snd_riv_div = 900;
static u8 eng_phase;
#define ENG_CH 4          /* FM5 is the player's engine, not music */

static void ymw(u8 part, u8 reg, u8 val) {
    while (YM[0] & 0x80) {}
    YM[part << 1] = reg;
    while (YM[0] & 0x80) {}
    YM[(part << 1) + 1] = val;
}

static inline u8 fm_part(u8 c) { return c >= 3; }
static inline u8 fm_sub(u8 c) { return c >= 3 ? c - 3 : c; }
static inline u8 fm_key(u8 c) { return c >= 3 ? c + 1 : c; }

static void fm_keyoff(u8 c) { ymw(0, 0x28, fm_key(c)); }
static void fm_freq(u8 c, u16 bf) {
    ymw(fm_part(c), 0xA4 + fm_sub(c), (u8)(bf >> 8));
    ymw(fm_part(c), 0xA0 + fm_sub(c), (u8)bf);
}
static void fm_note(u8 c, u8 n) {
    fm_keyoff(c);
    u16 v = m_fnum[n];
    u16 bf = (u16)(((v >> 11) << 11) | (v & 0x7FF));
    fm_freq(c, bf);
    ymw(0, 0x28, 0xF0 | fm_key(c));
}

static void psg_tone(u8 ch, u16 div) {
    PSG_PORT = 0x80 | (ch << 5) | (div & 15);
    PSG_PORT = (div >> 4) & 63;
}
static void psg_vol(u8 ch, u8 att) { PSG_PORT = 0x90 | (ch << 5) | (att & 15); }

void music_init(void) {
    volatile u16 *busreq = (volatile u16 *)0xA11100;
    volatile u16 *reset = (volatile u16 *)0xA11200;
    *busreq = 0x100;
    *reset = 0x100;
    while (*busreq & 0x100) {}
    ymw(0, 0x22, 0);      /* LFO off */
    ymw(0, 0x27, 0);      /* ch3 normal */
    ymw(0, 0x2B, 0);      /* DAC off */
    for (u8 c = 0; c < 6; c++) {
        fm_keyoff(c);
        for (u8 i = 0; i < M_PATCH_REGS; i++) {
            u8 r = m_patch[c][i][0];
            ymw(fm_part(c), (u8)(r + fm_sub(c)), m_patch[c][i][1]);
        }
    }
    for (u8 ch = 0; ch < 4; ch++) { psg_vol(ch, 15); psg_att[ch] = 15; }
}

void music_start(void) { tick = 0; step = 0; ord = 0; playing = 1; }
void music_stop(void) {
    playing = 0;
    for (u8 c = 0; c < 6; c++) if (c != ENG_CH) fm_keyoff(c);
    for (u8 ch = 0; ch < 4; ch++) psg_vol(ch, 15);
}

void sfx_noise(u8 kind) { (void)kind; if (sfx_t == 0) sfx_t = 14; }

static void do_step(void) {
    const u8 *row = m_pat + ((u16)m_order[ord] * 16 + step) * (M_NCH * 2);
    for (u8 c = 0; c < 6; c++) {
        u8 n = row[c * 2];
        if (n == 0 || c == ENG_CH) continue;
        if (n == 0xFF) { fm_keyoff(c); gate[c] = 0; continue; }
        if (c == 0) { kick_t = 0; fm_note(0, 64); }
        else fm_note(c, n);
        gate[c] = row[c * 2 + 1];
    }
    for (u8 c = 6; c < 7; c++) {
        u8 n = row[c * 2];
        if (n == 0) continue;
        u8 ch = c - 6;
        psg_tone(ch, m_psg[n]);
        psg_att[ch] = ch == 0 ? 6 : 10;
        psg_rate[ch] = 2; psg_cnt[ch] = 0;
        psg_vol(ch, psg_att[ch]);
        gate[c] = row[c * 2 + 1];
    }
    u8 dr = row[8 * 2];
    if (dr && sfx_t == 0) {
        if (dr == 1) { PSG_PORT = 0xE4; psg_att[3] = 5; psg_rate[3] = 0x83; }
        else if (dr == 2) { PSG_PORT = 0xE4; psg_att[3] = 4; psg_rate[3] = 1; }
        else { PSG_PORT = 0xE5; psg_att[3] = 1; psg_rate[3] = 1; }
        psg_cnt[3] = 0;
        psg_vol(3, psg_att[3]);
    }
    if (++step >= 16) {
        step = 0;
        if (++ord >= M_NORDER) ord = M_LOOP;
    }
}

static const u8 kick_sweep[8] = { 64, 55, 49, 45, 42, 40, 38, 37 };

/* Engine and effects, every frame:
 *  FM5  = player engine (growl, pitch from rpm, volume from throttle)
 *  PSG2 = nearest rival's engine, pitch includes Doppler shift, volume by distance
 *  PSG3 = tire squeal / wall scrape */
static u8 eng_on;
static void engine_sound(void) {
    eng_phase++;
    if (!eng_on) { ymw(0, 0x28, 0xF0 | fm_key(ENG_CH)); eng_on = 1; }
    u16 hz = (u16)snd_eng_hz + ((eng_phase & 2) ? 1 : 0);
    u16 fn = (u16)((hz * 315u) >> 5);                     /* block 2 */
    if (fn > 2047) fn = 2047;
    fm_freq(ENG_CH, (u16)((2 << 11) | fn));
    ymw(fm_part(ENG_CH), 0x4C + fm_sub(ENG_CH), (u8)(10 + snd_eng_att * 5));

    psg_tone(1, snd_riv_div + ((eng_phase & 4) ? 4 : 0));
    psg_vol(1, snd_riv_att);

    if (snd_skid) {
        psg_tone(2, 64 + ((eng_phase * 37) & 15));
        psg_vol(2, 7);
    } else if (snd_scrape) {
        psg_tone(2, 300 + ((eng_phase * 53) & 63));
        psg_vol(2, 8);
    } else psg_vol(2, 15);
}

void music_tick(void) {
    engine_sound();
    if (sfx_t) {
        if (sfx_t == 14) PSG_PORT = 0xE6;
        psg_vol(3, (u8)(14 - sfx_t));
        sfx_t--;
        if (!sfx_t) psg_vol(3, 15);
    }
    if (!playing) return;
    /* per-frame envelopes */
    if (kick_t < 8) {
        u16 v = m_fnum[kick_sweep[kick_t]];
        fm_freq(0, v);
        kick_t++;
    }
    for (u8 c = 1; c < 6; c++)
        if (c != ENG_CH && gate[c]) { if (--gate[c] == 0) fm_keyoff(c); }
    for (u8 ch = 0; ch < 1; ch++) {
        if (psg_att[ch] < 15) {
            if (gate[6 + ch]) gate[6 + ch]--;
            u8 r = gate[6 + ch] ? 2 : 1;
            if (++psg_cnt[ch] >= r) { psg_cnt[ch] = 0; psg_att[ch]++; psg_vol(ch, psg_att[ch]); }
        }
    }
    if (psg_att[3] < 15 && sfx_t == 0) {
        u8 r = psg_rate[3];
        if (r & 0x80) { psg_att[3] += 3; if (psg_att[3] > 15) psg_att[3] = 15; }
        else if (++psg_cnt[3] >= r) { psg_cnt[3] = 0; psg_att[3]++; }
        psg_vol(3, psg_att[3]);
    }
    if (++tick >= M_STEP_FRAMES) { tick = 0; do_step(); }
}
