#!/usr/bin/env python3
"""
Star Hangar CCU Path Optimizer
================================
Finds the cheapest sequence of Cross-Chassis Upgrades between two ships
using Dijkstra's algorithm on the scraped price graph.

Usage
-----
  python sh_optimizer.py "Hull B" "Galaxy"
  python sh_optimizer.py "Aurora MR" "Carrack" --max-hops 4
  python sh_optimizer.py "Hull B" "Galaxy" --top 5       # show top 5 paths
  python sh_optimizer.py --list                           # list all known ships
  python sh_optimizer.py --from "Hull B" --show-all      # all paths from Hull B
  python sh_optimizer.py --cache F:/SC_temp/sh_ccus.json "Hull B" "Galaxy"

The script reads F:/SC_temp/sh_ccus.json by default (produced by sh_scraper.py).
"""

import io
import json
import heapq
import argparse
import sys
from pathlib import Path
from collections import defaultdict

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFAULT_CACHE = Path("F:/SC_temp/sh_ccus.json")
MAX_HOPS_DEFAULT = 6


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph(edges: list[dict]) -> dict[str, list[tuple[float, str]]]:
    """Adjacency list: graph[from] = [(price, to), ...]"""
    graph: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for e in edges:
        graph[e["from"]].append((e["price"], e["to"]))
    return graph


def all_ships(edges: list[dict]) -> list[str]:
    names = set()
    for e in edges:
        names.add(e["from"])
        names.add(e["to"])
    # Deduplicate case-insensitively: keep one canonical form per name
    canonical: dict[str, str] = {}
    for name in names:
        key = name.lower()
        if key not in canonical:
            canonical[key] = name
        else:
            # Prefer title-case / longer form
            if len(name) > len(canonical[key]):
                canonical[key] = name
    return sorted(canonical.values(), key=str.casefold)


# ---------------------------------------------------------------------------
# Dijkstra — finds cheapest path, respecting max_hops
# ---------------------------------------------------------------------------

def dijkstra(
    graph: dict[str, list[tuple[float, str]]],
    start: str,
    end: str,
    max_hops: int = MAX_HOPS_DEFAULT,
) -> list[tuple[float, list[str]]]:
    """
    Returns the single cheapest path as [(total_cost, [ship0, ship1, ...])] or [].
    State: (cost, hops, current_node, path)
    """
    # (cost, hops, node, path)
    heap = [(0.0, 0, start, [start])]
    visited: dict[tuple[str, int], float] = {}  # (node, hops) → best cost

    best: list[tuple[float, list[str]]] = []

    while heap:
        cost, hops, node, path = heapq.heappop(heap)

        if node == end:
            best.append((cost, path))
            return best  # Dijkstra guarantees first hit is optimal

        if hops >= max_hops:
            continue

        state = (node, hops)
        if state in visited and visited[state] <= cost:
            continue
        visited[state] = cost

        for edge_cost, neighbor in graph.get(node, []):
            if neighbor not in path:  # no cycles
                heapq.heappush(heap, (cost + edge_cost, hops + 1, neighbor, path + [neighbor]))

    return []  # no path found


def k_shortest_paths(
    graph: dict[str, list[tuple[float, str]]],
    start: str,
    end: str,
    k: int = 5,
    max_hops: int = MAX_HOPS_DEFAULT,
) -> list[tuple[float, list[str]]]:
    """
    Yen's-style k-shortest paths using a modified Dijkstra with path tracking.
    Returns up to k paths sorted by cost.
    """
    # (cost, hops, node, path)
    heap = [(0.0, 0, start, [start])]
    results: list[tuple[float, list[str]]] = []
    # Allow revisiting nodes across different paths but not within one path
    count: dict[str, int] = defaultdict(int)

    while heap and len(results) < k:
        cost, hops, node, path = heapq.heappop(heap)

        count[node] += 1
        if count[node] > k:
            continue

        if node == end:
            results.append((cost, path))
            continue

        if hops >= max_hops:
            continue

        for edge_cost, neighbor in graph.get(node, []):
            if neighbor not in path:
                heapq.heappush(heap, (cost + edge_cost, hops + 1, neighbor, path + [neighbor]))

    return results


# ---------------------------------------------------------------------------
# Fuzzy ship name matching
# ---------------------------------------------------------------------------

