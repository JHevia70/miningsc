#!/usr/bin/env python3
"""
Measures network latency from multiple European countries toward known
Star Citizen game server IPs, using the free Globalping API, and stores
results in Supabase.

Star Citizen game servers (Google Cloud) block ICMP/TCP/HTTP entirely
except their own game UDP port (confirmed by manual testing). So this
does NOT ping the game host directly — it runs `mtr` over TCP/443 and
keeps the RTT of the last hop that responds before the route goes dark,
i.e. the closest reachable point to the server (the Google Cloud edge).

Env vars required: SUPABASE_URL, SUPABASE_ANON_KEY
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from supabase import create_client

GLOBALPING_API = "https://api.globalping.io/v1/measurements"
COUNTRIES = ["ES", "DE", "NL", "FR", "PT", "IT", "PL", "RU", "AT", "DK", "FI", "NO", "GB", "CH", "SK", "UA"]
# Extra probes per country to work around flaky/unprivileged individual probes
# (e.g. some Spanish datacenter probes lack raw-ICMP permissions and fail the
# whole hop). Countries not listed here default to 1 probe.
PROBE_LIMIT_OVERRIDES = {"ES": 3}
ACTIVE_WINDOW_DAYS = 7
POLL_INTERVAL_S = 3
POLL_TIMEOUT_S = 120
MAX_ATTEMPTS = 3


def _client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def _active_ips(sb):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=ACTIVE_WINDOW_DAYS)).isoformat()
    res = (
        sb.table("game_server_ips")
        .select("id, ip")
        .eq("active", True)
        .gte("last_seen", cutoff)
        .execute()
    )
    return res.data or []


def _create_measurement(ip: str, countries: list[str]) -> str:
    body = {
        "target": ip,
        "type": "mtr",
        "measurementOptions": {"protocol": "TCP", "port": 443},
        "locations": [
            {"country": c, "limit": PROBE_LIMIT_OVERRIDES.get(c, 1)} for c in countries
        ],
    }
    r = requests.post(GLOBALPING_API, json=body, timeout=15)
    r.raise_for_status()
    return r.json()["id"]


def _poll_measurement(msm_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        r = requests.get(f"{GLOBALPING_API}/{msm_id}", timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "in-progress":
            return data
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"measurement {msm_id} did not finish in {POLL_TIMEOUT_S}s")


def _last_reachable_hop(hops: list) -> dict | None:
    """Return the DEEPEST hop that received at least one reply, i.e. the
    closest point in the route to the server that any country's trace
    reached — not just the last hop with a *clean* (0% loss) reading.

    Different routes/probes hit intermittent loss at different depths, so
    requiring 0% loss made countries stop at wildly different hop indexes
    (e.g. ES at hop 2 vs DE at hop 7), making their RTTs incomparable —
    a shallow, lucky hop for one country could read "faster" than a much
    deeper, genuinely closer hop for another. Depth (how far into the
    route we got) matters more than a single lossy probe at that hop.
    """
    best = None
    for i, hop in enumerate(hops):
        stats = hop.get("stats") or {}
        if stats.get("avg") is not None and (stats.get("rcv") or 0) > 0:
            best = (i, hop, stats)
    if best is None:
        return None
    idx, hop, stats = best
    return {
        "hop_index":   idx,
        "hop_address": hop.get("resolvedAddress"),
        "rtt_min_ms":  stats.get("min"),
        "rtt_avg_ms":  stats.get("avg"),
        "rtt_max_ms":  stats.get("max"),
        "packet_loss_pct": stats.get("loss"),
    }


def _rows_by_country(server_ip_id: int, measurement: dict, measured_at: str) -> dict[str, dict]:
    best_by_country: dict[str, dict] = {}

    for entry in measurement.get("results", []):
        probe = entry.get("probe", {})
        country = probe.get("country")
        result = entry.get("result", {})
        hops = result.get("hops") or []
        hop = _last_reachable_hop(hops)
        if hop is None:
            continue
        row = {
            "server_ip_id":  server_ip_id,
            "probe_country": country,
            "probe_city":    probe.get("city"),
            "measured_at":   measured_at,
            **hop,
        }
        # With multiple probes per country (see PROBE_LIMIT_OVERRIDES), keep
        # only the fastest reachable one so each country contributes exactly
        # one row per measurement round.
        current_best = best_by_country.get(country)
        if current_best is None or (row["rtt_avg_ms"] or float("inf")) < (current_best["rtt_avg_ms"] or float("inf")):
            best_by_country[country] = row

    return best_by_country


def _measure_countries(ip: str, countries: list[str], server_ip_id: int, measured_at: str) -> dict[str, dict]:
    msm_id = _create_measurement(ip, countries)
    measurement = _poll_measurement(msm_id)
    return _rows_by_country(server_ip_id, measurement, measured_at)


def _last_known_row(sb, server_ip_id: int, country: str, measured_at: str) -> dict | None:
    """Fall back to the most recent successful measurement for this
    country/server, re-stamped at the current round, so the chart line
    has no gap when a country fails all retry attempts."""
    res = (
        sb.table("ping_results")
        .select("probe_country, probe_city, hop_index, hop_address, rtt_min_ms, rtt_avg_ms, rtt_max_ms, packet_loss_pct")
        .eq("server_ip_id", server_ip_id)
        .eq("probe_country", country)
        .order("measured_at", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    row = dict(res.data[0])
    row["server_ip_id"] = server_ip_id
    row["measured_at"] = measured_at
    return row


def _measure_ip_with_retries(sb, ip: str, server_ip_id: int) -> list[dict]:
    measured_at = datetime.now(timezone.utc).isoformat()
    results: dict[str, dict] = {}
    pending = list(COUNTRIES)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if not pending:
            break
        print(f"[network_runner] {ip} — attempt {attempt}/{MAX_ATTEMPTS} for {pending}")
        try:
            found = _measure_countries(ip, pending, server_ip_id, measured_at)
        except Exception as e:
            print(f"[network_runner] {ip} — attempt {attempt} error: {e}")
            found = {}
        results.update(found)
        pending = [c for c in pending if c not in results]
        if pending:
            print(f"[network_runner] {ip} — still missing: {pending}")

    for country in pending:
        fallback = _last_known_row(sb, server_ip_id, country, measured_at)
        if fallback:
            results[country] = fallback
            print(f"  [{country}] no fresh data after {MAX_ATTEMPTS} attempts — reused last known value")
        else:
            print(f"  [{country}] no fresh data and no prior history — skipped")

    for country, row in results.items():
        print(f"  [{country}] hop#{row['hop_index']} "
              f"{row['hop_address']} avg={row['rtt_avg_ms']}ms loss={row['packet_loss_pct']}%")

    return list(results.values())


def main() -> int:
    sb = _client()

    try:
        servers = _active_ips(sb)
    except Exception as e:
        print(f"[network_runner] FATAL: could not read game_server_ips: {e}")
        return 1

    if not servers:
        print("[network_runner] no active server IPs to measure")
        return 0

    print(f"[network_runner] measuring {len(servers)} server IP(s) from {COUNTRIES}")

    for server in servers:
        ip = server["ip"]
        try:
            rows = _measure_ip_with_retries(sb, ip, server["id"])
            if rows:
                sb.table("ping_results").insert(rows).execute()
                print(f"[network_runner] {ip} — inserted {len(rows)} row(s)")
        except Exception as e:
            print(f"[network_runner] {ip} — error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
