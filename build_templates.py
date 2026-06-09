"""
Run once to build digit templates from a known screenshot.
Usage: python build_templates.py <screenshot.png>
"""
import sys
import numpy as np
from PIL import Image
from src.panel_detector import mask_orange, to_bw
from src.digit_reader import build_templates_from_known, TEMPLATES_DIR, _segment_chars

def extract_1_from_16(arr, orange_bw):
    """
    '16.11%' segments as 5 glyphs instead of 6 because '11' fuses.
    Extract '1' from '16' which segments cleanly as 2 glyphs.
    """
    # '16' is the first two chars of '16.11%' at y=846-860, x=1638-1676
    strip = orange_bw[846:860, 1638:1676]
    glyphs = _segment_chars(strip)
    # The first glyph should be '1', second '6'
    # Verify by checking that '6' template matches glyph[1]
    if len(glyphs) >= 2:
        # glyph[0] is '1', glyph[1] is '6'
        glyph_1 = glyphs[0]
        print(f"  Extracted '1' from '16': {glyph_1.shape[1]}x{glyph_1.shape[0]}px")
        return glyph_1
    return None

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else r"F:\SC_temp\sc_hud_full.png"
    img = Image.open(path)
    arr = np.array(img)
    orange_bw = to_bw(mask_orange(arr))

    # Known labeled regions (x0, y0, x1, y1, label)
    known = [
        (1770, 806, 1790, 820, "654"),
        (1770, 820, 1790, 833, "253"),
        (1770, 833, 1790, 846, "439"),
        (1770, 846, 1790, 860, "0"),
        (1638, 806, 1676, 820, "3.80%"),
        (1638, 820, 1676, 833, "72.27%"),
        (1638, 833, 1676, 846, "0.80%"),
        # Skip '16.11%' — handled separately below
    ]

    print(f"Building templates from {path}")
    print(f"Output: {TEMPLATES_DIR}\n")

    print("Segmentation check:")
    for x0, y0, x1, y1, label in known:
        strip = orange_bw[y0:y1, x0:x1]
        glyphs = _segment_chars(strip)
        status = "OK" if len(glyphs) == len(label) else f"MISMATCH (got {len(glyphs)}, expected {len(label)})"
        print(f"  {label!r:12s} -> {len(glyphs)} glyphs  [{status}]")

    print()
    build_templates_from_known(arr, known)

    # Manually extract '1' from '16'
    print("\nExtracting '1' template from '16'...")
    glyph_1 = extract_1_from_16(arr, orange_bw)
    if glyph_1 is not None:
        import json
        from pathlib import Path
        out_path = TEMPLATES_DIR / f"char_{ord('1'):03d}.png"
        Image.fromarray(glyph_1).save(out_path)
        # Update meta.json
        meta_path = TEMPLATES_DIR / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta['1'] = {"file": str(out_path), "ord": ord('1')}
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"  Template '1' saved to {out_path}")
    else:
        print("  Could not extract '1' template")

if __name__ == "__main__":
    main()
