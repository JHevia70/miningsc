"""
Sends scan results to Supabase asynchronously.
Called from _scan_worker after a successful scan.
"""
import threading
import uuid
from datetime import datetime, timezone

from supabase import create_client
from . import config as cfg_mod

_client = None
_client_lock = threading.Lock()


def _get_client():
    global _client
    with _client_lock:
        if _client is None:
            _client = create_client(cfg_mod.SUPABASE_URL, cfg_mod.SUPABASE_ANON_KEY)
    return _client


def _ensure_player(cfg: dict) -> str:
    """Return player UUID, creating a new one if needed."""
    pid = cfg.get("player_id", "").strip()
    if not pid:
        pid = str(uuid.uuid4())
        cfg["player_id"] = pid
        cfg_mod.save(cfg)
        try:
            _get_client().table("players").insert({"id": pid}).execute()
        except Exception:
            pass
    return pid


def upload_scan(lines, location: dict, cfg: dict):
    """
    Upload a scan in a background thread so the overlay never blocks.

    lines    : list[MineralLine] from panel_detector
    location : dict with keys: system, body, station, altitude_m, coord_x, coord_y, raw
    cfg      : current config dict
    """
    threading.Thread(
        target=_do_upload,
        args=(lines, location, cfg),
        daemon=True,
    ).start()


def _do_upload(lines, location: dict, cfg: dict):
    try:
        sb = _get_client()
        player_id = _ensure_player(cfg)

        mineral_rows = []
        for line in lines:
            mineral_id = _resolve_id(sb, "minerals", "name", line.name) if line.name else None
            mineral_rows.append({
                "mineral_id": mineral_id,
                "name_raw":   line.name,
                "percent":    line.percent,
                "quality":    line.quality if not line.is_inert else None,
                "is_inert":   line.is_inert,
            })

        system_id = _resolve_id(sb, "systems", "name", location.get("system"))
        body_id   = _resolve_id(sb, "bodies",  "name", location.get("body"))

        result = sb.rpc("insert_scan_dedup", {
            "p_player_id":    player_id,
            "p_scanned_at":   datetime.now(timezone.utc).isoformat(),
            "p_system_id":    system_id,
            "p_body_id":      body_id,
            "p_zone":         None,
            "p_station":      None,
            "p_altitude_m":   None,
            "p_coord_x":      location.get("coord_x"),
            "p_coord_y":      location.get("coord_y"),
            "p_coord_z":      location.get("coord_z"),
            "p_raw_location": location.get("raw"),
            "p_session_id":   location.get("session_id"),
            "p_shard":        location.get("shard"),
            "p_minerals":     mineral_rows,
        }).execute()

        data = result.data
        if data.get("duplicate"):
            print(f"[uploader] duplicate scan, skipped (existing id={data.get('scan_id')})")
        else:
            print(f"[uploader] scan uploaded id={data.get('scan_id')}")

    except Exception as e:
        # Silent failure — overlay must never crash due to upload errors
        print(f"[uploader] {e}")


def _resolve_id(sb, table: str, col: str, value) -> int | None:
    if not value:
        return None
    try:
        res = sb.table(table).select("id").eq(col, value.upper() if table == "minerals" else value).limit(1).execute()
        if res.data:
            return res.data[0]["id"]
    except Exception:
        pass
    return None
