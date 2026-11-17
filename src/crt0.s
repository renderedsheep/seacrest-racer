| Seacrest Racer - Copyright 2026 Fernand Gouveia / PlayableFX.com
| Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
| SEACREST RACER - startup, interrupt handlers and runtime helpers (68000, gas syntax)
	.section .vectors,"ax"
	.long	0x01000000		| initial SP (wraps to top of RAM)
	.long	_start
	.rept	22
	.long	_crash
	.endr
	.long	_crash			| spurious
	.long	_rte			| level 1
	.long	_rte			| level 2 (ext)
	.long	_rte			| level 3
	.long	_hint			| level 4 (H-int)
	.long	_rte			| level 5
	.long	_vint			| level 6 (V-int)
	.long	_rte			| level 7
	.rept	32
	.long	_crash
	.endr

	| ---- cartridge header at 0x100 ----
	.ascii	"SEGA MEGA DRIVE "
	.ascii	"(C)PLFX 2026.NOV"
	.ascii	"SEACREST RACER                                  "
	.ascii	"SEACREST RACER                                  "
	.ascii	"GM 00000001-00"
	.word	0x0000
	.ascii	"J               "
	.long	0x00000000, 0x003FFFFF
	.long	0x00FF0000, 0x00FFFFFF
	.ascii	"            "
	.ascii	"            "
	.ascii	"(C)2026 FERNAND GOUVEIA / PLAYABLEFX.COM"
	.ascii	"JUE             "

	.text
	.globl	_start
_start:
	move.w	#0x2700,sr
	move.b	0xA10001,d0		| TMSS
	andi.b	#0x0F,d0
	beq.s	1f
	move.l	#0x53454741,0xA14000
1:
	tst.w	0xC00004		| clear pending VDP state
	lea	0xFF0000,a0		| clear RAM
	move.w	#0x3FFF,d0
2:	clr.l	(a0)+
	dbra	d0,2b
	lea	__data_load,a0		| copy initialized data
	lea	__data_start,a1
	move.l	#__data_end,d0
	sub.l	a1,d0
	lsr.l	#1,d0
	beq.s	4f
	subq.l	#1,d0
3:	move.w	(a0)+,(a1)+
	dbra	d0,3b
4:
	jsr	main
	bra.s	4b

_crash:
	move.w	#0x2700,sr
	move.l	#0xC0000000,0xC00004	| CRAM 0 = red so a crash is visible
	move.w	#0x000E,0xC00000
	move.w	#0x8700,0xC00004
5:	bra.s	5b

_rte:
	rte

	| ---- H-int: per-line vertical scroll of plane B (the road) ----
	| V-int sets reg10 = K so the first H-int lands at line K (sky): it only sets
	| reg10 = 0, which makes the next one land at 2K+1 = horizon and then every line.
	| a5 is reserved (gcc -ffixed-a5) as the walking pointer into the scroll table.
	.equ	FIRST_LINE, 47
_hint:
	move.w	#0x2700,sr		| V-int must not split the two VDP writes below
	cmpi.b	#0xDE,0xC00008
	bhi.s	1f			| stale interrupt delivered during vblank: ignore
	cmpi.b	#FIRST_LINE+1,0xC00008
	bcs.s	2f			| first (sky) interrupt
	move.l	#0x40020010,0xC00004	| VSRAM write, address 2 (plane B)
	move.w	(a5)+,0xC00000
1:	rte
2:	move.w	#0x8A00,0xC00004	| reg10 = 0 -> every line from the horizon on
	rte

	| ---- V-int: save everything, call C ----
_vint:
	movem.l	d0-d7/a0-a4/a6,-(sp)	| a5 belongs to the H-int
	jsr	vblank_c
	movem.l	(sp)+,d0-d7/a0-a4/a6
	rte

	.globl	irq_enable
irq_enable:
	move.w	#0x2000,sr
	rts

	.globl	enable_hint_in_isr
enable_hint_in_isr:			| lower IPL to 3 so H-int can preempt the rest of V-int
	move.w	#0x2300,sr
	rts

	| ---- runtime helpers expected by the compiler ----
	| args at 4(sp), 8(sp); result in d0; d0/d1/a0/a1 are scratch
	.globl	__mulsi3
