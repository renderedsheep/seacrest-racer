#!/usr/bin/env python3
# Seacrest Racer - Copyright 2026 Fernand Gouveia / PlayableFX.com
# Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
"""Packs editor/devkit.src.html with the art metadata and the default ROM into one self-contained page."""
import base64, json, sys
src = open("editor/devkit.src.html").read()
meta = json.load(open("build/meta.json"))
rom = open("out/seacrest_racer.md", "rb").read()
src = src.replace("/*META*/null", json.dumps(meta, separators=(",", ":")))
src = src.replace('"/*ROM*/"', '"' + base64.b64encode(rom).decode() + '"')
src = src.replace("/*LOGO*/", base64.b64encode(open("tools/art/logo.png", "rb").read()).decode())
out = sys.argv[1] if len(sys.argv) > 1 else "out/seacrest_devkit.html"
open(out, "w").write(src)
print("wrote", out, len(src), "bytes")
