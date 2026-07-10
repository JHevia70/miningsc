import json
from pathlib import Path

SUPABASE_URL     = "https://dtfkyacafqkrbyhgoxjk.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR0Zmt5YWNhZnFrcmJ5aGdveGprIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxNzQ2OTUsImV4cCI6MjA5Mzc1MDY5NX0.gKpTVsoleSQ9M7uXM-9glz2eINgnlto8EA7CF4LQKjE"

DEFAULTS = {
    "text_align": "right",   # "left" | "right"
    "alpha":      0.50,      # 0.1 – 1.0
    "font_size":  11,        # pts
    "font_name":  "Electrolize",
    "temp_dir":   "",        # "" = system temp
    "game_path":  "",        # ruta a la carpeta LIVE de Star Citizen
    "player_id":  "",        # UUID generado al primer arranque
    "share_server_ips": True,  # compartir IP de servidor de juego para medir latencia de red
}

def _exe_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent

_PATH = _exe_dir() / "config.json"

def load() -> dict:
    cfg = dict(DEFAULTS)
    if _PATH.exists():
        try:
            cfg.update(json.loads(_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg

def save(cfg: dict):
    _PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
