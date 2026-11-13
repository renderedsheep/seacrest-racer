| Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
| Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
	.section .rodata
	.balign 2
	.globl tiles_bin, tiles_bin_end, mapa_bin, mapb_bin, dial_bin, hi_bin, pool_bin, title_bin
tiles_bin:	.incbin "build/tiles.bin"
tiles_bin_end:
	.balign 2
mapa_bin:	.incbin "build/mapa.bin"
mapb_bin:	.incbin "build/mapb.bin"
dial_bin:	.incbin "build/dial.bin"
hi_bin:	.incbin "build/hi.bin"
	.balign 2
pool_bin:	.incbin "build/pool.bin"
	.balign 2
title_bin:	.incbin "build/title.bin"
	.balign 2

	.section .cdata,"a"
	.globl cdata_block
cdata_block:	.incbin "build/cdata.bin"
