"""
Reads location data from the Star Citizen r_displayinfo HUD (top-right corner).

Requires r_displayinfo 3 to be active in-game (bind to a key via console).
Uses RapidOCR (ONNX, no external binaries) — fully self-contained.

Parsed fields:
  Zone: OOC <System> <N> <Body> Pos: ...
  Planet:OOC <System> <N> <Body> (working)
  CamPos.Planet Zone: <x> <y> <z>   (metres from planet centre)
  Altitude: <m>
"""

import re
import numpy as np
from dataclasses import dataclass
from typing import Optional
from PIL import Image

# ---------------------------------------------------------------------------
# RapidOCR engine — lazy singleton
# ---------------------------------------------------------------------------

_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class LocationInfo:
    system: str                  # e.g. "Stanton"
    body: str                    # e.g. "Hurston"
    altitude_m: float            # metres above surface
    coord_x: Optional[float]     # km from planet centre (CamPos X)
    coord_y: Optional[float]     # km from planet centre (CamPos Y)
    coord_z: Optional[float]     # km from planet centre (CamPos Z)
    raw: str                     # OCR text for debugging


_SYSTEM_ALIASES = {
    "stanton": "Stanton",
    "pyro":    "Pyro",
    "nyx":     "Nyx",
}

_BODY_CANON = {
    "hurston":    "Hurston",
    "crusader":   "Crusader",
    "arccorp":    "ArcCorp",
    "microtech":  "microTech",
    "aberdeen":   "Aberdeen",
    "magda":      "Magda",
    "ita":        "Ita",
    "wala":       "Wala",
    "cellin":     "Cellin",
    "daymar":     "Daymar",
    "yela":       "Yela",
    "euterpe":    "Euterpe",
    "calliope":   "Calliope",
    "clio":       "Clio",
    "lyria":      "Lyria",
    "aaronhalo":  "Aaron Halo",
    "pyroi":      "Pyro I",
    "monox":      "Monox",
    "pyroiii":    "Pyro III",
    "bloom":      "Bloom",
    "pyrov":      "Pyro V",
    "terminus":   "Terminus",
    "fuego":      "Fuego",
    "adir":       "Adir",
    "delamar":    "Delamar",
}


def _canon_body(raw: str) -> Optional[str]:
    key = re.sub(r'[^a-z]', '', raw.lower())   # strip all non-alpha (underscores, digits, etc.)
    if key in _BODY_CANON:
        return _BODY_CANON[key]
    return None


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------

def _extract_hud_region(arr: np.ndarray) -> np.ndarray:
    """
    Crop the top-right corner where r_displayinfo renders.
    Returns an RGB uint8 array (RapidOCR works best with colour).
    The block spans top ~35% height, rightmost ~28% width.
    """
    h, w = arr.shape[:2]
    x0 = int(w * 0.72)
    y1 = int(h * 0.35)
    return arr[0:y1, x0:w]


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def _ocr(arr: np.ndarray) -> str:
    """Run RapidOCR and return all detected text joined by newlines."""
    engine = _get_engine()
    result, _ = engine(arr)
    if not result:
        return ""
    return "\n".join(line[1] for line in result)


