"""
Digit recognition via template matching for Star Citizen's HUD font.

The HUD uses a fixed bitmap font where each digit has a consistent shape.
We build templates from the first scan and match them by normalized
cross-correlation. Much more reliable than Tesseract for small pixel fonts.
"""

import numpy as np
from PIL import Image
from pathlib import Path
import json
import re

def _base_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent

TEMPLATES_DIR = _base_dir() / "data" / "digit_templates"

# Each character occupies roughly this many pixels wide in the HUD font
# (varies slightly per glyph, so we use sliding window matching)
CHAR_HEIGHT_RANGE = (8, 16)   # expected line height in original resolution
DIGIT_CHARS = "0123456789.%"


# ---------------------------------------------------------------------------
# Template building (run once to create reference templates)
# ---------------------------------------------------------------------------

def build_templates_from_known(
    image_arr: np.ndarray,
    known: list[tuple[int, int, int, int, str]],
    out_dir: Path = TEMPLATES_DIR,
):
    """
    Build per-digit templates from known labeled regions.

    known: list of (x0, y0, x1, y1, label) where label is the text shown
           e.g. (1770, 806, 1790, 820, "654")
    Saves one PNG per unique character glyph to out_dir.
    """
    from .panel_detector import mask_orange, to_bw

    out_dir.mkdir(parents=True, exist_ok=True)
    orange_bw = to_bw(mask_orange(image_arr))

    char_imgs: dict[str, list[np.ndarray]] = {}

    for x0, y0, x1, y1, label in known:
        strip = orange_bw[y0:y1, x0:x1]
        glyphs = _segment_chars(strip)
        if len(glyphs) != len(label):
            print(f"  [warn] {label!r}: expected {len(label)} glyphs, got {len(glyphs)}")
            continue
        for char, glyph in zip(label, glyphs):
            if char not in char_imgs:
                char_imgs[char] = []
            char_imgs[char].append(glyph)

    saved = {}
    for char, imgs in char_imgs.items():
        # Use the clearest (most black pixels relative to size) instance
        best = max(imgs, key=lambda g: np.sum(g == 0) / max(g.size, 1))
        fname = out_dir / f"char_{ord(char):03d}.png"
        Image.fromarray(best).save(fname)
        saved[char] = str(fname)
        print(f"  Template '{char}' saved ({best.shape[1]}x{best.shape[0]}px)")

    # Save metadata
    meta = {c: {"file": p, "ord": ord(c)} for c, p in saved.items()}
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Templates saved to {out_dir}")
    return saved


def _segment_chars(strip: np.ndarray, char_width: int = 6) -> list[np.ndarray]:
    """
    Segment a black-on-white strip into individual character images.

    First tries gap-based segmentation (works when chars have 1+ blank columns
    between them). Falls back to fixed-width sliding window when chars are
    touching (as in SC's HUD bitmap font).
    """
    h, w = strip.shape
    col_has_black = np.any(strip == 0, axis=0)

    # --- Gap-based pass ---
    chars_gap = []
    in_char = False
    c_start = 0

    for x in range(w):
        if col_has_black[x] and not in_char:
            in_char = True
            c_start = x
        elif not col_has_black[x] and in_char:
            in_char = False
            glyph = strip[:, c_start:x]
            if glyph.shape[1] >= 1:
                chars_gap.append(glyph)
    if in_char:
        glyph = strip[:, c_start:]
        if glyph.shape[1] >= 1:
            chars_gap.append(glyph)

    # If gap-based gives many thin single glyphs, use them
    if all(g.shape[1] <= char_width + 2 for g in chars_gap) and len(chars_gap) > 1:
        return chars_gap

    # --- Fixed-width sliding window fallback ---
    # Find the start of actual text (first black column)
    first_black = next((x for x in range(w) if col_has_black[x]), None)
    last_black  = next((x for x in range(w - 1, -1, -1) if col_has_black[x]), None)
    if first_black is None:
        return []

    text_w = last_black - first_black + 1
    n_chars = max(1, round(text_w / char_width))
    actual_cw = text_w // n_chars

    chars_fixed = []
    for i in range(n_chars):
        x0 = first_black + i * actual_cw
        x1 = x0 + actual_cw
        chars_fixed.append(strip[:, x0:x1])

    # Return whichever method gives more glyphs
    return chars_fixed if len(chars_fixed) >= len(chars_gap) else chars_gap


