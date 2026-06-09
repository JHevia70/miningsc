#!/usr/bin/env python3
"""
extract_hpp_zones.py
====================
Reads HPP JSON files for all Stanton + Pyro bodies and extracts
which minerals have biome tags, and which biome tag they spawn in.

Usage:
  python extract_hpp_zones.py
"""

import json
import sys
from pathlib import Path

HPP_DIRS = [
    Path(r"F:\SC_temp\dcb_unfiltered\libs\foundry\records\harvestable\providerpresets\system\stanton"),
    Path(r"F:\SC_temp\dcb_unfiltered\libs\foundry\records\harvestable\providerpresets\system\pyro"),
    Path(r"F:\SC_temp\dcb_unfiltered\libs\foundry\records\harvestable\providerpresets\system\nyx"),
]

# Known biome tag GUIDs (from tagdatabase) — first 8 hex chars
KNOWN_TAGS = {
    "dcb54332": "Acidic",
    "6874072c": "Desert",
    "b2abbc58": "Lunar",
    "bf63f1ed": "Ice",
    "cacaba91": "Crystaline",
    "e2e65028": "Jungle",
    "a9c7f801": "Arctic",
    "3f2a1d90": "Volcanic",
    "4d3e2f1a": "Swamp",
    "f1e2d3c4": "Tundra",
}


def tag_name(record_name: str) -> str:
    """Extract GUID prefix from 'Tag.dcb54332-xxxx-...' and look up name."""
    if not record_name:
        return "?"
    # Format: Tag.dcb54332-ceab-48f1-a3f5-37...
    guid = record_name.replace("Tag.", "").split("-")[0].lower()
    return KNOWN_TAGS.get(guid, f"?{guid[:8]}")


def normalize_mineral(path_or_name: str) -> str:
    """Get a clean mineral name from a harvestable file path."""
    stem = path_or_name.split("/")[-1].replace(".json", "")
    # Remove prefixes like mining_common_, groundvehiclemining_, fpsmining_
    for prefix in ["mining_legendary_", "mining_epic_", "mining_common_", "mining_uncommon_",
                   "mining_rare_", "groundvehiclemining_", "fpsmining_", "mining_"]:
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    # Capitalize
    return stem.capitalize()


def extract_mineral_tags(hpp_path: Path) -> dict[str, str]:
    """Returns mineral_name -> biome tag name."""
    with open(hpp_path, encoding="utf-8") as f:
        data = json.load(f)

    rv = data.get("_RecordValue_", data)
    result: dict[str, str] = {}

    groups = rv.get("harvestableGroups", [])
    for group in groups:
        harvs = group.get("harvestables", group.get("harvestableItems", []))
        for h in harvs:
            ref = h.get("harvestable", "") or h.get("name", "")
            mineral = normalize_mineral(ref)
            geos = h.get("geometries", [])
            if geos:
                tag_rec = geos[0].get("tag", {})
                if isinstance(tag_rec, dict):
                    rec_name = tag_rec.get("_RecordName_", "")
                    result[mineral] = tag_name(rec_name)
                elif isinstance(tag_rec, str):
                    result[mineral] = tag_name(tag_rec)

    return result


def main():
    for hpp_dir in HPP_DIRS:
        if not hpp_dir.exists():
            continue
        hpp_files = sorted(hpp_dir.glob("hpp_*.json"))
        for hpp_path in hpp_files:
            body = hpp_path.stem.replace("hpp_", "")

            try:
                mineral_tags = extract_mineral_tags(hpp_path)
            except Exception as e:
                print(f"[{body}] ERROR: {e}")
                continue

            if not mineral_tags:
                print(f"[{body}] (no minerals)")
                continue

            # Group minerals by biome tag
            tag_to_minerals: dict[str, list[str]] = {}
            for mineral, tag in sorted(mineral_tags.items()):
                tag_to_minerals.setdefault(tag, []).append(mineral)

            print(f"\n[{body}]")
            for tag, minerals in sorted(tag_to_minerals.items()):
                print(f"  {tag}: {minerals}")


if __name__ == "__main__":
    main()
