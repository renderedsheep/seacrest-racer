# Seacrest Racer - Copyright 2026 Fernand Gouveia / PlayableFX.com
# Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
import sys
d = bytearray(open(sys.argv[1], 'rb').read())
size = max(0x40000, (len(d) + 0x1FFFF) // 0x20000 * 0x20000)   # pad to 128KB multiple
d += b'\xFF' * (size - len(d))
d[0x1A4:0x1A8] = (size - 1).to_bytes(4, 'big')
cs = 0
for i in range(0x200, len(d), 2):
    cs = (cs + (d[i] << 8 | d[i + 1])) & 0xFFFF
d[0x18E:0x190] = cs.to_bytes(2, 'big')
open(sys.argv[2], 'wb').write(d)
print("ROM %s: %d KB, checksum %04X" % (sys.argv[2], len(d) // 1024, cs))