def find_ship(name: str, known: list[str]) -> str | None:
    name_l = name.lower()
    # Exact match (case-insensitive)
    for s in known:
        if s.lower() == name_l:
            return s
    # Substring match
    matches = [s for s in known if name_l in s.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous ship name '{name}'. Matches:")
        for m in matches:
            print(f"  - {m}")
        return None
    return None


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def fmt_path(path: list[str], cost: float, edge_map: dict[tuple[str, str], float]) -> str:
    lines = []
    cumulative = 0.0
    for i in range(len(path) - 1):
        frm, to = path[i], path[i + 1]
        step_cost = edge_map.get((frm, to), 0.0)
        cumulative += step_cost
        lines.append(f"  {frm:35s} → {to:35s}  ${step_cost:>8.2f}   (acum. ${cumulative:>8.2f})")
    lines.append(f"  {'TOTAL':35s}   {'':35s}  ${cost:>8.2f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Find cheapest CCU upgrade path on Star Hangar")
    ap.add_argument("ships", nargs="*", help="FROM_SHIP TO_SHIP (positional)")
    ap.add_argument("--from",   dest="from_ship", help="Source ship")
    ap.add_argument("--to",     dest="to_ship",   help="Target ship")
    ap.add_argument("--cache",  default=str(DEFAULT_CACHE), help="Path to sh_ccus.json")
    ap.add_argument("--top",    type=int, default=3, help="Show top N paths (default 3)")
    ap.add_argument("--max-hops", type=int, default=MAX_HOPS_DEFAULT,
                    help=f"Max intermediate ships (default {MAX_HOPS_DEFAULT})")
    ap.add_argument("--list",   action="store_true", help="List all ships in cache")
    ap.add_argument("--show-all", action="store_true",
                    help="Show all direct upgrades from --from ship")
    args = ap.parse_args()

    cache_path = Path(args.cache)
    if not cache_path.exists():
        print(f"Cache not found: {cache_path}")
        print("Run sh_scraper.py first to build the price cache.")
        sys.exit(1)

    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)

    edges = data["edges"]
    scraped_at = data.get("scraped_at", "unknown")
    print(f"Loaded {len(edges)} CCU edges (scraped {scraped_at[:19]})\n")

    ships = all_ships(edges)
    graph = build_graph(edges)
    edge_map = {(e["from"], e["to"]): e["price"] for e in edges}

    # --list
    if args.list:
        print(f"Known ships ({len(ships)}):")
        for s in ships:
            print(f"  {s}")
        return

    # Resolve ship names
    from_name = args.from_ship or (args.ships[0] if len(args.ships) >= 1 else None)
    to_name   = args.to_ship   or (args.ships[1] if len(args.ships) >= 2 else None)

    if from_name is None:
        ap.print_help()
        return

    from_ship = find_ship(from_name, ships)
    if from_ship is None:
        print(f"Ship not found: '{from_name}'\nUse --list to see available ships.")
        sys.exit(1)

    # --show-all: list all direct 1-hop upgrades from this ship
    if args.show_all or to_name is None:
        direct = sorted(graph.get(from_ship, []), key=lambda x: x[0])
        if not direct:
            print(f"No direct upgrades found from '{from_ship}'.")
        else:
            print(f"Direct upgrades from '{from_ship}' ({len(direct)} options):\n")
            for price, dest in direct:
                print(f"  ${price:>8.2f}  →  {dest}")
        return

    to_ship = find_ship(to_name, ships)
    if to_ship is None:
        print(f"Ship not found: '{to_name}'\nUse --list to see available ships.")
        sys.exit(1)

    print(f"Finding cheapest upgrade path:  {from_ship}  →  {to_ship}")
    print(f"Max hops: {args.max_hops}   Top paths: {args.top}\n")

    # Check direct path first
    direct_price = edge_map.get((from_ship, to_ship))
    if direct_price is not None:
        print(f"Direct CCU available:  ${direct_price:.2f}\n")

    # Find top N paths
    paths = k_shortest_paths(graph, from_ship, to_ship, k=args.top, max_hops=args.max_hops)

    if not paths:
        print(f"No upgrade path found from '{from_ship}' to '{to_ship}' "
              f"within {args.max_hops} hops.")
        print("Try increasing --max-hops or check --list for ship names.")
        return

    print(f"Top {len(paths)} cheapest paths:\n")
    print(f"  {'─'*90}")
    for rank, (cost, path) in enumerate(paths, 1):
        hops = len(path) - 1
        label = "DIRECT" if hops == 1 else f"{hops} hops"
        saving = ""
        if direct_price and hops > 1:
            diff = direct_price - cost
            saving = f"  (saves ${diff:.2f} vs direct)" if diff > 0 else f"  (+${-diff:.2f} vs direct)"
        print(f"\n  #{rank}  [{label}]  Total: ${cost:.2f}{saving}")
        print(f"  {'─'*90}")
        print(fmt_path(path, cost, edge_map))

    print()

    # Summary comparison
    if direct_price and len(paths) > 0:
        best_cost, best_path = paths[0]
        if len(best_path) > 2 and best_cost < direct_price:
            saving = direct_price - best_cost
            print(f"  Recommendation: take the {len(best_path)-1}-hop path and save ${saving:.2f} "
                  f"vs the direct CCU (${direct_price:.2f})")
        elif direct_price is not None:
            print(f"  Recommendation: the direct CCU (${direct_price:.2f}) is already optimal.")


if __name__ == "__main__":
    main()
