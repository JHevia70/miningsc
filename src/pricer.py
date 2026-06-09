"""
Fetches mineral prices from Supabase and computes rock value estimates.
Prices are cached in memory for the session.

Uses commodities.name substring matching against canonical mineral names
because commodity.mineral_id is NULL for many minerals in the DB.

Refinery yield data (source: Star Citizen community testing, starcitizen.tools):
All methods share a 95% base yield. Each method applies an additional reduction.
Dinyx Solventation has the highest yield (no extra reduction beyond base).
We apply Dinyx yield by default since it maximises value.
"""

import threading
from typing import Optional
from . import config as cfg_mod

# Refinery method yields (fraction of raw SCU that becomes refined output).
# Source: community-verified values. Dinyx Solventation = best yield.
# Values are relative to input: e.g. 0.95 means 95% of the ore becomes refined.
REFINERY_YIELDS: dict[str, float] = {
    "Dinyx Solventation":      0.95,   # Slow/Careful  — best yield
    "Ferron Exchange":         0.925,  # Normal/Careful — 2.4% less profit, 3× faster
    "Pyrometric Chromalysis":  0.8075, # Slow/Wasteful  — ~15% less profit
    "Thermonatic Deposition":  0.855,  # Slow/Normal
    "Electrostarolysis":       0.789,  # Normal/Normal  — ~17% less profit
    "Gaskin Process":          0.831,  # Fast/Normal
    "Cormack Method":          0.878,  # Fast/Careful
    "Kazen Winnowing":         0.76,   # Normal/Wasteful
    "XCR Reaction":            0.712,  # Fast/Wasteful  — lowest yield
}

# Default method: best yield
DEFAULT_REFINERY_METHOD = "Dinyx Solventation"
DEFAULT_YIELD = REFINERY_YIELDS[DEFAULT_REFINERY_METHOD]

_lock   = threading.Lock()
_cache: dict[str, dict] = {}   # canonical_name_upper -> {"raw": float|None, "refined": float|None, "location": str|None}
_loaded = False


def _get_client():
    from supabase import create_client
    return create_client(cfg_mod.SUPABASE_URL, cfg_mod.SUPABASE_ANON_KEY)


def _load_prices():
    global _loaded
    try:
        sb = _get_client()
        from .mineral_names import normalize as _norm

        raw:      dict[str, float] = {}
        refined:  dict[str, float] = {}
        location: dict[str, str]   = {}  # best sell location for refined

        # Build id->canonical map from commodities table (refined only)
        comm_rows = (
            sb.table("commodities")
            .select("id,name,is_refined,price_sell")
            .eq("is_refined", True)
            .execute()
            .data
        )
        id_to_canon: dict[int, str] = {}
        for r in comm_rows:
            canon = _norm(r.get("name") or "")
            if not canon:
                continue
            cid = r.get("id")
            if cid:
                id_to_canon[cid] = canon
            # Also use commodities.price_sell as a fallback price
            key = canon.upper()
            price = float(r.get("price_sell") or 0)
            if price > refined.get(key, 0):
                refined[key] = price

        # Refined prices: commodity_prices — paginate to get all rows (>1000)
        ref_rows = []
        page = 0
        page_size = 1000
        while True:
            batch = (
                sb.table("commodity_prices")
                .select("id_commodity,price_sell,terminal_name")
                .gt("price_sell", 0)
                .range(page * page_size, (page + 1) * page_size - 1)
                .execute()
                .data
            )
            ref_rows.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        for r in ref_rows:
            cid   = r.get("id_commodity")
            canon = id_to_canon.get(cid)
            if not canon:
                continue
            key   = canon.upper()
            price = float(r.get("price_sell") or 0)
            if price > refined.get(key, 0):
                refined[key] = price
                location[key] = r.get("terminal_name") or ""

        # Raw prices: commodity_raw_prices table — best price_sell per mineral
        raw_rows = (
            sb.table("commodity_raw_prices")
            .select("price_sell,commodities(name)")
            .gt("price_sell", 0)
            .execute()
            .data
        )
        for r in raw_rows:
            name  = (r.get("commodities") or {}).get("name") or ""
            canon = _norm(name)
            if not canon:
                continue
            key   = canon.upper()
            price = float(r.get("price_sell") or 0)
            if price > raw.get(key, 0):
                raw[key] = price

        all_keys = set(raw) | set(refined)
        new_cache = {
            k: {"raw": raw.get(k), "refined": refined.get(k), "location": location.get(k)}
            for k in all_keys
        }
        with _lock:
            _cache.update(new_cache)
            _loaded = True
        print(f"[pricer] Loaded prices for {len(all_keys)} minerals")
        for k, v in sorted(new_cache.items()):
            print(f"  {k}: raw={v['raw']} ref={v['refined']} loc={v['location']}")
    except Exception as e:
        print(f"[pricer] Failed to load prices: {e}")


def ensure_loaded():
    """Start background price fetch on first call (non-blocking)."""
    with _lock:
        already = _loaded
    if not already:
        threading.Thread(target=_load_prices, daemon=True).start()


def get_prices(mineral_name: str) -> dict:
    """Return {"raw": float|None, "refined": float|None, "location": str|None}."""
    with _lock:
        return dict(_cache.get(mineral_name.upper(), {"raw": None, "refined": None, "location": None}))


def compute_value(lines, mass_scu: float,
                  refinery_yield: float = DEFAULT_YIELD
                  ) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Given MineralLine list and total rock mass in SCU, return
    (total_raw_aUEC, total_refined_aUEC, best_location).

    refined value accounts for refinery yield loss:
      value = (percent/100) * mass_scu * yield * price_per_scu
    """
    if mass_scu <= 0:
        return None, None, None

    total_raw = total_refined = 0.0
    has_raw = has_refined = False
    best_loc: Optional[str] = None
    best_ref_val = 0.0

    for line in lines:
        if line.is_inert or not line.name:
            continue
        prices = get_prices(line.name)
        frac = line.percent / 100.0
        if prices["raw"] is not None:
            total_raw += frac * mass_scu * prices["raw"]
            has_raw = True
        if prices["refined"] is not None:
            ref_val = frac * mass_scu * refinery_yield * prices["refined"]
            total_refined += ref_val
            has_refined = True
            if ref_val > best_ref_val and prices["location"]:
                best_ref_val = ref_val
                best_loc = prices["location"]

    return (total_raw if has_raw else None,
            total_refined if has_refined else None,
            best_loc)
