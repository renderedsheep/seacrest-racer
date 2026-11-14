/* Seacrest Racer - Copyright 2026 Fernand Gouveia / PlayableFX.com
 * Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE). */
#pragma once
typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef short s16;
typedef unsigned long u32;
typedef long s32;

#define VDP_DATA   (*(volatile u16 *)0xC00000)
#define VDP_DATA32 (*(volatile u32 *)0xC00000)
#define VDP_CTRL   (*(volatile u16 *)0xC00004)
#define VDP_CTRL32 (*(volatile u32 *)0xC00004)
#define PSG_PORT   (*(volatile u8 *)0xC00011)

#define VRAM_W(a)  (0x40000000UL | (((u32)(a) & 0x3FFF) << 16) | ((u32)(a) >> 14))
#define CRAM_W(a)  (0xC0000000UL | (((u32)(a) & 0x3FFF) << 16))
#define VSRAM_W(a) (0x40000010UL | (((u32)(a) & 0x3FFF) << 16))

/* VRAM layout */
#define VR_PLANE_A 0xA000   /* sky   (128x32) */
#define VR_PLANE_B 0xC000   /* road  (128x32) */
#define VR_WINDOW  0xE000   /* HUD bar */
#define VR_SPRITES 0xF000
#define VR_HSCROLL 0xF400

static inline void vdp_reg(u8 r, u8 v) { VDP_CTRL = 0x8000 | ((u16)r << 8) | v; }

/* pad bits (active high after read) */
#define PAD_UP    0x01
#define PAD_DOWN  0x02
#define PAD_LEFT  0x04
#define PAD_RIGHT 0x08
#define PAD_B     0x10
#define PAD_C     0x20
#define PAD_A     0x40
#define PAD_START 0x80

void music_init(void);
void music_tick(void);
void music_start(void);
void music_stop(void);
void sfx_noise(u8 kind);
extern void enable_hint_in_isr(void);