# ---------------------------------------------------------------------------
# Template loading and matching
# ---------------------------------------------------------------------------

_template_cache: dict[str, np.ndarray] = {}

def _load_templates() -> dict[str, np.ndarray]:
    global _template_cache
    if _template_cache:
        return _template_cache

    meta_path = TEMPLATES_DIR / "meta.json"
    if not meta_path.exists():
        return {}

    meta = json.loads(meta_path.read_text())
    for char, info in meta.items():
        img = Image.open(info["file"]).convert("L")
        _template_cache[char] = np.array(img)

    return _template_cache


_NORM_W = 10
_NORM_H = 14

def _match_score(glyph: np.ndarray, template: np.ndarray) -> float:
    """
    Similarity score between glyph and template using normalized SAD.
    Both are resized to (_NORM_W x _NORM_H) using LANCZOS then binarized.
    Returns 0.0-1.0 (higher = better match).
    """
    if glyph.size == 0 or template.size == 0:
        return 0.0

    from PIL import Image as PILImage
    g = np.array(PILImage.fromarray(glyph).resize(
        (_NORM_W, _NORM_H), PILImage.LANCZOS)) / 255.0
    t = np.array(PILImage.fromarray(template).resize(
        (_NORM_W, _NORM_H), PILImage.LANCZOS)) / 255.0

    # SAD on continuous values (more robust than binary threshold at small sizes)
    sad = np.sum(np.abs(g - t))
    max_sad = _NORM_W * _NORM_H  # max possible SAD (all pixels differ by 1.0)
    return float(1.0 - sad / max_sad)


def read_number_strip(strip: np.ndarray, expected_chars: str = "0123456789.%") -> str:
    """
    Read a number from a black-on-white strip using CNN classifier.
    Falls back to template matching, then Tesseract, if CNN unavailable.
    """
    from .digit_cnn import load_model, predict_glyph

    chars = _segment_chars(strip)
    if not chars:
        return ""

    model = load_model()
    if model is not None:
        result = []
        for glyph in chars:
            pred, conf = predict_glyph(glyph)
            if pred in expected_chars and conf >= 0.5:
                result.append(pred)
        return "".join(result)

    # Template matching fallback
    templates = _load_templates()
    if not templates:
        return _tesseract_fallback(strip, expected_chars)

    result = []
    for glyph in chars:
        best_char = "?"
        best_score = 0.0
        for char, tmpl in templates.items():
            if char not in expected_chars:
                continue
            score = _match_score(glyph, tmpl)
            if score > best_score:
                best_score = score
                best_char = char
        if best_score >= 0.35:
            result.append(best_char)

    return "".join(result)


def _tesseract_fallback(strip: np.ndarray, expected_chars: str) -> str:
    """Tesseract fallback for when templates are not built yet."""
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        img = Image.fromarray(strip)
        img = img.resize((img.width * 6, img.height * 6), Image.NEAREST)
        whitelist = re.sub(r'[^0-9.%]', '', expected_chars)
        cfg = f'--psm 8 --oem 3 -c tessedit_char_whitelist={whitelist}'
        return pytesseract.image_to_string(img, config=cfg).strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Convenience parsers
# ---------------------------------------------------------------------------

def parse_quality(strip: np.ndarray) -> int:
    """Read a quality value (0-1000) from a strip."""
    text = read_number_strip(strip, expected_chars="0123456789")
    m = re.search(r'\d+', text)
    return int(m.group()) if m else 0


def parse_percent(strip: np.ndarray) -> float:
    """Read a percentage like 3.80 or 72.27 from a strip."""
    text = read_number_strip(strip, expected_chars="0123456789.")
    m = re.search(r'(\d+)[.,](\d+)', text)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.search(r'\d+', text)
    return float(m.group()) if m else 0.0
