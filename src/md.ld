/* Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
 * Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE). */
OUTPUT_ARCH(m68k)
ENTRY(_start)
MEMORY {
  rom (rx)  : ORIGIN = 0x000000, LENGTH = 4M
  ram (rwx) : ORIGIN = 0xFF0000, LENGTH = 0xFE00
}
SECTIONS {
  .text : {
    KEEP(*(.vectors))
    *(.text .text.*)
    . = ALIGN(2);
    *(.rodata .rodata.*)
    . = ALIGN(2);
  } > rom
  .data : {
    __data_start = .;
    *(.data .data.*)
    . = ALIGN(2);
    __data_end = .;
  } > ram AT > rom
  __data_load = LOADADDR(.data);
  .bss (NOLOAD) : {
    __bss_start = .;
    *(.bss .bss.* COMMON)
    . = ALIGN(2);
    __bss_end = .;
  } > ram
  /* editable data block (tracks + car) at a fixed ROM address for the editors */
  .cdata 0x030000 : {
    KEEP(*(.cdata))
  } > rom
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame) *(.llvm_addrsig) }
}
