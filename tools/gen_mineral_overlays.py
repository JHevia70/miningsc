#!/usr/bin/env python3
"""
gen_mineral_overlays.py
=======================
Generates per-biome mineral zone overlay PNGs from splat map DDS files.

Each output PNG is a white-on-transparent mask (RGBA) where white pixels
mark the presence of a biome zone. The Three.js globe loads this as a
MeshBasicMaterial with AdditiveBlending and sets its color to the mineral's
color — so the zone lights up only when that mineral is selected.

Biome→mineral mapping for Hurston (from hpp_stanton1.json):
  acidic  → Beradom, Glacosite, Feynmaline (GV) + Hadanite, Aphorite, Dolivine (FPS)
  The splat indices for "rare point" biomes (Acidic/Coastline) are 13 and 15.
  Since we cannot distinguish them from the splat alone, we use both.

Usage
-----
  python gen_mineral_overlays.py
  python gen_mineral_overlays.py --planets stanton1a stanton2b

Output: H:/Projects/SC/web/public/images/planets/<planet>_zone_<tag>.png
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

# ── Paths ─────────────────────────────────────────────────────────────────────

SPLAT_DIR   = Path(r"F:\SC_temp\splats\Data\Textures\planets\global\stanton")
OUT_DIR     = Path(r"H:\Projects\SC\web\public\images\planets")

# ── Splat config per planet ────────────────────────────────────────────────────
# Each entry: splat DDS stem → list of (tag, [indices], blur_radius)
# tag is used in the output filename: <planet>_zone_<tag>.png

PLANET_ZONES: dict[str, list[tuple[str, list[int], int]]] = {
    # stanton1a (Hurston): Acidic biome = splat indices 13 + 15 (rare-point biomes)
    # Minerals: Beradom, Glacosite, Feynmaline (GV) + Hadanite, Aphorite, Dolivine (FPS)
    # Also ship: Aluminum, Corundum, Hephaestanite, Tin, Ouratite, Quantainium
    "stanton1a": [("acidic", [13, 15], 4)],

    # stanton2c (Yela): Ice biome = splat indices 3, 5, 6, 8 (all <2.5%)
    # Minerals: Beradom, Glacosite, Feynmaline (GV) + Quartz, Silicon, Taranite, Agricium, Quantainium (ship)
    "stanton2c": [("ice", [3, 5, 6, 8], 4)],

    # stanton3b (Lyria): Crystaline biome = splat indices 3, 15 (rarest <1.3%)
    # Minerals: Beradom, Glacosite, Feynmaline (GV) + Copper, Iron, Beryl, Laranite, Quantainium (ship)
    "stanton3b": [("crystaline", [3, 15], 4)],
}

# Which minerals appear in each zone tag (for the web app to know)
ZONE_MINERALS: dict[str, list[str]] = {
    "acidic":    ["Beradom", "Glacosite", "Feynmaline", "Hadanite", "Aphorite", "Dolivine",
                  "Aluminium", "Corundum", "Hephaestanite", "Tin", "Ouratite", "Quantainium"],
    "ice":       ["Beradom", "Glacosite", "Feynmaline",
                  "Quartz", "Silicon", "Taranite", "Agricium", "Quantainium"],
    "crystaline": ["Beradom", "Glacosite", "Feynmaline",
                   "Copper", "Iron", "Beryl", "Laranite", "Quantainium"],
}

# ── DDS reader (R8_UINT splat maps) ───────────────────────────────────────────

def read_dds_r8(path: Path) -> np.ndarray:
    """Read a DDS R8_UINT file and return a 2D uint8 numpy array."""
    data = path.read_bytes()

    # DDS header is 128 bytes; pixel data follows immediately
    # Validate magic
    if data[:4] != b"DDS ":
        raise ValueError(f"Not a DDS file: {path}")

    # Read height/width from header (offsets 12 and 16)
    height = struct.unpack_from("<I", data, 12)[0]
    width  = struct.unpack_from("<I", data, 16)[0]

    pixels = np.frombuffer(data[128:], dtype=np.uint8)

    expected = width * height
    if len(pixels) < expected:
        raise ValueError(f"DDS too small: expected {expected} bytes, got {len(pixels)}")

    return pixels[:expected].reshape(height, width)


def splat_to_index(raw: np.ndarray) -> np.ndarray:
    """Convert R8 pixel values (0,16,32,...,240) to index 0..15."""
    return (raw // 16).astype(np.uint8)


# ── Blur ──────────────────────────────────────────────────────────────────────

def box_blur(arr: np.ndarray, radius: int) -> np.ndarray:
    """Fast separable box blur via cumsum."""
    k = 2 * radius + 1
    f = arr.astype(np.float32)

    # Horizontal
    cs = np.cumsum(f, axis=1)
    cs = np.pad(cs, ((0,0),(1,0)), mode="constant")
    h = (cs[:, k:] - cs[:, :-k]) / k

    # Vertical
    cs2 = np.cumsum(h, axis=0)
    cs2 = np.pad(cs2, ((1,0),(0,0)), mode="constant")
    v = (cs2[k:, :] - cs2[:-k, :]) / k

    return v


def make_zone_png(splat_path: Path, indices: list[int], blur_radius: int,
                  out_path: Path, target_size: tuple[int,int] = (512, 256)):
    """
    Create a white-on-transparent PNG mask for the given splat indices.
    The mask is upscaled to target_size for use as a globe texture.
    """
    raw = read_dds_r8(splat_path)
    idx = splat_to_index(raw)

    # Binary mask: 1 where any of the listed indices is present
    mask = np.zeros_like(idx, dtype=np.float32)
    for i in indices:
        mask[idx == i] = 1.0

    # Blur to soften edges
    if blur_radius > 0:
        for _ in range(3):  # 3 passes for smooth falloff
            mask = box_blur(mask, blur_radius)

    # Normalise to 0..255
    mx = mask.max()
    if mx > 0:
        mask = mask / mx

    alpha = (mask * 255).clip(0, 255).astype(np.uint8)

    # Build RGBA: white where present, alpha = blurred mask
    h, w = alpha.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, 0] = 255  # R
    rgba[:, :, 1] = 255  # G
    rgba[:, :, 2] = 255  # B
    rgba[:, :, 3] = alpha

    img = Image.fromarray(rgba, "RGBA")

    # Upscale to target size using LANCZOS for smooth result
    tw, th = target_size
    img = img.resize((tw, th), Image.LANCZOS)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    nonzero = int(np.count_nonzero(alpha))
    total   = alpha.size
    print(f"  -> {out_path.name}  ({nonzero}/{total} px = {100*nonzero/total:.1f}% coverage)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Generate mineral zone overlay PNGs from splat maps")
    ap.add_argument("--planets", nargs="*", default=None,
                    help="Limit to these planet stems (e.g. stanton1a stanton2b)")
    args = ap.parse_args()

    target_planets = set(args.planets) if args.planets else set(PLANET_ZONES.keys())

    for planet, zones in PLANET_ZONES.items():
        if planet not in target_planets:
            continue

        # Find the per-planet splat DDS
        # Try: <planet>/<planet>_global_splat.dds  (individual planet dir)
        # Then: <planet>_global_splat.dds           (flat in splat dir)
        candidates = [
            SPLAT_DIR / planet / f"{planet}_global_splat.dds",
            SPLAT_DIR / f"{planet}_global_splat.dds",
        ]
        splat_path = next((p for p in candidates if p.exists()), None)
        if not splat_path:
            print(f"[{planet}] SKIP — splat DDS not found (tried {candidates})")
            continue

        print(f"[{planet}] splat: {splat_path}")

        for tag, indices, blur_r in zones:
            out_path = OUT_DIR / f"{planet}_zone_{tag}.png"
            print(f"  zone '{tag}' indices={indices} blur={blur_r}")
            make_zone_png(splat_path, indices, blur_r, out_path)

    # Print web app config block
    print("\nZone minerals config:")
    for tag, minerals in ZONE_MINERALS.items():
        print(f'  "{tag}": {minerals}')


if __name__ == "__main__":
    main()
