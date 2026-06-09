"""
Detects and reads the RESULTADOS/RESULTS mining panel from a Star Citizen screenshot.

Approach:
- Language-agnostic: no text anchors, pure pixel analysis
- Color-based: orange=numbers+volatile names, white=non-volatile names
- Resolution-independent: all bounds computed relative to detected panel
"""

import numpy as np
import threading
from PIL import Image
from dataclasses import dataclass
from typing import Optional
import re

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MineralLine:
    percent: float
    name: str
    quality: int
    is_inert: bool


@dataclass
class RockScan:
    lines: list[MineralLine]
    mass_scu: float = 0.0   # total rock mass from COMP header (SCU)

    @property
    def best_quality(self) -> int:
        valid = [l.quality for l in self.lines if not l.is_inert and l.quality > 0]
        return max(valid) if valid else 0


# ---------------------------------------------------------------------------
# Color masks
# ---------------------------------------------------------------------------

def mask_orange(arr: np.ndarray) -> np.ndarray:
    """Orange/yellow: numbers and volatile mineral names."""
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    return (r > 180) & (g > 100) & (b < 120) & (r > g) & (g > b)


def mask_white(arr: np.ndarray) -> np.ndarray:
    """White: non-volatile mineral names."""
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    return (r > 200) & (g > 200) & (b > 200)


