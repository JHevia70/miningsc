#!/usr/bin/env python3
"""
gen_biome_overlays.py
=====================
Generates colorized biome overlay PNGs from splat map DDS files.
Each biome index (0-15) gets a distinct color; the result is a
semi-transparent RGBA PNG used as the biome layer on the 3D globe.

Usage
-----
  python gen_biome_overlays.py
  python gen_biome_overlays.py --planets stanton1a stanton1b

Output: H:/Projects/SC/web/public/images/planets/<stem>_biome.png
"""

import argparse
import struct
import sys
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("ERROR: pip install pillow numpy")
    sys.exit(1)

SPLAT_DIR = Path(r"F:\SC_temp\splats\Data\Textures\planets\global")
OUT_DIR   = Path(r"H:\Projects\SC\web\public\images\planets")

# Distinct colors for each biome index 0-15
BIOME_COLORS = [
    (220,  60,  60),  # 0  desert/barren
    (220, 120,  40),  # 1  rocky
    (200, 180,  40),  # 2  savanna
    (140, 200,  40),  # 3  grassland
    ( 40, 180, 140),  # 4  wetland
    ( 40, 160, 200),  # 5  ocean/water
    ( 80, 180, 200),  # 6  ice/arctic
    (120,  60, 220),  # 7  volcanic
    (180,  40, 200),  # 8  toxic/acidic
    (220,  40, 140),  # 9  scorched
    (160, 120,  60),  # 10 dusty
    ( 60, 100, 220),  # 11 deep ocean
    (220,  80,  80),  # 12 arid
    ( 60, 200,  80),  # 13 coastline/rare-point A
    (220, 200,  40),  # 14 plains
    ( 40, 200, 160),  # 15 coastline/rare-point B
]

# Planets to process: stem -> subdir inside SPLAT_DIR (system/planet)
PLANETS = {
    "stanton1a": "stanton/stanton1a",
    "stanton1b": "stanton/stanton1b",
    "stanton1c": "stanton/stanton1c",
    "stanton1d": "stanton/stanton1d",
    "stanton2b": "stanton/stanton2b",
    "stanton2c": "stanton/stanton2c",
    "stanton3b": "stanton/stanton3b",
}


def read_dds_r8(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if data[:4] != b"DDS ":
        raise ValueError(f"Not a DDS file: {path}")
    height = struct.unpack_from("<I", data, 12)[0]
    width  = struct.unpack_from("<I", data, 16)[0]
    pixels = np.frombuffer(data[128:], dtype=np.uint8)
    return pixels[:width * height].reshape(height, width)


def make_biome_png(splat_path: Path, out_path: Path,
                   target_size: tuple[int,int] = (512, 512)):
    raw = read_dds_r8(splat_path)
    idx = (raw // 16).astype(np.uint8)
    h, w = idx.shape

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for i, (r, g, b) in enumerate(BIOME_COLORS):
        mask = idx == i
        rgba[mask, 0] = r
        rgba[mask, 1] = g
        rgba[mask, 2] = b
        rgba[mask, 3] = 160  # semi-transparent

    img = Image.fromarray(rgba, "RGBA")
    if img.size != target_size:
        img = img.resize(target_size, Image.NEAREST)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    unique_idx = len(np.unique(idx))
    print(f"  -> {out_path.name}  ({unique_idx} biome indices, {img.size[0]}x{img.size[1]})")


def main():
    ap = argparse.ArgumentParser(description="Generate biome overlay PNGs from splat maps")
    ap.add_argument("--planets", nargs="*", default=None)
    args = ap.parse_args()

    target = set(args.planets) if args.planets else set(PLANETS.keys())

    for stem, subdir in PLANETS.items():
        if stem not in target:
            continue
        splat_path = SPLAT_DIR / subdir.replace("/", "\\") / f"{stem}_global_splat.dds"
        if not splat_path.exists():
            print(f"[{stem}] SKIP - splat not found: {splat_path}")
            continue
        out_path = OUT_DIR / f"{stem}_biome.png"
        print(f"[{stem}] {splat_path.name}")
        make_biome_png(splat_path, out_path)

    print("Done.")


if __name__ == "__main__":
    main()
