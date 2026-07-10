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
ACTIVE_WINDOW_DAYS = 7
POLL_INTERVAL_S = 3
POLL_TIMEOUT_S = 120


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


def _create_measurement(ip: str) -> str:
    body = {
        "target": ip,
        "type": "mtr",
        "measurementOptions": {"protocol": "TCP", "port": 443},
        "locations": [{"country": c, "limit": 1} for c in COUNTRIES],
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
    """Return the last hop with 0% loss and real timings — the closest
    reachable point before the server's firewall drops everything."""
    best = None
    for i, hop in enumerate(hops):
        stats = hop.get("stats") or {}
        if stats.get("loss") == 0 and stats.get("avg") is not None:
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


def _rows_for_result(server_ip_id: int, measurement: dict) -> list[dict]:
    rows = []
    measured_at = datetime.now(timezone.utc).isoformat()
    for entry in measurement.get("results", []):
        probe = entry.get("probe", {})
        result = entry.get("result", {})
        hops = result.get("hops") or []
        hop = _last_reachable_hop(hops)
        if hop is None:
            print(f"  [{probe.get('country')}] no reachable hop")
            continue
        rows.append({
            "server_ip_id":  server_ip_id,
            "probe_country": probe.get("country"),
            "probe_city":    probe.get("city"),
            "measured_at":   measured_at,
            **hop,
        })
        print(f"  [{probe.get('country')}] hop#{hop['hop_index']} "
              f"{hop['hop_address']} avg={hop['rtt_avg_ms']}ms loss={hop['packet_loss_pct']}%")
    return rows


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
            print(f"[network_runner] {ip} — creating measurement")
            msm_id = _create_measurement(ip)
            measurement = _poll_measurement(msm_id)
            rows = _rows_for_result(server["id"], measurement)
            if rows:
                sb.table("ping_results").insert(rows).execute()
                print(f"[network_runner] {ip} — inserted {len(rows)} row(s)")
        except Exception as e:
            print(f"[network_runner] {ip} — error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
