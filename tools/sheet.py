# Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
# Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
import sys
from PIL import Image
pre, frames, out = sys.argv[1], [int(x) for x in sys.argv[2].split(',')], sys.argv[3]
ims = [Image.open('%s_%05d.ppm' % (pre, f)) for f in frames]
w, h = ims[0].size
cols = 2
rows = (len(ims) + 1) // 2
c = Image.new('RGB', (w * cols, h * rows))
for i, im in enumerate(ims): c.paste(im, ((i % cols) * w, (i // cols) * h))
c = c.resize((c.width * 2, c.height * 2), Image.NEAREST)
c.save(out)
