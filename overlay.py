"""
MiningSC Scanner
- Runs as a system tray application
- F9: scan screen and update display
- F10: toggle scanner visibility
- Tray menu: Show/Hide, Exit
"""
import tkinter as tk
import tkinter.font as tkfont
import threading
import tempfile
import os
import sys
import ctypes
from pathlib import Path

import mss
import mss.tools
import keyboard
import pystray
from PIL import Image, ImageDraw

# Resolve base directory (works both from source and PyInstaller bundle)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

sys.path.insert(0, str(BASE_DIR))
from src.panel_detector import scan_screenshot, warmup, is_ready
from src.sc_location import get_coords
from src.log_reader import start as start_log_reader, get_session_info
from src.config import load as load_cfg, save as save_cfg
from src.config_window import ConfigWindow
from src.uploader import upload_scan
from src.pricer import ensure_loaded, compute_value


def _register_bundled_fonts():
    """Load fonts shipped with the app so tkinter can use them without system install."""
    font_dir = BASE_DIR / "data" / "fonts"
    if not font_dir.exists():
        return
    FR_PRIVATE = 0x10
    for ttf in font_dir.glob("*.ttf"):
        ctypes.windll.gdi32.AddFontResourceExW(str(ttf), FR_PRIVATE, 0)

_register_bundled_fonts()


def _sc_monitor(sct) -> dict:
    """
    Return the mss monitor dict that contains the Star Citizen window.
    Falls back to monitors[1] if SC is not found.
    """
    try:
        import ctypes, ctypes.wintypes
        user32 = ctypes.windll.user32
        buf = ctypes.create_unicode_buffer(256)

        found = [None]
        def cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            user32.GetWindowTextW(hwnd, buf, 256)
            if "Star Citizen" in buf.value:
                rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                found[0] = rect
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(cb), 0)

        if found[0]:
            r = found[0]
            # Find the mss monitor (index 1+) whose region contains the SC window centre
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            for m in sct.monitors[1:]:
                if m["left"] <= cx < m["left"] + m["width"] and \
                   m["top"]  <= cy < m["top"]  + m["height"]:
                    return m
    except Exception:
        pass
    return sct.monitors[1]


def _coords_to_dict(coords, session=None) -> dict:
    """Merge SCCoords + SessionInfo into a location dict for uploader."""
    d = {}
    if coords:
        d["coord_x"] = coords.x
        d["coord_y"] = coords.y
        d["coord_z"] = coords.z
        d["raw"]     = coords.raw
    if session:
        d["session_id"] = session.session_id
        d["shard"]      = session.shard
        d["system"]     = session.system
        d["body"]       = session.body
    return d


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OVERLAY_MARGIN = 20   # px from screen edge
COLOR_BG   = "#0a1a2e"
COLOR_FG   = "#e0e0e0"
COLOR_PCT  = "#ffcc00"
COLOR_NAME = "#00cfff"
COLOR_QUAL = "#aaaaaa"
COLOR_INRT = "#888888"
COLOR_BEST = "#ff6600"
COLOR_HEAD = "#ffffff"
COLOR_VAL  = "#44ff88"   # aUEC value
HOTKEY_SCAN   = "f9"
HOTKEY_TOGGLE = "f10"


# ---------------------------------------------------------------------------
# Win32 helpers
# ---------------------------------------------------------------------------
GWL_EXSTYLE       = -20
WS_EX_LAYERED     = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

def _set_clickthrough(hwnd):
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


# ---------------------------------------------------------------------------
# Tray icon image (simple SC-themed diamond)
# ---------------------------------------------------------------------------
def _make_tray_icon():
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = size // 2 - 4
    diamond = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    d.polygon(diamond, fill="#00cfff")
    d.polygon([(cx, cy - r + 6), (cx + r - 6, cy), (cx, cy + r - 6), (cx - r + 6, cy)],
              fill="#0a1a2e")
    return img


