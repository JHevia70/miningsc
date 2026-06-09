#!/usr/bin/env python3
"""
gen_clim_overlays.py
====================
Generates per-zone mineral overlay PNGs from clim map PNGs.

Clim map RGBA channels:
  G = temperature / latitude proxy (0 = cold/polar, 255 = hot/equatorial)
  R = secondary terrain info
  B = always 127-254 (moisture/elevation)
  A = always 255

Zone detection: threshold on G channel.
  polar zone:      G < threshold  (cold = poles)
  equatorial zone: G > threshold  (hot = tropics/equator)

Special case: pyro6 (Terminus) — G is inverted (polar = high G).

Output: H:/Projects/SC/web/public/images/planets/<stem>_zone_<tag>.png
Format: white-on-transparent RGBA mask, same as splat-based overlays.
"""

import sys
from pathlib import Path
import numpy as np
try:
    from PIL import Image
except ImportError:
    print("ERROR: pip install pillow"); sys.exit(1)

CLIM_BASE = Path(r"F:\SC_temp\clims\Data\Textures\planets\global")
OUT_DIR   = Path(r"H:\Projects\SC\web\public\images\planets")

# Configuration per body:
# key: body_stem
# value: list of (zone_tag, zone_type, g_threshold, minerals)
#   zone_type: "polar" (G < thresh) or "equatorial" (G > thresh)
#   minerals: list of mineral names in this zone
#
# Bodies with only a single zone (all minerals same biome):
#   We use "polar" for Ice biome since ice concentrates at poles,
#   and "equatorial" for Desert biome (hot = equator).
#
# Bodies with two distinct biome zones:
#   We generate both a polar and equatorial zone.
#
# Thresholds chosen from analyze_clims.py output.
# G polar_mean vs equator_mean: threshold = midpoint.

