"""
Reads Star Citizen Game.log to extract session and location context.

Parsed data:
  - session_id   : server session UUID (from Channel Connected lines)
  - shard        : human-readable shard name (env_session, e.g. "pub-sc-alpha-480-11825000")
  - node_id      : server node UUID (available after Channel Connection Complete)
  - body         : active celestial body (from OOC_<System>_<N>_<Body> lines during map load)
  - system       : star system name

The log is read once on init (tail of last N lines) then monitored via thread.
All state is updated in-place; callers read get_session_info() at any time.
"""

import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Log location
# ---------------------------------------------------------------------------

_LOG_CANDIDATES = [
    Path(r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Game.log"),
    Path(r"D:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Game.log"),
    Path(r"E:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Game.log"),
    Path(r"G:\Roberts Space Industries\StarCitizen\StarCitizen\LIVE\Game.log"),
]


def _find_log() -> Optional[Path]:
    for p in _LOG_CANDIDATES:
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# <2026-06-09T18:58:19.540Z> [Notice] <Channel Created> ... session=c4b094984f0ae9fd1f1070757201a5c1 ... remoteAddr=34.78.69.136:64338 ...
_RE_CHANNEL = re.compile(
    r"<Channel (?:Created|Connection Complete)>"
    r".*?session=([0-9a-f]{32})"
    r".*?node_id=([\w-]+)"
    r".*?remoteAddr=([\d.]+:\d+)",
    re.IGNORECASE,
)

# [Trace] @session:      '3b1718d2-c4b5-5f4c-8630-e6be5652e8f8'
_RE_CLIENT_SESSION = re.compile(r"@session:\s+'([\w-]+)'")

# [Trace] @env_session:  'pub-sc-alpha-480-11825000'
_RE_ENV_SESSION = re.compile(r"@env_session:\s+'([^']+)'")

# planet cells: ... name: OOC_Stanton_1_Hurston
_RE_OOC_BODY = re.compile(r"name:\s+OOC_(\w+)_\d+_(\w+)", re.IGNORECASE)

# Channel Disconnected — clear server session
_RE_DISCONNECTED = re.compile(r"<Channel Disconnected>.*?remoteAddr=(\d+\.\d+)")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class SessionInfo:
    session_id:     Optional[str] = None   # server session hex (32 chars)
    shard:          Optional[str] = None   # e.g. "pub-sc-alpha-480-11825000"
    node_id:        Optional[str] = None   # server node UUID
    system:         Optional[str] = None   # "Stanton" | "Pyro" | ...
    body:           Optional[str] = None   # "Hurston" | "microTech" | ...


_state  = SessionInfo()
_lock   = threading.Lock()
_thread: Optional[threading.Thread] = None


_SYSTEM_CANON = {
    "stanton": "Stanton",
    "pyro":    "Pyro",
    "nyx":     "Nyx",
}

_BODY_CANON = {
    "hurston":   "Hurston",
    "crusader":  "Crusader",
    "arccorp":   "ArcCorp",
    "microtech": "microTech",
    "aberdeen":  "Aberdeen",
    "magda":     "Magda",
    "ita":       "Ita",
    "wala":      "Wala",
    "cellin":    "Cellin",
    "daymar":    "Daymar",
    "yela":      "Yela",
    "euterpe":   "Euterpe",
    "calliope":  "Calliope",
    "clio":      "Clio",
    "lyria":     "Lyria",
    "pyroi":     "Pyro I",
    "monox":     "Monox",
    "pyroiii":   "Pyro III",
    "bloom":     "Bloom",
    "pyrov":     "Pyro V",
    "terminus":  "Terminus",
    "fuego":     "Fuego",
    "adir":      "Adir",
    "delamar":   "Delamar",
    "aaronhalo": "Aaron Halo",
}


def _process_line(line: str):
    with _lock:
        # env_session — shard name, written at startup
        m = _RE_ENV_SESSION.search(line)
        if m:
            _state.shard = m.group(1)
            return

        # Channel Created / Connection Complete — server session + node
        m = _RE_CHANNEL.search(line)
        if m:
            _state.session_id = m.group(1)
            node = m.group(2)
            if node != "00000000-0000-0000-0000-000000000000":
                _state.node_id = node
            return

        # Channel Disconnected from real server — clear session
        m = _RE_DISCONNECTED.search(line)
        if m:
            _state.session_id = None
            _state.node_id    = None
            return

        # OOC body name during map load
        m = _RE_OOC_BODY.search(line)
        if m:
            sys_raw  = m.group(1).lower()
            body_raw = re.sub(r"[^a-z]", "", m.group(2).lower())
            system = _SYSTEM_CANON.get(sys_raw)
            body   = _BODY_CANON.get(body_raw)
            if system:
                _state.system = system
            if body:
                _state.body = body


# ---------------------------------------------------------------------------
# Background tail thread
# ---------------------------------------------------------------------------

def _tail_log(path: Path):
    """Open the log file and tail it indefinitely, processing new lines."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            # Seek near end — read last ~200 KB to catch current session
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 200_000))
            f.readline()   # discard partial first line

            for line in f:
                _process_line(line)

            # Now tail
            while True:
                line = f.readline()
                if line:
                    _process_line(line)
                else:
                    time.sleep(0.2)
    except Exception as e:
        print(f"[log_reader] tail error: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start():
    """Start the background log-tailing thread. Safe to call multiple times."""
    global _thread
    if _thread and _thread.is_alive():
        return
    path = _find_log()
    if not path:
        print("[log_reader] Game.log not found — session/location context unavailable")
        return
    print(f"[log_reader] monitoring {path}")
    _thread = threading.Thread(target=_tail_log, args=(path,), daemon=True)
    _thread.start()


def get_session_info() -> SessionInfo:
    """Return a snapshot of the current session state."""
    with _lock:
        return SessionInfo(
            session_id = _state.session_id,
            shard      = _state.shard,
            node_id    = _state.node_id,
            system     = _state.system,
            body       = _state.body,
        )
