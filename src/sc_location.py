"""
Obtiene coordenadas del jugador enviando /showlocation al chat de Star Citizen.

El juego copia al portapapeles:
    Coordinates: X: 12345678.123 Y: -98765432.456 Z: 1234567.789

No requiere r_displayinfo ni OCR. Funciona en cualquier lugar del espacio.
"""

import ctypes
import ctypes.wintypes
import re
import time
import threading
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Win32
# ---------------------------------------------------------------------------

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_KEYDOWN   = 0x0100
WM_KEYUP     = 0x0101
WM_CHAR      = 0x0102
VK_RETURN    = 0x0D
VK_SLASH     = 0xBF   # '/' — VK code para teclado estándar US
VK_T         = 0x54

# PostMessage es asíncrono (no bloquea esperando que SC procese el mensaje)
PostMessage  = user32.PostMessageW
SendMessage  = user32.SendMessageW
FindWindow   = user32.FindWindowW
EnumWindows  = user32.EnumWindows

_CLIPBOARD_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class SCCoords:
    x: float   # metros en coordenadas globales del sistema
    y: float
    z: float
    raw: str   # texto original del portapapeles

# "Coordinates: X: 12345678.123 Y: -98765432.456 Z: 1234567.789"
_RE_COORDS = re.compile(
    r"Coordinates:\s*X:\s*([-\d.]+)\s*Y:\s*([-\d.]+)\s*Z:\s*([-\d.]+)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Buscar ventana de Star Citizen
# ---------------------------------------------------------------------------

def _find_sc_hwnd() -> Optional[int]:
    """Devuelve el HWND de la ventana Star Citizen, o None."""
    found = [None]

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if "Star Citizen" in buf.value:
            found[0] = hwnd
            return False   # detener enumeración
        return True

    EnumWindows(cb, 0)
    return found[0]


# ---------------------------------------------------------------------------
# Portapapeles
# ---------------------------------------------------------------------------

def _get_clipboard() -> str:
    """Lee texto del portapapeles de Windows."""
    CF_UNICODETEXT = 13
    if not user32.OpenClipboard(0):
        return ""
    try:
        h = ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def _set_clipboard(text: str):
    """Escribe texto en el portapapeles."""
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE  = 0x0002
    encoded = (text + "\0").encode("utf-16-le")
    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not h:
        return
    ptr = kernel32.GlobalLock(h)
    if not ptr:
        kernel32.GlobalFree(h)
        return
    ctypes.memmove(ptr, encoded, len(encoded))
    kernel32.GlobalUnlock(h)
    if user32.OpenClipboard(0):
        try:
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_UNICODETEXT, h)
        finally:
            user32.CloseClipboard()


# ---------------------------------------------------------------------------
# Envío de /showlocation via WM_CHAR
# ---------------------------------------------------------------------------

def _send_showlocation(hwnd: int):
    """
    Envía '/showlocation\n' carácter a carácter al chat de SC.

    WM_CHAR es la forma más compatible — no depende de teclas virtuales ni
    estado del teclado físico. SC abre el chat con '/' como primer carácter.
    """
    msg = "/showlocation\r"   # \r = Enter
    for ch in msg:
        PostMessage(hwnd, WM_CHAR, ord(ch), 0)
        time.sleep(0.015)     # 15 ms entre caracteres — evita que SC los descarte


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def get_coords(timeout: float = 2.5) -> Optional[SCCoords]:
    """
    Envía /showlocation a Star Citizen y devuelve las coordenadas del portapapeles.

    Retorna None si:
    - SC no está abierto
    - el portapapeles no se actualiza en `timeout` segundos
    - el formato del portapapeles no coincide

    Usa un lock para no solapar llamadas concurrentes.
    """
    with _CLIPBOARD_LOCK:
        hwnd = _find_sc_hwnd()
        if not hwnd:
            return None

        # Guardar contenido actual del portapapeles para detectar cambio
        prev = _get_clipboard()

        _send_showlocation(hwnd)

        # Esperar a que SC actualice el portapapeles
        deadline = time.monotonic() + timeout
        text = ""
        while time.monotonic() < deadline:
            time.sleep(0.05)
            text = _get_clipboard()
            if text != prev and "Coordinates:" in text:
                break
        else:
            return None

        m = _RE_COORDS.search(text)
        if not m:
            return None

        try:
            return SCCoords(
                x   = float(m.group(1)),
                y   = float(m.group(2)),
                z   = float(m.group(3)),
                raw = text.strip(),
            )
        except ValueError:
            return None