BODY_ZONES = {
    # Hurston (stanton1a): Acidic(polar, splat-based already done) + Desert(equatorial/general)
    # But stanton1a has a splat, so we skip it here — already handled by gen_mineral_overlays.py
    # Keeping here for reference only — commented out.

    # Daymar (stanton2b): Desert only → all minerals same biome
    # polar_mean=27.8, equator_mean=190.3 → desert = equatorial zone (high G)
    "stanton2b": [
        ("desert", "equatorial", 100,
         ["Agricium", "Aphorite", "Beradom", "Dolivine", "Feynmaline",
          "Glacosite", "Hadanite", "Quantainium", "Quartz", "Silicon"]),
    ],

    # ArcCorp (stanton3a): Ice only → polar zone
    # polar_mean=33.1, equator_mean=217.9 → threshold=125
    "stanton3a": [
        ("ice", "polar", 100,
         ["Aphorite", "Beradom", "Copper", "Dolivine", "Feynmaline",
          "Glacosite", "Iron", "Janalite", "Laranite", "Quantainium"]),
    ],

    # MicroTech (stanton4a): Ice → polar zone
    # polar_mean=25.4, equator_mean=89.2 → G<40 covers ~31% (polar caps + high latitudes)
    "stanton4a": [
        ("ice", "polar", 40,
         ["Aphorite", "Beradom", "Dolivine", "Feynmaline", "Glacosite",
          "Hephaestanite", "Ice", "Iron", "Janalite", "Quantainium"]),
    ],

    # Calliope (stanton4b): Ice → polar zone
    # polar_mean=55.6, equator_mean=177.3 → threshold=100
    "stanton4b": [
        ("ice", "polar", 100,
         ["Aphorite", "Beradom", "Copper", "Dolivine", "Feynmaline",
          "Glacosite", "Ice", "Janalite", "Quantainium", "Taranite"]),
    ],

    # Clio (stanton4c): Ice → no strong polar signal (diff=6.9), skip
    # "stanton4c": [],

    # Aberdeen (stanton1b): Desert only → equatorial
    # polar_mean=29.7, equator_mean=223.6 → threshold=100
    "stanton1b": [
        ("desert", "equatorial", 100,
         ["Aluminum", "Aphorite", "Beradom", "Corundum", "Dolivine",
          "Feynmaline", "Glacosite", "Hadanite", "Ouratite", "Quantainium", "Titanium"]),
    ],

    # Arial (stanton1c): Desert only → equatorial
    # polar_mean=40.8, equator_mean=195.8 → threshold=100
    "stanton1c": [
        ("desert", "equatorial", 100,
         ["Aluminum", "Aphorite", "Aslarite", "Beradom", "Dolivine",
          "Feynmaline", "Glacosite", "Hadanite", "Iron", "Quantainium", "Titanium"]),
    ],

    # Ita (stanton1d): Desert only → equatorial
    # polar_mean=34.7, equator_mean=188.7 → threshold=100
    "stanton1d": [
        ("desert", "equatorial", 100,
         ["Aluminum", "Aphorite", "Aslarite", "Beradom", "Dolivine",
          "Feynmaline", "Glacosite", "Hadanite", "Quantainium", "Tin"]),
    ],

    # Crusader (stanton2a): Lunar(polar) + Desert(equatorial)
    # polar_mean=59.8, equator_mean=177.5 → threshold=100
    "stanton2a": [
        ("lunar", "polar", 100,
         ["Agricium", "Beradom", "Feynmaline", "Glacosite",
          "Quantainium", "Quartz", "Silicon", "Taranite"]),
        ("desert", "equatorial", 100,
         ["Aphorite", "Dolivine", "Hadanite"]),
    ],

    # Pyro I (pyro1): Ice → polar
    # polar_mean=23.8, equator_mean=217.7 → threshold=100
    "pyro1": [
        ("ice", "polar", 100,
         ["Aphorite", "Dolivine", "Hadanite"]),
    ],

    # Monox (pyro2): Ice → polar
    # polar_mean=27.3, equator_mean=202.5 → threshold=100
    "pyro2": [
        ("ice", "polar", 100,
         ["Aphorite", "Dolivine", "Hadanite"]),
    ],

    # Pyro III (pyro3): Ice → polar
    # polar_mean=25.9, equator_mean=220.4 → threshold=100
    "pyro3": [
        ("ice", "polar", 100,
         ["Aphorite", "Dolivine", "Janalite"]),
    ],

    # Bloom (pyro4): Ice → polar
    # polar_mean=26.6, equator_mean=184.6 → threshold=100
    "pyro4": [
        ("ice", "polar", 100,
         ["Aphorite", "Dolivine", "Hadanite"]),
    ],

    # Pyro V moons (pyro5a-f): Ice → polar
    "pyro5a": [
        ("ice", "polar", 100,
         ["Aphorite", "Dolivine", "Hadanite"]),
    ],
    "pyro5b": [
        ("ice", "polar", 100,
         ["Aphorite", "Dolivine", "Hadanite"]),
    ],
    "pyro5c": [
        ("ice", "polar", 80,
         ["Aphorite", "Dolivine", "Hadanite"]),
    ],
    "pyro5d": [
        ("ice", "polar", 100,
         ["Aphorite", "Dolivine", "Hadanite"]),
    ],
    "pyro5e": [
        ("ice", "polar", 100,
         ["Aphorite", "Dolivine", "Janalite"]),
    ],
    "pyro5f": [
        ("ice", "polar", 100,
         ["Aphorite", "Dolivine", "Hadanite"]),
    ],

    # Terminus (pyro6): Ice → G INVERTED (polar_mean=162 > equator_mean=68)
    # High G = polar here → use "polar_inverted"
    "pyro6": [
        ("ice", "polar_inverted", 120,
         ["Aphorite", "Dolivine", "Janalite"]),
    ],
}

