#!/usr/bin/env python3
"""
process_ui_starmap.py
=====================
Resizes UI starmap PNGs to web-ready size and copies to web public dir.

Source: F:/SC_temp/ui_starmap/.../ui_sm_*.png  (4096x4096 or 2048x1024)
Target: H:/Projects/SC/web/public/images/planets/<stem>.png at 2048x1024

Mapping is defined in SOURCE_MAP below.
"""

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: pip install pillow")
    sys.exit(1)

UI_DIR  = Path(r"F:\SC_temp\ui_starmap\Data\UI\starmap\textures")
OUT_DIR = Path(r"H:\Projects\SC\web\public\images\planets")
TARGET_W, TARGET_H = 1024, 512

# Maps source PNG (relative to UI_DIR) -> output stem
SOURCE_MAP = {
    # Pyro
    "Pyro/ui_sm_pyro_1.png":  "pyro1",
    "Pyro/ui_sm_pyro_2.png":  "pyro2",
    "Pyro/ui_sm_pyro_3.png":  "pyro3",
    "Pyro/ui_sm_pyro_4.png":  "pyro4",
    "Pyro/ui_sm_pyro_5a.png": "pyro5a",
    "Pyro/ui_sm_pyro_5b.png": "pyro5b",
    "Pyro/ui_sm_pyro_5c.png": "pyro5c",
    "Pyro/ui_sm_pyro_5d.png": "pyro5d",
    "Pyro/ui_sm_pyro_5e.png": "pyro5e",
    "Pyro/ui_sm_pyro_5f.png": "pyro5f",
    "Pyro/ui_sm_pyro_6.png":  "pyro6",
    # Nyx
    "Nyx/ui_sm_nyx_1.png":    "nyx1",
    "Nyx/ui_sm_nyx_2.png":    "nyx2",
    "Nyx/ui_sm_nyx_3.png":    "nyx3",
}

def process(src_rel: str, stem: str):
    src = UI_DIR / src_rel.replace("/", "\\")
    out = OUT_DIR / f"{stem}.png"
    if not src.exists():
        print(f"  SKIP {src_rel} (not found)")
        return
    img = Image.open(src)
    # Convert to RGB (drop alpha — planet textures don't need transparency)
    img = img.convert("RGB")
    if img.size != (TARGET_W, TARGET_H):
        img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    img.save(out, "PNG", optimize=True)
    size_kb = out.stat().st_size // 1024
    print(f"  {stem}.png  {img.size}  {size_kb} KB  (from {img.size[0]}x{img.size[1]} source)")

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Processing {len(SOURCE_MAP)} textures -> {OUT_DIR}")
    for src_rel, stem in SOURCE_MAP.items():
        process(src_rel, stem)
    print("Done.")

if __name__ == "__main__":
    main()