# ---------------------------------------------------------------------------
# Overlay window
# ---------------------------------------------------------------------------
class MiningOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MiningSC Scanner")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=COLOR_BG)

        self._cfg = load_cfg()
        self.root.attributes("-alpha", self._cfg["alpha"])

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self._screen_w = sw
        self._screen_h = sh
        self._overlay_x = sw - 400 - OVERLAY_MARGIN
        self._overlay_y = sh // 4
        self._user_moved = False
        self._visible = False

        self.root.geometry(f"+{self._overlay_x}+{self._overlay_y}")
        self.root.withdraw()

        # Outer frame — the whole overlay widget
        self._outer = tk.Frame(self.root, bg=COLOR_BG,
                               highlightbackground="#1e4a6e", highlightthickness=1)
        self._outer.pack(fill=tk.BOTH, expand=True)

        self._scan     = None
        self._lines    = []
        self._location = {}
        self._scanning = False
        self._hwnd     = None
        self._labels   = []   # currently displayed label widgets

        self._config_win = ConfigWindow(self.root, self._apply_config)

        start_log_reader()
        ensure_loaded()
        warmup()
        self.root.after(500, self._poll_ready)
        self._draw_idle()
        self.root.after(200, self._apply_clickthrough)

        keyboard.add_hotkey(HOTKEY_SCAN,   self._on_scan,   suppress=False)
        keyboard.add_hotkey(HOTKEY_TOGGLE, self._on_toggle, suppress=False)
        keyboard.on_press_key("alt",   self._enable_drag,  suppress=False)
        keyboard.on_release_key("alt", self._disable_drag, suppress=False)

    # ------------------------------------------------------------------
    def _apply_clickthrough(self):
        hwnd = ctypes.windll.user32.FindWindowW(None, "MiningSC Scanner")
        if hwnd:
            _set_clickthrough(hwnd)
        self._hwnd = hwnd

    def _enable_drag(self, _=None):
        if not self._hwnd or not self._visible:
            return
        style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style)
        self._outer.bind("<ButtonPress-1>", self._drag_start)
        self._outer.bind("<B1-Motion>",     self._drag_motion)

    def _disable_drag(self, _=None):
        if not self._hwnd:
            return
        style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        style |= WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style)
        self._outer.unbind("<ButtonPress-1>")
        self._outer.unbind("<B1-Motion>")

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag_motion(self, event):
        self._overlay_x = event.x_root - self._drag_x
        self._overlay_y = event.y_root - self._drag_y
        self._user_moved = True
        self.root.geometry(f"+{self._overlay_x}+{self._overlay_y}")

    def _apply_config(self, cfg):
        self._cfg = cfg
        self.root.attributes("-alpha", cfg["alpha"])
        self._draw_idle() if not self._lines else self._draw_results()

    def open_config(self):
        self.root.after(0, self._config_win.open)

    # ------------------------------------------------------------------
    def _on_toggle(self):
        self.root.after(0, self._toggle_visibility)

    def _toggle_visibility(self):
        if self._visible:
            self.root.withdraw()
            self._visible = False
        else:
            self.root.deiconify()
            self._visible = True
            self._apply_clickthrough()
            # Refresh display in case state changed while hidden
            if self._lines:
                self._draw_results()
            elif not is_ready():
                self._build_simple("MiningSC Scanner", "Iniciando...")
            else:
                self._draw_idle()

    def show(self):
        self.root.after(0, lambda: (self.root.deiconify(),
                                    setattr(self, '_visible', True),
                                    self._apply_clickthrough()))

    def hide(self):
        self.root.after(0, lambda: (self.root.withdraw(),
                                    setattr(self, '_visible', False)))

    # ------------------------------------------------------------------
    def _on_scan(self):
        if not self._visible or self._scanning:
            return
        if not is_ready():
            self._build_simple("MiningSC Scanner", "Iniciando...")
            return
        self._scanning = True
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        self.root.after(0, lambda: self._build_simple("MiningSC Scanner", "Escaneando..."))
        tmp = None
        try:
            # Lanzar /showlocation en paralelo mientras preparamos el screenshot
            coords_result = [None]
            def _fetch_coords():
                try:
                    coords_result[0] = get_coords(timeout=2.5)
                except Exception as ex:
                    print(f"[scanner] /showlocation error: {ex}")
            coords_thread = threading.Thread(target=_fetch_coords, daemon=True)
            coords_thread.start()

            with mss.mss() as sct:
                monitor = _sc_monitor(sct)
                shot = sct.grab(monitor)
                temp_dir = self._cfg.get("temp_dir", "").strip() or None
                tmp = tempfile.mktemp(suffix=".png", dir=temp_dir)
                mss.tools.to_png(shot.rgb, shot.size, output=tmp)

            rock = scan_screenshot(tmp)
            self._scan  = rock
            self._lines = rock.lines if rock else []

            import shutil
            shutil.copy(tmp, Path(r"F:\SC_temp") / "diag_last_scan.png")

            if not self._lines:
                print("[scanner] No panel detected")
            else:
                print(f"[scanner] {len(self._lines)} minerals, {self._scan.mass_scu:.2f} SCU")

            session = get_session_info()

            def _bg(lines=list(self._lines), cfg=dict(self._cfg), session=session):
                try:
                    coords_thread.join(timeout=3.0)
                    coords = coords_result[0]
                    if coords:
                        print(f"[scanner] coords X={coords.x:.0f} Y={coords.y:.0f} Z={coords.z:.0f}")
                    else:
                        print("[scanner] /showlocation sin respuesta")
                    self._location = _coords_to_dict(coords, session)
                    self.root.after(0, self._draw_results)
                    if lines:
                        upload_scan(lines, self._location, cfg)
                except Exception as ex:
                    print(f"[scanner] bg error: {ex}")
            threading.Thread(target=_bg, daemon=True).start()

        except Exception as e:
            self._scan  = None
            self._lines = []
            print(f"[scanner] Error: {e}")
        finally:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
            self._scanning = False
            self.root.after(0, self._draw_results)

    # ------------------------------------------------------------------
    # Drawing — Label-based grid table
    # ------------------------------------------------------------------

    def _clear(self):
        for w in self._labels:
            w.destroy()
        self._labels.clear()
        for w in self._outer.winfo_children():
            w.destroy()

    def _lbl(self, parent, text, fg, bg=None, bold=False, size=None,
             padx=6, pady=3, anchor="w", row=0, col=0, colspan=1):
        fn = self._cfg.get("font_name", "Electrolize")
        fs = size or self._cfg.get("font_size", 11)
        w = tk.Label(parent, text=text, fg=fg, bg=bg or COLOR_BG,
                     font=(fn, fs, "bold" if bold else "normal"),
                     padx=padx, pady=pady, anchor=anchor)
        w.grid(row=row, column=col, columnspan=colspan,
               sticky="nsew", padx=0, pady=0)
        self._labels.append(w)
        return w

    def _sep(self, parent, row, ncols):
        f = tk.Frame(parent, bg="#1e3a55", height=1)
        f.grid(row=row, column=0, columnspan=ncols, sticky="ew", padx=4, pady=0)
        self._labels.append(f)

    def _build_simple(self, title, status):
        self._clear()
        f = tk.Frame(self._outer, bg=COLOR_BG)
        f.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._lbl(f, title,  COLOR_HEAD, bold=True, size=12, row=0, col=0)
        self._lbl(f, status, COLOR_FG,              size=10, row=1, col=0)
        self._reposition()

    def _poll_ready(self):
        if is_ready():
            self._draw_idle()
        else:
            self._build_simple("MiningSC Scanner", "Iniciando...")
            self.root.after(500, self._poll_ready)

    def _draw_idle(self):
        self._build_simple("MiningSC Scanner", "F9 escanear  |  F10 ocultar")

    def _draw_results(self):
        if not self._lines:
            self._build_simple("MiningSC Scanner", "Panel no detectado")
            return

        cx = self._location.get("coord_x")
        cy = self._location.get("coord_y")
        cz = self._location.get("coord_z")
        if cx is not None:
            loc_label = f"X:{cx/1000:.1f}  Y:{cy/1000:.1f}  Z:{cz/1000:.1f} km"
        else:
            loc_label = ""

        # Merge duplicate mineral names
        from src.panel_detector import MineralLine
        merged: dict[str, MineralLine] = {}
        for l in self._lines:
            key = l.name.upper() if l.name else ""
            if key in merged:
                ex = merged[key]
                merged[key] = MineralLine(
                    percent  = round(ex.percent + l.percent, 2),
                    name     = ex.name,
                    quality  = max(ex.quality, l.quality),
                    is_inert = ex.is_inert,
                )
            else:
                merged[key] = MineralLine(l.percent, l.name, l.quality, l.is_inert)
        display_lines = list(merged.values())

        mass_scu = self._scan.mass_scu if self._scan else 0.0
        val_raw, val_ref, best_loc = compute_value(display_lines, mass_scu)
        best_q = max((l.quality for l in display_lines if not l.is_inert), default=0)

        def fmt(v):
            if v is None: return "—"
            if v >= 1_000_000: return f"{v/1_000_000:.2f}M"
            if v >= 1_000:     return f"{v/1_000:.1f}K"
            return f"{v:.0f}"

        self._clear()
        NCOLS = 4   # Mineral | Crudo | Ref | Venta

        # ── outer padding frame ──────────────────────────────────────
        pad = tk.Frame(self._outer, bg=COLOR_BG)
        pad.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ── title row ───────────────────────────────────────────────
        r = 0
        title_lbl = tk.Label(pad, text="MiningSC Scanner", fg=COLOR_HEAD, bg=COLOR_BG,
                              font=(self._cfg.get("font_name","Electrolize"), 12, "bold"),
                              padx=4, pady=2, anchor="w")
        title_lbl.grid(row=r, column=0, columnspan=NCOLS, sticky="ew")
        self._labels.append(title_lbl)
        r += 1

        if loc_label:
            self._lbl(pad, loc_label, COLOR_FG, size=9, padx=4, pady=1,
                      row=r, col=0, colspan=NCOLS)
            r += 1

        # ── table ────────────────────────────────────────────────────
        tbl = tk.Frame(pad, bg="#1e3a55", bd=0)   # border-colour frame
        tbl.grid(row=r, column=0, columnspan=NCOLS, sticky="nsew", pady=(4, 0))
        self._labels.append(tbl)

        # inner white-on-dark grid
        inner = tk.Frame(tbl, bg=COLOR_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self._labels.append(inner)

        # configure column weights so numbers right-align inside fixed-width cells
        inner.columnconfigure(0, weight=3)   # Mineral — wider
        inner.columnconfigure(1, weight=1, minsize=65)
        inner.columnconfigure(2, weight=1, minsize=65)
        inner.columnconfigure(3, weight=2, minsize=90)

        def cell(row, col, text, fg, bg=COLOR_BG, bold=False, anchor="e", colspan=1):
            fn = self._cfg.get("font_name", "Electrolize")
            fs = self._cfg.get("font_size", 10)
            w = tk.Label(inner, text=text, fg=fg, bg=bg,
                         font=(fn, fs, "bold" if bold else "normal"),
                         padx=5, pady=3, anchor=anchor)
            w.grid(row=row, column=col, columnspan=colspan,
                   sticky="nsew", padx=1, pady=1)
            self._labels.append(w)

        # header row
        HDR_BG = "#0d2b45"
        cell(0, 0, "Mineral", COLOR_HEAD, bg=HDR_BG, bold=True, anchor="w")
        cell(0, 1, "Crudo",   COLOR_HEAD, bg=HDR_BG, bold=True)
        cell(0, 2, "Ref",     COLOR_HEAD, bg=HDR_BG, bold=True)
        cell(0, 3, "Venta",   COLOR_HEAD, bg=HDR_BG, bold=True, anchor="w")

        # totals row
        TOT_BG = "#0a2a1a"
        cell(1, 0, "TOTAL",        COLOR_VAL, bg=TOT_BG, bold=True, anchor="w")
        cell(1, 1, fmt(val_raw),   COLOR_VAL, bg=TOT_BG, bold=True)
        cell(1, 2, fmt(val_ref),   COLOR_VAL, bg=TOT_BG, bold=True)
        cell(1, 3, best_loc or "—", COLOR_NAME, bg=TOT_BG, bold=False, anchor="w")

        # separator
        sep = tk.Frame(inner, bg="#1e3a55", height=1)
        sep.grid(row=2, column=0, columnspan=NCOLS, sticky="ew")
        self._labels.append(sep)

        # mineral rows
        for i, l in enumerate(display_lines):
            gr = i + 3
            row_bg = "#0c1f35" if i % 2 == 0 else COLOR_BG
            if l.is_inert:
                continue
            else:
                is_best = (l.quality == best_q and best_q > 0)
                col_n   = COLOR_BEST if is_best else COLOR_NAME
                prices  = compute_value([l], mass_scu)
                cell(gr, 0, l.name, col_n, bg=row_bg,
                     bold=is_best, anchor="w")
                cell(gr, 1, fmt(prices[0]), COLOR_PCT,  bg=row_bg)
                cell(gr, 2, fmt(prices[1]), COLOR_VAL,  bg=row_bg)
                loc_s = prices[2] or "—"
                cell(gr, 3, loc_s, COLOR_FG, bg=row_bg, anchor="w")

        self._reposition()

    def _reposition(self):
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        if not self._user_moved:
            text_align = self._cfg.get("text_align", "right")
            if text_align == "right":
                self._overlay_x = self._screen_w - w - OVERLAY_MARGIN
            else:
                self._overlay_x = OVERLAY_MARGIN
            self._overlay_y = self._screen_h // 4 - h // 2
        self.root.geometry(f"{w}x{h}+{self._overlay_x}+{self._overlay_y}")

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Tray application
# ---------------------------------------------------------------------------
class TrayApp:
    def __init__(self):
        self.overlay = MiningOverlay()
        icon_img = _make_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar / Ocultar", self._tray_toggle, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Configuración...", self._tray_config),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._tray_exit),
        )
        self.tray = pystray.Icon("MiningSC", icon_img, "MiningSC Scanner", menu)

    def _tray_toggle(self, icon=None, item=None):
        if self.overlay._visible:
            self.overlay.hide()
        else:
            self.overlay.show()

    def _tray_config(self, icon=None, item=None):
        self.overlay.open_config()

    def _tray_exit(self, icon=None, item=None):
        keyboard.unhook_all()
        self.tray.stop()
        self.overlay.root.after(0, self.overlay.root.destroy)

    def run(self):
        # Tray runs in its own thread; tkinter mainloop on main thread
        threading.Thread(target=self.tray.run, daemon=True).start()
        self.overlay.run()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = TrayApp()
    app.run()