def to_bw(mask: np.ndarray) -> np.ndarray:
    """Boolean mask -> black-on-white uint8 array."""
    return np.where(mask, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Panel detection
# ---------------------------------------------------------------------------

_ocr_engine = None

def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


_warmup_done = threading.Event()

def warmup():
    """Run a dummy OCR pass to load ONNX models into memory. Call at startup."""
    def _do():
        try:
            engine = _get_ocr_engine()
            # Use a realistic-sized image so all ONNX submodels (det+rec) warm up
            dummy = np.zeros((504, 448, 3), dtype=np.uint8)
            engine(dummy)
        except Exception:
            pass
        finally:
            _warmup_done.set()
    threading.Thread(target=_do, daemon=True).start()

def is_ready() -> bool:
    """Returns True once the OCR engine has finished warming up."""
    return _warmup_done.is_set()


def find_panel_region(arr: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    """
    Returns (x0, y0, x1, y1) of the RESULTADOS/RESULTS mining panel, or None.

    Uses RapidOCR to locate the 'RESULTADOS' / 'RESULTS' header text, then
    expands to encompass the full panel below it.
    """
    h, w = arr.shape[:2]

    # Search right 55% where the panel always appears, full height
    xs = int(w * 0.45)
    crop = arr[:, xs:]

    try:
        engine = _get_ocr_engine()
        result, _ = engine(crop)
        if not result:
            return None

        hdr_box  = None
        load_y   = None   # y of CARGA/LOAD/INTENSIDAD line — natural bottom of panel

        for item in result:
            box, text, conf = item
            conf_f = float(conf) if not isinstance(conf, float) else conf
            pts = np.array(box, dtype=float)
            if re.search(r'RESULT(?:ADOS)?', text, re.IGNORECASE) and conf_f > 0.5:
                hdr_box = pts
            # "CARGA" / "LOAD" alone (not SOBRECARGAR, not NIVEL DE CARGA)
            # marks the charge bar — natural bottom of the panel
            stripped = text.strip().upper()
            if re.fullmatch(r'CARGA|LOAD', stripped) and conf_f > 0.4:
                y_top = int(pts[:, 1].min())
                if load_y is None or y_top < load_y:
                    load_y = y_top

        if hdr_box is not None:
            hdr_x0 = int(hdr_box[:, 0].min()) + xs
            hdr_y0 = int(hdr_box[:, 1].min())
            hdr_x1 = int(hdr_box[:, 0].max()) + xs
            hdr_y1 = int(hdr_box[:, 1].max())
            hdr_h  = max(hdr_y1 - hdr_y0, 12)

            panel_x0 = max(0,     hdr_x0 - int(hdr_h * 1.5))
            panel_x1 = min(w - 1, hdr_x1 + int(hdr_h * 6))
            panel_y0 = max(0,     hdr_y0 - int(hdr_h * 0.5))
            if load_y is not None:
                # Cut just above the INTENSIDAD/LOAD bar
                panel_y1 = min(h - 1, load_y + int(hdr_h * 2))
            else:
                panel_y1 = min(h - 1, hdr_y0 + int(hdr_h * 25))
            return (panel_x0, panel_y0, panel_x1, panel_y1)
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# COMP line detection
# ---------------------------------------------------------------------------

def find_comp_lines(panel_arr: np.ndarray) -> list[tuple[int, int]]:
    """
    Returns (y_start, y_end) for each COMP mineral line in the panel.
    Skips the header section (mineral name, MASA, RES, INST bars, separator).

    The COMP section starts after the last gap >= 4 rows in the top 75% of
    the panel. Each COMP line has >= 2 distinct orange word groups (pct + qual).
    """
    ph, pw = panel_arr.shape[:2]
    orange = mask_orange(panel_arr)
    orange_bw = to_bw(orange)
    row_density = orange.sum(axis=1)

    # Find all row-band groups (contiguous rows with orange content)
    bands = []
    in_band, band_start = False, 0
    for y, d in enumerate(row_density):
        has = d > 2
        if has and not in_band:
            in_band = True; band_start = y
        elif not has and in_band:
            in_band = False
            bands.append((band_start, y))
    if in_band:
        bands.append((band_start, len(row_density)))

    # A COMP line has >= 2 orange word groups separated by a gap >= 5px
    # (at minimum: pct group on left + quality group on right).
    comp_lines = []
    for by0, by1 in bands:
        if (by1 - by0) < 7:   # COMP lines are at least 7px tall
            continue
        strip = orange_bw[by0:by1, :]
        groups = _find_col_groups(strip, min_gap=5)
        # COMP lines have 2-4 orange word groups (pct, maybe name, quality)
        # Header decorations have more fragmented groups
        if 2 <= len(groups) <= 5:
            # Pct group on left side, quality group on right side
            left_ok  = groups[0][0] < pw * 0.35
            right_ok = groups[-1][1] > pw * 0.70
            left_w = groups[0][1] - groups[0][0]
            # Left group is a number like "3.80%" — must be 15-65px wide
            left_narrow = left_w < pw * 0.40
            left_wide_enough = left_w >= 15
            if left_ok and right_ok and left_narrow and left_wide_enough:
                comp_lines.append((by0, by1))

    return comp_lines


# ---------------------------------------------------------------------------
# Column detection within a line
# ---------------------------------------------------------------------------

def _find_col_groups(strip_bw: np.ndarray, min_gap: int = 5) -> list[tuple[int, int]]:
    """
    Return list of (x_start, x_end) word groups in a bw strip.
    Gaps of >= min_gap blank columns separate groups.
    """
    col_has = (strip_bw == 0).any(axis=0)
    groups, in_group, g_start, blank_run = [], False, 0, 0
    for x, has in enumerate(col_has):
        if has:
            if not in_group:
                in_group = True; g_start = x
            blank_run = 0
        else:
            if in_group:
                blank_run += 1
                if blank_run >= min_gap:
                    groups.append((g_start, x - blank_run))
                    in_group = False; blank_run = 0
    if in_group:
        groups.append((g_start, len(col_has) - 1))
    return groups


# ---------------------------------------------------------------------------
# Mineral name OCR  (Tesseract on white+orange text, scaled up)
# ---------------------------------------------------------------------------

def _ocr_name(strip_arr: np.ndarray) -> str:
    """Read mineral name from a BGR crop using Tesseract."""
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        # Build a white+orange combined mask for the name column
        bw = to_bw(mask_orange(strip_arr) | mask_white(strip_arr))
        img = Image.fromarray(bw)
        img = img.resize((img.width * 4, img.height * 4), Image.LANCZOS)
        cfg = '--psm 7 --oem 3'
        return pytesseract.image_to_string(img, config=cfg).strip()
    except Exception:
        return ""


INERT_TOKENS = {"INERT", "INERTE", "MATERIAL INERTE", "MATERIAL INERT",
                "MATERIAL", "INERTITE"}


def _is_inert(name: str) -> bool:
    up = name.upper()
    return any(tok in up for tok in INERT_TOKENS)


# ---------------------------------------------------------------------------
# Main read_panel
# ---------------------------------------------------------------------------

def _find_pct_value(pct_scan: np.ndarray) -> Optional[float]:
    """
    Parse a percentage value (e.g. 3.80, 72.27) from a strip that contains
    pct text somewhere to the right side (strip = panel_x0-85 to panel_x0+50).

    Strategy:
    1. Find '%' by sliding window (widths 6-10) on the rightmost run, right-to-left.
    2. Read digit chars immediately before the '%' from the assembled run sequence.
    3. Extract the rightmost valid D.DD / DD.DD pattern from those chars.
    """
    from .digit_cnn import load_model, predict_glyph
    from .digit_reader import _segment_chars

    load_model()

    h, w = pct_scan.shape
    if w < 4:
        return None

    col_has = (pct_scan == 0).any(axis=0)
    raw_runs = []
    in_run, r_start = False, 0
    for x, has in enumerate(col_has):
        if has and not in_run:
            in_run = True; r_start = x
        elif not has and in_run:
            in_run = False
            raw_runs.append((r_start, x - 1))
    if in_run:
        raw_runs.append((r_start, w - 1))

    if not raw_runs:
        return None

    # Merge 1-px gaps (dot fragmentation)
    runs = [raw_runs[0]]
    for rs, rend in raw_runs[1:]:
        if rs - runs[-1][1] <= 1:
            runs[-1] = (runs[-1][0], rend)
        else:
            runs.append((rs, rend))

    # Step 1: find '%' in the rightmost run using sliding window (width 6-10px),
    # scanning right-to-left so we find the rightmost occurrence first.
    rs_last, rend_last = runs[-1]

    pct_abs_start = None  # absolute x in pct_scan where % starts
    for x_end in range(rend_last, rs_last - 1, -1):
        for win_w in range(6, 11):
            x_start = x_end - win_w + 1
            if x_start < rs_last:
                continue
            sg = pct_scan[:, x_start:x_end + 1]
            pred, conf = predict_glyph(sg)
            if pred == '%' and conf >= 0.70:
                pct_abs_start = x_start
                break
        if pct_abs_start is not None:
            break

    # Step 2: collect digit chars preceding '%'.
    # Only consider runs within 40px of the '%' to exclude distant HUD noise.
    # Skip 1px runs (fragmentation noise).
    # Single chars are ≤9px wide; blobs wider than that are treated as multi-char.
    CHAR_MAX_W = 9
    MAX_DIST_FROM_PCT = 40  # digits can't be more than ~5 chars × 7px away from %

    def _build_char_seq(clip_x):
        """Build char_seq clipping digit runs at clip_x (exclusive)."""
        seq = []
        for rs, rend in runs:
            if clip_x is not None and rs >= clip_x:
                break
            rend_c = min(rend, (clip_x - 1) if clip_x is not None else rend)
            clip_w = rend_c - rs + 1
            if clip_x is not None and (clip_x - rend_c) > MAX_DIST_FROM_PCT:
                continue
            if clip_w <= 1 and clip_x is not None:
                dist = clip_x - rend_c
                if dist > 20 or dist <= 2:
                    continue
            block = pct_scan[:, rs:rend_c + 1]
            if (block == 0).sum() < 2:
                continue
            if clip_w <= CHAR_MAX_W:
                pred, conf = predict_glyph(block)
                seq.append((pred, conf))
            else:
                seq.append(('__WIDE__', 0.0, block))
        return seq

    # Step 3: read up to 5 digit/dot chars backwards from the end of char_seq.
    def _extract_number(flat_preds):
        """Try to extract D.DD or DD.DD from a flat (pred,conf) list."""
        digits = []
        for pred, conf in reversed(flat_preds):
            if conf < 0.4:
                continue
            if pred in '0123456789.':
                digits.append(pred)
                if len(digits) >= 5:
                    break
            else:
                break
        digits.reverse()
        text = ''.join(digits)

        for start in range(len(text)):
            m = re.fullmatch(r'(\d{1,2})\.(\d{2})', text[start:])
            if m:
                val = float(f"{m.group(1)}.{m.group(2)}")
                if 0.0 <= val <= 99.99:
                    return val

        return None

    def _get_flat(seq, cw):
        flat = []
        for item in seq:
            if item[0] == '__WIDE__':
                block = item[2]
                for sg in _segment_chars(block, char_width=cw):
                    flat.append(predict_glyph(sg))
            else:
                flat.append(item[:2])
        return flat

    def _collect_text(flat, max_chars=5):
        digits = []
        for pred, conf in reversed(flat):
            if conf < 0.4:
                continue
            if pred in '0123456789.':
                digits.append(pred)
                if len(digits) >= max_chars:
                    break
            else:
                break
        digits.reverse()
        return ''.join(digits)

    # Pass 1: strict D.DD matching across all clip offsets and char widths.
    # Vary clip_x by ±2px to tolerate % detection offset.
    # For each (clip_x, cw): if cw=6 gives only pure digits (no '.') with 4 total
    # digits, immediately infer DD.DD before cw=5 can produce a spurious D.DD match.
    clip_offsets = [0, -1, -2, 1, 2] if pct_abs_start is not None else [0]
    tried_clips = set()
    for offset in clip_offsets:
        clip_x = (pct_abs_start + offset) if pct_abs_start is not None else None
        if clip_x in tried_clips:
            continue
        tried_clips.add(clip_x)
        char_seq = _build_char_seq(clip_x)
        if not char_seq:
            continue

        # Try cw=6 first. If it gives exactly 4 pure digits (no dot), the decimal
        # is missing from the pixel data — infer DD.DD before trying smaller cw.
        flat6 = _get_flat(char_seq, 6)
        result = _extract_number(flat6)
        if result is not None:
            return result
        text6 = _collect_text(flat6)
        pure6 = ''.join(c for c in text6 if c.isdigit())
        if len(pure6) == 4 and '.' not in text6 and pure6[0] != '0':
            val = float(f"{pure6[:2]}.{pure6[2:]}")
            if 1.0 <= val <= 99.99:
                return val

        # cw=5 and cw=4 for cases where cw=6 segments too coarsely
        for cw in (5, 4):
            flat = _get_flat(char_seq, cw)
            result = _extract_number(flat)
            if result is not None:
                return result

    # Pass 2: missing-decimal inference for cases where no cw found a strict match.
    for offset in clip_offsets:
        clip_x = (pct_abs_start + offset) if pct_abs_start is not None else None
        char_seq = _build_char_seq(clip_x)
        if not char_seq:
            continue
        for cw in (6, 5, 4):
            text = _collect_text(_get_flat(char_seq, cw))
            pure = ''.join(c for c in text if c.isdigit())
            if len(pure) == 4 and pure[0] != '0':
                val = float(f"{pure[:2]}.{pure[2:]}")
                if 1.0 <= val <= 99.99:
                    return val
            if len(pure) == 3:
                val = float(f"{pure[0]}.{pure[1:]}")
                if 0.0 <= val <= 9.99:
                    return val

    # Last resort: last 1-2 digit integer
    char_seq = _build_char_seq(pct_abs_start)
    flat = _get_flat(char_seq, 6)
    text = _collect_text(flat, max_chars=2)
    pure = ''.join(c for c in text if c.isdigit())
    if pure:
        val = int(pure[-2:]) if len(pure) >= 2 else int(pure)
        if 0 <= val <= 99:
            return float(val)
    return None


def _find_pct_in_full(full_orange_bw: np.ndarray,
                      panel_x0: int, abs_y0: int,
                      line_h: int, _unused: int = 0) -> tuple[float, Optional[int]]:
    """
    Find the percentage value for a COMP line.
    Returns (pct_float, None) — the abs x is no longer needed.
    """
    fh = full_orange_bw.shape[0]
    # ±4px vertical padding helps fixed-width char segmentation
    y0 = max(0, abs_y0 - 4)
    y1 = min(fh, abs_y0 + line_h + 4)
    search_left = max(0, panel_x0 - 85)
    search_right = min(full_orange_bw.shape[1], panel_x0 + 50)
    strip = full_orange_bw[y0:y1, search_left:search_right]
    if strip.shape[1] == 0:
        return 0.0, None

    pct_val = _find_pct_value(strip)
    return (pct_val if pct_val is not None else 0.0), None


_RE_PCT  = re.compile(r'^(\d{1,2}[.,]\d{1,2})%')
_RE_QUAL = re.compile(r'^\d{1,4}$')
_RE_SCU  = re.compile(r'([\d.,]+)\s*S(?:CU|C0|0U|0)', re.IGNORECASE)


def read_panel(panel_arr: np.ndarray,
               full_arr: np.ndarray = None,
               panel_x0: int = 0,
               panel_y0: int = 0) -> Optional[RockScan]:
    """
    Read COMP mineral lines and total mass from the panel using RapidOCR.
    Returns a RockScan with lines and mass_scu, or None if no COMP data found.
    """
    engine = _get_ocr_engine()
    result, _ = engine(panel_arr)
    if not result:
        return None

    ph, pw = panel_arr.shape[:2]
    pct_left_threshold = pw * 0.50

    # Group detections into rows by y-centre proximity
    detections = []
    for item in result:
        box, text, conf = item
        pts = np.array(box, dtype=float)
        detections.append((pts[:, 1].mean(), pts[:, 0].min(), text.strip()))
    detections.sort(key=lambda d: d[0])

    # Group detections into rows — tolerance 14px to handle slight vertical
    # misalignment between tokens on the same COMP line.
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for y_c, x_l, text in detections:
        if rows and abs(rows[-1][0] - y_c) <= 14:
            rows[-1][1].append((x_l, text))
        else:
            rows.append((y_c, [(x_l, text)]))

    from .mineral_names import normalize as _norm

    mass_scu = 0.0
    results  = []
    seen_pct: list[float] = []   # deduplicate rows with same % (OCR double-detects)

    for y_c, tokens in rows:
        sorted_toks = sorted(tokens, key=lambda t: t[0])
        all_text = ' '.join(t for _, t in sorted_toks)

        # Pick up "17.86SCU" / "42.14 SCU" from the COMP header row.
        # Only consider the top 55% of the panel height to avoid reading
        # the charge-bar numbers at the bottom as mass.
        if y_c < ph * 0.55:
            m_scu = _RE_SCU.search(all_text)
            if m_scu:
                try:
                    mass_scu = float(m_scu.group(1).replace(',', '.'))
                except ValueError:
                    pass

        # Find a percentage token anywhere in the row
        pct_val = None
        for x_l, text in sorted_toks:
            m = _RE_PCT.match(text.replace(',', '.'))
            if m:
                try:
                    pct_val = float(m.group(1).replace(',', '.'))
                    break
                except ValueError:
                    pass

        # Quality: rightmost plain integer on right side
        qual_val = 0
        for x_l, text in sorted(tokens, key=lambda t: t[0], reverse=True):
            if x_l > pw * 0.60 and _RE_QUAL.match(text):
                try:
                    qual_val = int(text)
                    break
                except ValueError:
                    pass

        # Mineral name: all tokens except pct and pure quality; strip pct prefix
        name_tokens = []
        for x_l, text in sorted_toks:
            if _RE_QUAL.match(text) and x_l > pw * 0.60:
                continue
            clean = re.sub(r'^\d{1,2}[.,]\d{1,2}%1?\s*', '', text)
            if clean and not _RE_PCT.match(clean):
                name_tokens.append(clean)

        raw_name = ' '.join(name_tokens).upper()
        raw_name = re.sub(r'[^A-Z0-9\s\(\)]', '', raw_name).strip()
        is_inert = _is_inert(raw_name)

        if not is_inert:
            canonical = _norm(raw_name)
            if canonical is None:
                for tok in name_tokens:
                    canonical = _norm(tok.upper())
                    if canonical:
                        break
            mineral = canonical if canonical else "???"
        else:
            mineral = "INERT"

        # Skip rows with neither a valid name nor a quality (noise rows)
        if not mineral and qual_val == 0 and pct_val is None:
            continue

        # Skip duplicate rows (same % already seen within ±0.1)
        if pct_val is not None:
            if any(abs(pct_val - s) < 0.1 for s in seen_pct):
                continue
            seen_pct.append(pct_val)

        results.append(MineralLine(
            percent  = pct_val if pct_val is not None else -1.0,
            name     = mineral,
            quality  = qual_val,
            is_inert = is_inert,
        ))

    if not results:
        return None

    # Post-pass: fill in missing percentages (OCR sometimes misses the % token).
    # The sum of all mineral percentages must equal 100, so if exactly one line
    # is missing its %, compute it as 100 - sum(known).
    missing = [l for l in results if l.percent < 0]
    known_pcts = [l.percent for l in results if l.percent >= 0]
    if len(missing) == 1 and known_pcts:
        missing[0].percent = max(0.0, round(100.0 - sum(known_pcts), 2))

    # Drop any remaining lines with no percentage (couldn't infer it)
    results = [l for l in results if l.percent >= 0]

    if not results:
        return None

    # Post-pass: fix unrecognised names using canonical names already found in
    # this scan (same rock often has the same mineral twice at different qualities).
    known_canons = {l.name for l in results if _norm(l.name) is not None}
    for line in results:
        if line.is_inert or _norm(line.name) is not None:
            continue
        raw_lower = re.sub(r'[^a-z]', '', line.name.lower())
        best_canon, best_score = None, 0.0
        for canon in known_canons:
            cl = canon.lower()
            # Count how many chars of canon appear in raw_lower as subsequence
            si = 0
            for ch in raw_lower:
                if si < len(cl) and ch == cl[si]:
                    si += 1
            score = si / len(cl)
            if score > best_score:
                best_score, best_canon = score, canon
        if best_canon and best_score >= 0.65:
            line.name = best_canon

    return RockScan(lines=results, mass_scu=mass_scu)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def scan_screenshot(image_path: str) -> Optional[RockScan]:
    """
    Full pipeline: load -> single OCR pass on right-half at 50% scale ->
    locate panel -> parse lines. Returns RockScan or None.

    One OCR call instead of two: find_panel_region and read_panel both
    consume the same token list, cutting total OCR time roughly in half.
    Scaling to 50% before OCR reduces pixel count 4× with negligible
    accuracy loss for the large SC HUD text.
    """
    img = Image.open(image_path)
    arr = np.array(img)
    h, w = arr.shape[:2]

    # Panel can appear anywhere in the right half depending on ship/seat.
    # No scaling — small text from high-FOV seats needs full resolution.
    xs = int(w * 0.50)
    ys = int(h * 0.10)
    ye = int(h * 0.98)
    crop = arr[ys:ye, xs:]
    ch, cw = crop.shape[:2]
    small = crop
    scale = 1.0

    engine = _get_ocr_engine()
    result, _ = engine(small)
    if not result:
        return None

    # ---- Phase 1: locate panel boundaries from OCR tokens ----
    hdr_box = None
    load_y  = None

    for item in result:
        box, text, conf = item
        conf_f = float(conf) if not isinstance(conf, float) else conf
        pts = np.array(box, dtype=float) * scale   # back to crop coords
        if re.search(r'E?SULT(?:ADOS)?', text, re.IGNORECASE) and conf_f > 0.5:
            hdr_box = pts
        stripped = text.strip().upper()
        if re.fullmatch(r'CARGA|LOAD', stripped) and conf_f > 0.4:
            y_top = int(pts[:, 1].min())
            if load_y is None or y_top < load_y:
                load_y = y_top

    if hdr_box is None:
        return None

    hdr_x0 = int(hdr_box[:, 0].min())
    hdr_y0 = int(hdr_box[:, 1].min())
    hdr_x1 = int(hdr_box[:, 0].max())
    hdr_y1 = int(hdr_box[:, 1].max())
    hdr_h  = max(hdr_y1 - hdr_y0, 12)

    panel_x0_crop = max(0,      hdr_x0 - int(hdr_h * 1.5))
    panel_x1_crop = min(cw - 1, hdr_x1 + int(hdr_h * 6))
    panel_y0_crop = max(0,      hdr_y0 - int(hdr_h * 0.5))
    if load_y is not None:
        panel_y1_crop = min(ch - 1, load_y + int(hdr_h * 2))
    else:
        panel_y1_crop = min(ch - 1, hdr_y0 + int(hdr_h * 25))

    # Convert crop coords → full-image coords (xs/ys are crop offsets)
    panel_x0 = panel_x0_crop + xs
    panel_y0 = panel_y0_crop + ys

    pw = panel_x1_crop - panel_x0_crop
    ph = panel_y1_crop - panel_y0_crop

    # ---- Phase 2: parse mineral lines from the same OCR tokens ----
    # Filter to tokens that fall within the panel bounding box
    from .mineral_names import normalize as _norm

    detections = []
    for item in result:
        box, text, conf = item
        pts = np.array(box, dtype=float) * scale
        yc = pts[:, 1].mean()
        xc = pts[:, 0].mean()
        if (panel_x0_crop <= xc <= panel_x1_crop and
                panel_y0_crop <= yc <= panel_y1_crop):
            detections.append((yc - panel_y0_crop, pts[:, 0].min() - panel_x0_crop, text.strip()))

    detections.sort(key=lambda d: d[0])

    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for y_c, x_l, text in detections:
        if rows and abs(rows[-1][0] - y_c) <= 14:
            rows[-1][1].append((x_l, text))
        else:
            rows.append((y_c, [(x_l, text)]))

    mass_scu = 0.0
    results: list[MineralLine] = []
    seen_pct: list[float] = []

    for y_c, tokens in rows:
        sorted_toks = sorted(tokens, key=lambda t: t[0])
        all_text = ' '.join(t for _, t in sorted_toks)

        if y_c < ph * 0.55:
            m_scu = _RE_SCU.search(all_text)
            if m_scu:
                try:
                    mass_scu = float(m_scu.group(1).replace(',', '.'))
                except ValueError:
                    pass

        pct_val = None
        for x_l, text in sorted_toks:
            m = _RE_PCT.match(text.replace(',', '.'))
            if m:
                try:
                    pct_val = float(m.group(1).replace(',', '.'))
                    break
                except ValueError:
                    pass

        qual_val = 0
        for x_l, text in sorted(tokens, key=lambda t: t[0], reverse=True):
            if x_l > pw * 0.60 and _RE_QUAL.match(text):
                try:
                    qual_val = int(text)
                    break
                except ValueError:
                    pass

        name_tokens = []
        for x_l, text in sorted_toks:
            if _RE_QUAL.match(text) and x_l > pw * 0.60:
                continue
            clean = re.sub(r'^\d{1,2}[.,]\d{1,2}%1?\s*', '', text)
            if clean and not _RE_PCT.match(clean):
                name_tokens.append(clean)

        raw_name = ' '.join(name_tokens).upper()
        raw_name = re.sub(r'[^A-Z0-9\s\(\)]', '', raw_name).strip()
        is_inert = _is_inert(raw_name)

        if not is_inert:
            canonical = _norm(raw_name)
            if canonical is None:
                for tok in name_tokens:
                    canonical = _norm(tok.upper())
                    if canonical:
                        break
            mineral = canonical if canonical else "???"
        else:
            mineral = "INERT"

        if not mineral and qual_val == 0 and pct_val is None:
            continue

        if pct_val is not None:
            if any(abs(pct_val - s) < 0.1 for s in seen_pct):
                continue
            seen_pct.append(pct_val)

        results.append(MineralLine(
            percent  = pct_val if pct_val is not None else -1.0,
            name     = mineral,
            quality  = qual_val,
            is_inert = is_inert,
        ))

    if not results:
        return None

    missing   = [l for l in results if l.percent < 0]
    known_pcts = [l.percent for l in results if l.percent >= 0]
    if len(missing) == 1 and known_pcts:
        missing[0].percent = max(0.0, round(100.0 - sum(known_pcts), 2))

    results = [l for l in results if l.percent >= 0]
    if not results:
        return None

    known_canons = {l.name for l in results if _norm(l.name) is not None}
    for line in results:
        if line.is_inert or _norm(line.name) is not None:
            continue
        raw_lower = re.sub(r'[^a-z]', '', line.name.lower())
        best_canon, best_score = None, 0.0
        for canon in known_canons:
            cl = canon.lower()
            si = 0
            for ch in raw_lower:
                if si < len(cl) and ch == cl[si]:
                    si += 1
            score = si / len(cl)
            if score > best_score:
                best_score, best_canon = score, canon
        if best_canon and best_score >= 0.65:
            line.name = best_canon

    return RockScan(lines=results, mass_scu=mass_scu)


if __name__ == "__main__":
    import sys
    paths = sys.argv[1:] or [r"F:\SC_temp\sc_hud_full.png"]
    for path in paths:
        print(f"\n=== {path} ===")
        scan = scan_screenshot(path)
        if scan:
            print(f"  Mass: {scan.mass_scu} SCU")
            for l in scan.lines:
                flag = " [INERT]" if l.is_inert else ""
                print(f"  {l.percent:6.2f}%  {l.name:<30}  Q={l.quality}{flag}")
            print(f"  >> best quality: {scan.best_quality}")
        else:
            print("  No lines found.")