# Path to clim PNG per body
CLIM_PATHS = {
    "stanton1b": CLIM_BASE / "stanton" / "stanton1b" / "stanton1b_global_clim.png",
    "stanton1c": CLIM_BASE / "stanton" / "stanton1c" / "stanton1c_global_clim.png",
    "stanton1d": CLIM_BASE / "stanton" / "stanton1d" / "stanton1d_global_clim.png",
    "stanton2a": CLIM_BASE / "stanton" / "stanton2a" / "stanton2a_global_clim.png",
    "stanton2b": CLIM_BASE / "stanton" / "stanton2b" / "stanton2b_global_clim.png",
    "stanton3a": CLIM_BASE / "stanton" / "stanton3a" / "stanton3a_global_clim.png",
    "stanton4a": CLIM_BASE / "stanton" / "stanton4a" / "stanton4a_clim.png",
    "stanton4b": CLIM_BASE / "stanton" / "stanton4b" / "stanton4b_clim.png",
    "pyro1":  CLIM_BASE / "pyro" / "pyro1"  / "pyro1_clim.png",
    "pyro2":  CLIM_BASE / "pyro" / "pyro2"  / "pyro2_clim.png",
    "pyro3":  CLIM_BASE / "pyro" / "pyro3"  / "pyro3_clim.png",
    "pyro4":  CLIM_BASE / "pyro" / "pyro4"  / "pyro4_clim.png",
    "pyro5a": CLIM_BASE / "pyro" / "pyro5a" / "pyro5a_clim.png",
    "pyro5b": CLIM_BASE / "pyro" / "pyro5b" / "pyro5b_clim.png",
    "pyro5c": CLIM_BASE / "pyro" / "pyro5c" / "pyro5c_clim.png",
    "pyro5d": CLIM_BASE / "pyro" / "pyro5d" / "pyro5d_clim.png",
    "pyro5e": CLIM_BASE / "pyro" / "pyro5e" / "pyro5e_clim.png",
    "pyro5f": CLIM_BASE / "pyro" / "pyro5f" / "pyro5f_clim.png",
    "pyro6":  CLIM_BASE / "pyro" / "pyro6"  / "pyro6_clim.png",
}


def box_blur(arr: np.ndarray, radius: int) -> np.ndarray:
    k = 2 * radius + 1
    f = arr.astype(np.float32)
    cs = np.cumsum(f, axis=1)
    cs = np.pad(cs, ((0,0),(1,0)), mode="constant")
    h = (cs[:, k:] - cs[:, :-k]) / k
    cs2 = np.cumsum(h, axis=0)
    cs2 = np.pad(cs2, ((1,0),(0,0)), mode="constant")
    return (cs2[k:, :] - cs2[:-k, :]) / k


def make_clim_zone_png(clim_path: Path, zone_type: str, threshold: int,
                       out_path: Path, target_size: tuple[int,int] = (512, 256)):
    img = Image.open(clim_path)
    arr = np.array(img)
    G = arr[:, :, 1].astype(np.float32)

    if zone_type == "polar":
        mask = (G < threshold).astype(np.float32)
    elif zone_type == "equatorial":
        mask = (G > threshold).astype(np.float32)
    elif zone_type == "polar_inverted":
        # G high = polar (Terminus/pyro6)
        mask = (G > threshold).astype(np.float32)
    else:
        raise ValueError(f"Unknown zone_type: {zone_type}")

    # Blur to soften edges (3 passes)
    for _ in range(3):
        mask = box_blur(mask, 4)

    mx = mask.max()
    if mx > 0:
        mask = mask / mx

    alpha = (mask * 255).clip(0, 255).astype(np.uint8)

    h, w = alpha.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, 0] = 255
    rgba[:, :, 1] = 255
    rgba[:, :, 2] = 255
    rgba[:, :, 3] = alpha

    out_img = Image.fromarray(rgba, "RGBA")
    tw, th = target_size
    out_img = out_img.resize((tw, th), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path, "PNG", optimize=True)

    nonzero = int(np.count_nonzero(alpha))
    total = alpha.size
    print(f"  -> {out_path.name}  ({nonzero}/{total} px = {100*nonzero/total:.1f}% coverage)")


def main():
    for stem, zones in BODY_ZONES.items():
        clim_path = CLIM_PATHS.get(stem)
        if not clim_path or not clim_path.exists():
            print(f"[{stem}] SKIP — clim PNG not found")
            continue

        print(f"\n[{stem}]")
        for tag, zone_type, threshold, minerals in zones:
            out_path = OUT_DIR / f"{stem}_zone_{tag}.png"
            print(f"  zone '{tag}' type={zone_type} threshold={threshold}")
            make_clim_zone_png(clim_path, zone_type, threshold, out_path)
            print(f"     minerals: {minerals}")


if __name__ == "__main__":
    main()
