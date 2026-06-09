#!/usr/bin/env python3
"""
analyze_clims.py
================
Analyzes extracted clim PNGs (RGBA) to understand channel distributions.
For each planet, prints per-channel stats + polar vs equatorial value patterns.

Usage:
  python analyze_clims.py
"""

import sys
from pathlib import Path
import numpy as np
try:
    from PIL import Image
except ImportError:
    print("ERROR: pip install pillow"); sys.exit(1)

CLIM_BASE = Path(r"F:\SC_temp\clims\Data\Textures\planets\global")

# body_key -> (system_subdir, filename_stem)
BODIES = {
    # Stanton
    "stanton1a": ("stanton/stanton1a", "stanton1a_global_clim"),
    "stanton1b": ("stanton/stanton1b", "stanton1b_global_clim"),
    "stanton1c": ("stanton/stanton1c", "stanton1c_global_clim"),
    "stanton1d": ("stanton/stanton1d", "stanton1d_global_clim"),
    "stanton2a": ("stanton/stanton2a", "stanton2a_global_clim"),
    "stanton2b": ("stanton/stanton2b", "stanton2b_global_clim"),
    "stanton2c": ("stanton/stanton2c", "stanton2c_global_clim"),
    "stanton3a": ("stanton/stanton3a", "stanton3a_global_clim"),
    "stanton3b": ("stanton/stanton3b", "stanton3b_global_clim"),
    "stanton4a": ("stanton/stanton4a", "stanton4a_clim"),
    "stanton4b": ("stanton/stanton4b", "stanton4b_clim"),
    "stanton4c": ("stanton/stanton4c", "stanton4c_clim"),
    # Pyro
    "pyro1":  ("pyro/pyro1",  "pyro1_clim"),
    "pyro2":  ("pyro/pyro2",  "pyro2_clim"),
    "pyro3":  ("pyro/pyro3",  "pyro3_clim"),
    "pyro4":  ("pyro/pyro4",  "pyro4_clim"),
    "pyro5a": ("pyro/pyro5a", "pyro5a_clim"),
    "pyro5b": ("pyro/pyro5b", "pyro5b_clim"),
    "pyro5c": ("pyro/pyro5c", "pyro5c_clim"),
    "pyro5d": ("pyro/pyro5d", "pyro5d_clim"),
    "pyro5e": ("pyro/pyro5e", "pyro5e_clim"),
    "pyro5f": ("pyro/pyro5f", "pyro5f_clim"),
    "pyro6":  ("pyro/pyro6",  "pyro6_clim"),
}

CHANNEL_NAMES = ["R", "G", "B", "A"]


def analyze(arr: np.ndarray, name: str):
    """Print per-channel stats and polar vs equatorial comparison."""
    h, w = arr.shape[:2]
    n_ch = arr.shape[2] if arr.ndim == 3 else 1
    print(f"\n{'='*60}")
    print(f"  {name}  ({w}x{h}, {n_ch} channels)")
    print(f"{'='*60}")

    for c in range(n_ch):
        ch = arr[:, :, c] if n_ch > 1 else arr
        mn, mx, mean = int(ch.min()), int(ch.max()), float(ch.mean())
        unique = len(np.unique(ch))
        # Polar rows = top 10% + bottom 10% rows
        pole_rows = max(1, h // 10)
        polar = np.concatenate([ch[:pole_rows, :].ravel(), ch[-pole_rows:, :].ravel()])
        equator_rows = slice(h * 2 // 5, h * 3 // 5)
        equatorial = ch[equator_rows, :].ravel()
        p_mean = float(polar.mean())
        e_mean = float(equatorial.mean())
        print(f"  Ch {CHANNEL_NAMES[c]}: min={mn:3d} max={mx:3d} mean={mean:6.1f}  "
              f"polar_mean={p_mean:6.1f}  equator_mean={e_mean:6.1f}  "
              f"unique={unique}  diff={abs(p_mean-e_mean):.1f}")

    # Find channel with maximum polar/equatorial contrast
    if n_ch >= 2:
        best_ch, best_diff = 0, 0.0
        for c in range(n_ch):
            ch = arr[:, :, c]
            pole_rows = max(1, h // 10)
            polar = np.concatenate([ch[:pole_rows, :].ravel(), ch[-pole_rows:, :].ravel()])
            equatorial = ch[h*2//5:h*3//5, :].ravel()
            diff = abs(float(polar.mean()) - float(equatorial.mean()))
            if diff > best_diff:
                best_diff = diff
                best_ch = c
        print(f"  >> Best polar-contrast channel: {CHANNEL_NAMES[best_ch]} (diff={best_diff:.1f})")


def main():
    for key, (subdir, stem) in BODIES.items():
        path = CLIM_BASE / subdir.replace("/", "\\") / f"{stem}.png"
        if not path.exists():
            print(f"[{key}] MISSING: {path}")
            continue
        img = Image.open(path)
        arr = np.array(img)
        analyze(arr, key)


if __name__ == "__main__":
    main()
