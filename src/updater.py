"""
Comprueba si hay una versión más nueva en GitHub Releases.
Se ejecuta en un hilo daemon al arrancar; llama a on_update_available(latest)
si la versión remota es mayor que la local.
"""

import re
import threading
import urllib.request
import urllib.error
from typing import Callable, Optional

CURRENT_VERSION = "1.0.4"
RELEASES_API    = "https://api.github.com/repos/JHevia70/miningsc/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", tag)
    return tuple(int(n) for n in nums)


def _fetch_latest() -> Optional[str]:
    try:
        req = urllib.request.Request(
            RELEASES_API,
            headers={"User-Agent": "MiningSC-Scanner", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            import json
            data = json.loads(resp.read())
            return data.get("tag_name", "")
    except Exception as e:
        print(f"[updater] no se pudo comprobar actualizaciones: {e}")
        return None


def check_async(on_update_available: Callable[[str], None]):
    """Lanza la comprobación en un hilo daemon. No bloquea el arranque."""
    def _run():
        tag = _fetch_latest()
        if not tag:
            return
        if _parse_version(tag) > _parse_version(CURRENT_VERSION):
            on_update_available(tag)

    threading.Thread(target=_run, daemon=True).start()