__mulsi3:
	move.l	4(sp),d0
	move.l	8(sp),d1
	move.w	d0,a0			| a0 = sign-extended low word of a
	cmpa.l	d0,a0
	bne.s	.Lmul_long
	move.w	d1,a1
	cmpa.l	d1,a1
	bne.s	.Lmul_long
	muls.w	d1,d0			| both fit in 16 bits
	rts
.Lmul_long:
	move.l	d2,-(sp)
	move.l	d0,d2
	swap	d2
	mulu.w	d1,d2			| ah*bl
	swap	d1
	mulu.w	d0,d1			| al*bh
	add.w	d1,d2
	swap	d2
	clr.w	d2
	move.l	12(sp),d1
	mulu.w	d1,d0			| al*bl
	add.l	d2,d0
	move.l	(sp)+,d2
	rts

	| unsigned 32/32 core: d0 = n, d1 = d  ->  d0 = q, d1 = r
udiv32:
	cmpi.l	#0xFFFF,d1
	bhi.s	.Lud_big
	move.l	d2,-(sp)
	move.l	d0,d2
	clr.w	d2
	swap	d2			| d2 = n_hi
	divu.w	d1,d2			| d2 = r1:q_hi
	move.l	d3,-(sp)
	move.w	d2,d3			| q_hi
	move.w	d0,d2			| d2 = r1:n_lo
	divu.w	d1,d2			| d2 = r:q_lo
	swap	d3
	move.w	d2,d3			| d3 = q_hi:q_lo
	clr.w	d2
	swap	d2			| d2 = r
	move.l	d3,d0
	move.l	d2,d1
	move.l	(sp)+,d3
	move.l	(sp)+,d2
	rts
.Lud_big:				| divisor >= 65536: shift-subtract
	movem.l	d2-d3,-(sp)
	moveq	#0,d2			| remainder
	moveq	#31,d3
.Lud_loop:
	add.l	d0,d0
	addx.l	d2,d2
	cmp.l	d1,d2
	bcs.s	.Lud_skip
	sub.l	d1,d2
	addq.l	#1,d0
.Lud_skip:
	dbra	d3,.Lud_loop
	move.l	d2,d1
	movem.l	(sp)+,d2-d3
	rts

	.globl	__udivsi3
__udivsi3:
	move.l	4(sp),d0
	move.l	8(sp),d1
	bra	udiv32

	.globl	__umodsi3
__umodsi3:
	move.l	4(sp),d0
	move.l	8(sp),d1
	bsr	udiv32
	move.l	d1,d0
	rts

	.globl	__divsi3
__divsi3:
	move.l	d2,-(sp)
	move.l	8(sp),d0
	move.l	12(sp),d1
	moveq	#0,d2
	tst.l	d0
	bpl.s	1f
	neg.l	d0
	not.b	d2
1:	tst.l	d1
	bpl.s	2f
	neg.l	d1
	not.b	d2
2:	bsr	udiv32
	tst.b	d2
	beq.s	3f
	neg.l	d0
3:	move.l	(sp)+,d2
	rts

	.globl	__modsi3
__modsi3:
	move.l	d2,-(sp)
	move.l	8(sp),d0
	move.l	12(sp),d1
	moveq	#0,d2
	tst.l	d0
	bpl.s	1f
	neg.l	d0
	not.b	d2			| remainder takes the sign of the dividend
1:	tst.l	d1
	bpl.s	2f
	neg.l	d1
2:	bsr	udiv32
	move.l	d1,d0
	tst.b	d2
	beq.s	3f
	neg.l	d0
3:	move.l	(sp)+,d2
	rts

	.globl	memset
memset:
	movea.l	4(sp),a0
	move.l	8(sp),d0
	move.l	12(sp),d1
	beq.s	2f
1:	move.b	d0,(a0)+
	subq.l	#1,d1
	bne.s	1b
2:	move.l	4(sp),d0
	rts

	.globl	memcpy
memcpy:
	movea.l	4(sp),a1
	movea.l	8(sp),a0
	move.l	12(sp),d1
	beq.s	2f
1:	move.b	(a0)+,(a1)+
	subq.l	#1,d1
	bne.s	1b
2:	move.l	4(sp),d0
	rts