# ---------------------------------------------------------------------------
# Normalisation — fix RapidOCR substitutions specific to this HUD font
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    # RapidOCR reads '5' for 'S', '0' for 'O', '1' for 'l' in this monospace font
    # Fix "00c" / "0oc" → "OOC"  (common in Zone/Planet lines)
    text = re.sub(r'\b[0O][0Oc][cC]\b', 'OOC', text)
    # "5tanton" → "Stanton", "5olar" → "Solar"
    text = re.sub(r'\b5tanton\b', 'Stanton', text, flags=re.IGNORECASE)
    text = re.sub(r'\b5olar\b',   'Solar',   text, flags=re.IGNORECASE)
    # CamPos line: "CamPosplanetZone:" or "CamPos.PlanetZone:" → normalise
    text = re.sub(r'CamPos\.?[Pp]lanet\.?[Zz]one\s*:?\s*', 'CamPos.Planet Zone: ', text)
    # planet:ooc / planet:00c
    text = re.sub(r'planet\s*:\s*[0O][0Oo][cC]\s*', 'Planet:OOC ', text, flags=re.IGNORECASE)
    # Zone:00c / Zone:0oc
    text = re.sub(r'Zone\s*:\s*[0O][0Oo][cC]\s*', 'Zone: OOC ', text, flags=re.IGNORECASE)
    # Underscores used as spaces between tokens ("Stanton_1_Hurston" → "Stanton 1 Hurston")
    text = re.sub(r'(\w)_(\w)', r'\1 \2', text)
    # Commas between digits → dots
    text = re.sub(r'(\d),(\d)', r'\1.\2', text)
    # Spaces inside decimal numbers
    text = re.sub(r'(\d+)\.\s+(\d+)', r'\1.\2', text)
    return text


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# "Zone: OOC Stanton 1 Hurston Pos:"  or  "Zone:OOC _Stanton 1_HurstonPos:"
# System number may be digit or letter 'l' (OCR confusion); body may have leading '_'
_RE_OOC_ZONE = re.compile(
    r"Zone\s*:\s*OOC\s+_?(\w+)\s+[0-9l]*\s*_?(\w+)\s*(?:Pos|$)",
    re.IGNORECASE,
)

# "Planet:OOC Stanton 1 Hurston (working)" / "Planet:OOC Stanton l_Hurston (working)"
_RE_PLANET = re.compile(
    r"Planet\s*:\s*OOC\s+_?(\w+)\s+[0-9l]*\s*_?(\w+)\s+[(\[]?working",
    re.IGNORECASE,
)

# "CamPos.Planet Zone: 35425.011720 -967402.796166 -254226.311659"
# Numbers may be separated by spaces or run together with a '-' sign
_RE_CAMPOS = re.compile(
    r"CamPos\.Planet Zone:\s*([-]?\d{4,}\.\d+)\s*([-]\d{4,}\.\d+)\s*([-]\d{4,}\.\d+)",
    re.IGNORECASE,
)

# "Altitude 59.046645" or "Altitude: 59.046645"
_RE_ALTITUDE = re.compile(
    r"Altitude\s*:?\s*([\d.]+)",
    re.IGNORECASE,
)


def _parse_body(text: str) -> Optional[tuple[str, str]]:
    """Return (system, body) from OOC Zone or Planet line."""
    for pat in (_RE_PLANET, _RE_OOC_ZONE):
        m = pat.search(text)
        if m:
            sys_raw  = m.group(1)
            body_raw = m.group(2)
            system = _SYSTEM_ALIASES.get(sys_raw.lower())
            body   = _canon_body(body_raw)
            if system and body:
                return system, body
    return None


def _parse_campos(text: str) -> Optional[tuple[float, float, float]]:
    m = _RE_CAMPOS.search(text)
    if m:
        try:
            return float(m.group(1)), float(m.group(2)), float(m.group(3))
        except ValueError:
            pass
    return None


def _parse_altitude(text: str) -> Optional[float]:
    m = _RE_ALTITUDE.search(text)
    try:
        return float(m.group(1)) if m else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_location(arr: np.ndarray) -> Optional[LocationInfo]:
    """
    Given a full screenshot as an RGB numpy array, return LocationInfo or None.
    Requires r_displayinfo 3 to be active in-game.
    The RapidOCR engine is loaded on first call (~1 s); subsequent calls are fast.
    """
    crop   = _extract_hud_region(arr)
    raw    = _ocr(crop)
    if not raw.strip():
        return None

    text = _normalise(raw)

    body_info = _parse_body(text)
    if body_info is None:
        return None

    system, body = body_info
    altitude     = _parse_altitude(text)
    if altitude is None:
        return None

    campos = _parse_campos(text)
    x_km = y_km = z_km = None
    if campos:
        x_m, y_m, z_m = campos
        x_km = x_m / 1000.0
        y_km = y_m / 1000.0
        z_km = z_m / 1000.0

    return LocationInfo(
        system     = system,
        body       = body,
        altitude_m = altitude,
        coord_x    = x_km,
        coord_y    = y_km,
        coord_z    = z_km,
        raw        = raw[:500],
    )
