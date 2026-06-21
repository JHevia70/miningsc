#!/usr/bin/env python3
"""
process_ui_starmap.py
=====================
Resizes UI starmap PNGs to web-ready size and copies to web public dir.

Source: F:/SC_temp/ui_starmap/.../ui_sm_*.png  (4096x4096 or 2048x1024)
Target: H:/Projects/SC/web/public/images/planets/<stem>.png at 1024x512

Mapping is defined in SOURCE_MAP below. Delamar uses a different source path
(Data/Textures/planets/global/nyx/delamar/) since it has no UI starmap texture.
"""

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: pip install pillow")
    sys.exit(1)

UI_DIR   = Path(r"F:\SC_temp\ui_starmap\Data\UI\starmap\textures")
NYX_DIR  = Path(r"F:\SC_temp\ui_starmap\Data\Textures\planets\global\nyx")
OUT_DIR  = Path(r"H:\Projects\SC\web\public\images\planets")
TARGET_W, TARGET_H = 1024, 512

# Maps source PNG (relative to UI_DIR) -> output stem
SOURCE_MAP = {
    # --- Stanton ---
    "Stanton/ui_sm_stanton_1_hurston.png":          "stanton1",       # Hurston planet
    "Stanton/ui_sm_stanton_1a_hurston_arial.png":   "stanton1a",      # Arial
    "Stanton/ui_sm_stanton_1b_hurston_aberdeen.png":"stanton1b",      # Aberdeen
    "Stanton/ui_sm_stanton_1c_hurston_magda.png":   "stanton1c",      # Magda
    "Stanton/ui_sm_stanton_1d_hurston_ita.png":     "stanton1d",      # Ita
    "Stanton/ui_sm_stanton_2_crusader.png":          "stanton2",       # Crusader (gas giant)
    "Stanton/ui_sm_stanton_2a_crusader_cellin.png": "stanton2a",      # Cellin
    "Stanton/ui_sm_stanton_2b_crusader_daymar.png": "stanton2b",      # Daymar
    "Stanton/ui_sm_stanton_2c_crusader_yela.png":   "stanton2c",      # Yela
    "Stanton/ui_sm_stanton_3_arccorp.png":           "stanton3",       # ArcCorp
    "Stanton/ui_sm_stanton_3a_arccorp_lyria.png":   "stanton3a",      # Lyria
    "Stanton/ui_sm_stanton_3b_arccorp_wala.png":    "stanton3b",      # Wala
    "Stanton/ui_sm_stanton_4_microtech.png":         "stanton4",       # microTech
    "Stanton/ui_sm_stanton_4a_microtech_calliope.png": "stanton4a",   # Calliope
    "Stanton/ui_sm_stanton_4b_microtech_clio.png":  "stanton4b",      # Clio
    "Stanton/ui_sm_stanton_4c_microtech_euterpe.png": "stanton4c",    # Euterpe
    # --- Pyro ---
    "Pyro/ui_sm_pyro_1.png":  "pyro1",    # Pyro I
    "Pyro/ui_sm_pyro_2.png":  "pyro2",    # Monox (Pyro II)
    "Pyro/ui_sm_pyro_3.png":  "pyro3",    # Pyro III
    "Pyro/ui_sm_pyro_4.png":  "pyro4",    # Bloom (Pyro V moon)
    "Pyro/ui_sm_pyro_5a.png": "pyro5",    # Pyro V (gas giant) — 5a = the planet itself
    "Pyro/ui_sm_pyro_5b.png": "pyro5a",   # Ignis
    "Pyro/ui_sm_pyro_5c.png": "pyro5b",   # Vatra
    "Pyro/ui_sm_pyro_5d.png": "pyro5c",   # Adir
    "Pyro/ui_sm_pyro_5e.png": "pyro5e",   # (extra moon if added later)
    "Pyro/ui_sm_pyro_5f.png": "pyro5f",   # (extra moon if added later)
    "Pyro/ui_sm_pyro_6.png":  "pyro6",    # Pyro VI
    # --- Nyx ---
    "Nyx/ui_sm_nyx_1.png": "nyx1",        # Nyx I
    "Nyx/ui_sm_nyx_2.png": "nyx2",        # Nyx II
    "Nyx/ui_sm_nyx_3.png": "nyx3",        # Nyx III
}

# Delamar uses a separate path (no UI starmap texture)
DELAMAR_SRC = NYX_DIR / "delamar" / "delamar_global_starmap_diff.png"
DELAMAR_OUT = OUT_DIR / "delamar.png"


def process(src: Path, stem: str, out: Path):
    if not src.exists():
        print(f"  SKIP {src.name} (not found)")
        return
    img = Image.open(src)
    img = img.convert("RGB")
    if img.size != (TARGET_W, TARGET_H):
        img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    img.save(out, "PNG", optimize=True)
    size_kb = out.stat().st_size // 1024
    print(f"  {out.name}  {img.size}  {size_kb} KB")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Processing {len(SOURCE_MAP) + 1} textures -> {OUT_DIR}")
    for src_rel, stem in SOURCE_MAP.items():
        src = UI_DIR / src_rel.replace("/", "\\")
        out = OUT_DIR / f"{stem}.png"
        process(src, stem, out)
    # Delamar special case
    process(DELAMAR_SRC, "delamar", DELAMAR_OUT)
    print("Done.")


if __name__ == "__main__":
    main()
