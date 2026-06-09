#!/usr/bin/env python3
"""
MiningSC — Mineral Spawn Data Pipeline
=======================================
Extracts HarvestableProviderPreset data from Star Citizen's Game2.dcb and
upserts it into the Supabase `mineral_spawns` table.

Usage
-----
  # Full pipeline: extract DCB → parse → upload
  python update_spawn_data.py --p4k "G:/Roberts Space Industries/StarCitizen/StarCitizen/LIVE/Data.p4k" --version 4.1

  # Re-parse already-extracted DCB (skip extraction)
  python update_spawn_data.py --dcb-dir F:/SC_temp/dcb_extracted --version 4.1

  # Parse only, write JSON (no Supabase upload)
  python update_spawn_data.py --dcb-dir F:/SC_temp/dcb_extracted --version 4.1 --dry-run

  # Show diff vs current DB without writing
  python update_spawn_data.py --dcb-dir F:/SC_temp/dcb_extracted --version 4.1 --diff-only

Environment variables (or .env file)
-------------------------------------
  SUPABASE_URL       https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY   <service_role key>
  STARBREAKER_EXE    path to starbreaker.exe  (default: auto-detect)
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

TOOLS_DIR    = Path(__file__).parent
BODY_MAP_FILE    = TOOLS_DIR / "body_map.json"
MINERAL_MAP_FILE = TOOLS_DIR / "mineral_map.json"

DEFAULT_STARBREAKER_LOCATIONS = [
    Path(r"F:\SC_temp\starbreaker\starbreaker.exe"),
    Path(r"C:\tools\starbreaker\starbreaker.exe"),
    Path(r"C:\SC_tools\starbreaker.exe"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_starbreaker() -> Path:
    # Check env first
    env_path = os.environ.get("STARBREAKER_EXE")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    for loc in DEFAULT_STARBREAKER_LOCATIONS:
        if loc.exists():
            return loc
    raise FileNotFoundError(
        "starbreaker.exe not found. Set STARBREAKER_EXE env var or place it in a known location."
    )


def extract_dcb(p4k: Path, out_dir: Path) -> Path:
    """Extract all Game2.dcb records to out_dir using StarBreaker."""
    sb = find_starbreaker()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[extract] {p4k} → {out_dir}")
    print("[extract] Extracting DCB (this takes ~1-2 min)…")

    result = subprocess.run(
        [str(sb), "dcb", "extract", "--p4k", str(p4k), "--output", str(out_dir), "--format", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("StarBreaker extraction failed.")

    records_dir = out_dir / "libs" / "foundry" / "records"
    if not records_dir.exists():
        raise RuntimeError(f"Expected records dir not found: {records_dir}")

    print(f"[extract] Done.")
    return records_dir


# ── Parsing ───────────────────────────────────────────────────────────────────

def mineral_from_name(name: str, mineral_map: dict) -> str | None:
    name_lower = name.lower()
    for key, canonical in mineral_map.items():
        if key.startswith("_"):
            continue
        if key in name_lower:
            return canonical
    return None


def mining_type_from_group(group_name: str) -> str:
    gn = group_name.lower()
    if "spaceship" in gn or "spaceshipmineables" in gn:
        return "ship_asteroid"
    if "surface" in gn or "shipmineable" in gn:
        return "ship_surface"
    if "fps" in gn:
        return "fps"
    if "groundvehicle" in gn or "ground" in gn:
        return "ground_vehicle"
    return "unknown"


def parse_hpp(filepath: Path, mineral_map: dict) -> list[dict]:
    data = load_json(filepath)
    rv = data.get("_RecordValue_", {})
    groups = rv.get("harvestableGroups", [])

    rows = []
    for group in groups:
        group_name = group.get("groupName", "")
        group_prob = group.get("groupProbability", 0.0)
        mining_type = mining_type_from_group(group_name)

        harvestables = group.get("harvestables", [])
        total_rel = sum(h.get("relativeProbability", 0.0) for h in harvestables)

        for h in harvestables:
            path_ref = h.get("harvestable", "") or ""
            if not path_ref:
                continue
            preset = path_ref.split("/")[-1].replace(".json", "")
            # Only process mining harvestables — skip plants, salvage, etc.
            if not any(preset.startswith(pfx) for pfx in ("mining_", "fpsmining_", "groundvehiclemining_")):
                continue
            mineral = mineral_from_name(preset, mineral_map)
            if not mineral:
                continue

            rel = h.get("relativeProbability", 0.0)
            norm = round(rel / total_rel * 100, 2) if total_rel > 0 else 0.0

            rows.append({
                "mineral":      mineral,
                "mining_type":  mining_type,
                "group_prob":   group_prob,
                "spawn_prob_pct": norm,
                "source":       filepath.stem,
            })
    return rows


def parse_all(records_dir: Path, body_map: dict, mineral_map: dict, version: str) -> list[dict]:
    skip = set(body_map.get("_skip", []))
    hpp_dir = records_dir / "harvestable" / "providerpresets" / "system"

    # body_name → {mineral_mtype_key → best row}  (de-duplicate by taking highest prob)
    by_body: dict[str, dict[str, dict]] = {}
    unknown_hpp: list[str] = []

    for hpp_file in sorted(hpp_dir.rglob("hpp_*.json")):
        stem = hpp_file.stem
        if stem in skip:
            continue

        body_info = body_map.get(stem)
        if not body_info:
            unknown_hpp.append(stem)
            continue

        rows = parse_hpp(hpp_file, mineral_map)
        body_name = body_info["name"]

        if body_name not in by_body:
            by_body[body_name] = {}

        for row in rows:
            key = f"{row['mineral']}_{row['mining_type']}"
            existing = by_body[body_name].get(key)
            # Keep highest spawn_prob_pct when multiple HPPs map to same body
            if not existing or row["spawn_prob_pct"] > existing["spawn_prob_pct"]:
                by_body[body_name][key] = {
                    "system":         body_info["system"],
                    "body":           body_name,
                    "body_type":      body_info["type"],
                    "parent_body":    body_info.get("parent"),
                    "mineral":        row["mineral"],
                    "mining_type":    row["mining_type"],
                    "spawn_prob_pct": row["spawn_prob_pct"],
                    "group_prob":     row["group_prob"],
                    "data_version":   version,
                    "source_file":    row["source"],
                }

    if unknown_hpp:
        print(f"[parse] WARNING: {len(unknown_hpp)} HPP files not in body_map.json:")
        for s in unknown_hpp:
            print(f"         {s}")
        print("         Add them to tools/body_map.json or tools/body_map.json '_skip' list.")

    # Flatten
    db_rows = []
    for body_name in sorted(by_body):
        for key in sorted(by_body[body_name]):
            db_rows.append(by_body[body_name][key])

    return db_rows


# ── Supabase upload ───────────────────────────────────────────────────────────

def load_env():
    """Load .env from project root if present."""
    env_file = TOOLS_DIR.parent / ".env"
    if not env_file.exists():
        env_file = TOOLS_DIR.parent / "web" / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def upsert_to_supabase(rows: list[dict], version: str):
    try:
        from supabase import create_client
    except ImportError:
        print("[upload] ERROR: supabase-py not installed. Run: pip install supabase")
        sys.exit(1)

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("[upload] ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars (or in .env / .env.local).")
        sys.exit(1)

    sb = create_client(url, key)

    print(f"[upload] Deleting existing rows for version={version}…")
    sb.table("mineral_spawns").delete().eq("data_version", version).execute()

    print(f"[upload] Inserting {len(rows)} rows…")
    # Insert in batches of 500
    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        sb.table("mineral_spawns").insert(batch).execute()
        print(f"[upload]   {min(i + batch_size, len(rows))}/{len(rows)}")

    print("[upload] Done.")


def diff_vs_db(new_rows: list[dict]):
    """Print a human-readable diff of what would change."""
    try:
        from supabase import create_client
    except ImportError:
        print("[diff] ERROR: supabase-py not installed. Run: pip install supabase")
        return

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    # diff only needs read access — anon key is enough
    key = (os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY"))
    if not url or not key:
        print("[diff] Cannot connect: no Supabase credentials.")
        return

    sb = create_client(url, key)
    existing = sb.table("mineral_spawns").select("body,mineral,mining_type,spawn_prob_pct,data_version").execute().data

    existing_keys = {(r["body"], r["mineral"], r["mining_type"]) for r in existing}
    new_keys      = {(r["body"], r["mineral"], r["mining_type"]) for r in new_rows}

    added   = new_keys - existing_keys
    removed = existing_keys - new_keys

    changed = []
    ex_map = {(r["body"], r["mineral"], r["mining_type"]): float(r["spawn_prob_pct"]) for r in existing}
    for r in new_rows:
        k = (r["body"], r["mineral"], r["mining_type"])
        if k in ex_map and abs(ex_map[k] - r["spawn_prob_pct"]) > 0.01:
            changed.append((k, ex_map[k], r["spawn_prob_pct"]))

    print(f"\n=== DIFF vs current DB ===")
    print(f"  Added:   {len(added)}")
    print(f"  Removed: {len(removed)}")
    print(f"  Changed: {len(changed)}")

    if added:
        print("\nNEW entries:")
        for b, m, mt in sorted(added):
            prob = next(r["spawn_prob_pct"] for r in new_rows if r["body"]==b and r["mineral"]==m and r["mining_type"]==mt)
            print(f"  + {b:20s} {m:20s} {mt:15s} {prob:.1f}%")

    if removed:
        print("\nREMOVED entries:")
        for b, m, mt in sorted(removed):
            print(f"  - {b:20s} {m:20s} {mt:15s}")

    if changed:
        print("\nCHANGED probabilities:")
        for (b, m, mt), old, new in sorted(changed):
            print(f"  ~ {b:20s} {m:20s} {mt:15s} {old:.1f}% -> {new:.1f}%")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="MiningSC spawn data pipeline")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--p4k",     type=Path, help="Path to Data.p4k (triggers DCB extraction)")
    src.add_argument("--dcb-dir", type=Path, help="Already-extracted DCB directory (skips extraction)")

    ap.add_argument("--version",   default="4.x", help="SC version string stored in DB (default: 4.x)")
    ap.add_argument("--out",       type=Path, default=None, help="Save parsed JSON to this file")
    ap.add_argument("--dry-run",   action="store_true", help="Parse only, do not upload to Supabase")
    ap.add_argument("--diff-only", action="store_true", help="Show diff vs DB, do not upload")
    ap.add_argument("--extract-dir", type=Path, default=Path(r"F:\SC_temp\dcb_extracted"),
                    help="Where to extract DCB when --p4k is used")
    args = ap.parse_args()

    load_env()
    body_map    = load_json(BODY_MAP_FILE)
    mineral_map = load_json(MINERAL_MAP_FILE)

    # ── Step 1: locate records dir ────────────────────────────────────────────
    if args.p4k:
        extract_dcb(args.p4k, args.extract_dir)
        records_dir = args.extract_dir / "libs" / "foundry" / "records"
    elif args.dcb_dir:
        # Could be the root (contains libs/) or already the records dir
        candidate = args.dcb_dir / "libs" / "foundry" / "records"
        if candidate.exists():
            records_dir = candidate
        elif (args.dcb_dir / "harvestable").exists():
            records_dir = args.dcb_dir
        else:
            print(f"ERROR: Cannot find records dir under {args.dcb_dir}")
            sys.exit(1)
    else:
        # Default: use already-extracted files from previous session
        default = Path(r"F:\SC_temp\dcb_unfiltered\libs\foundry\records")
        if default.exists():
            records_dir = default
            print(f"[info] Using default records dir: {records_dir}")
        else:
            print("ERROR: Provide --p4k or --dcb-dir")
            ap.print_help()
            sys.exit(1)

    # ── Step 2: parse ─────────────────────────────────────────────────────────
    print(f"[parse] records dir: {records_dir}")
    rows = parse_all(records_dir, body_map, mineral_map, args.version)
    print(f"[parse] {len(rows)} rows across {len(set(r['body'] for r in rows))} bodies, "
          f"{len(set(r['mineral'] for r in rows))} minerals.")

    # ── Step 3: optional JSON output ──────────────────────────────────────────
    out_path = args.out or (TOOLS_DIR / f"mining_spawn_data_{args.version.replace('.','_')}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"[parse] Saved to {out_path}")

    # ── Step 4: diff or upload ────────────────────────────────────────────────
    if args.diff_only:
        diff_vs_db(rows)
        return

    if args.dry_run:
        print("[dry-run] Skipping Supabase upload.")
        return

    upsert_to_supabase(rows, args.version)


if __name__ == "__main__":
    # Handle --p4k path with star-breaker extraction inline
    sys.argv  # just to reference
    main()
