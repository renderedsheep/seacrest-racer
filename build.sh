#!/bin/bash
# Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
# Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
# Build SEACREST RACER: assets/music -> C (gcc 68000) + asm (gas) -> link -> ROM
set -e
cd "$(dirname "$0")"
export PATH=/opt/m68k/bin:$PATH
mkdir -p build out
python3 tools/gen_assets.py build > build/assets.log
python3 tools/gen_music.py build > build/music.log
python3 tools/gen_data.py build > build/data.log
CFLAGS="$EXTRA -m68000 -O2 -ffixed-a5 -fomit-frame-pointer -ffreestanding -fno-builtin -nostdlib -Wall -Wno-unused-function"
OBJS=""
for f in src/*.c; do
  o=build/$(basename "$f" .c).o
  m68k-elf-gcc $CFLAGS -c "$f" -o "$o"
  OBJS="$OBJS $o"
done
m68k-elf-as -m68000 --register-prefix-optional src/crt0.s -o build/crt0.o
m68k-elf-as -m68000 --register-prefix-optional src/assets.s -o build/assets_s.o
m68k-elf-ld -T src/md.ld -o build/coastrun.elf build/crt0.o $OBJS build/assets_s.o \
  "$(m68k-elf-gcc -m68000 -print-libgcc-file-name)" -Map build/coastrun.map
m68k-elf-objcopy -O binary build/coastrun.elf build/coastrun.bin
python3 tools/fixrom.py build/coastrun.bin out/seacrest_racer.md
