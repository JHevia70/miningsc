#!/usr/bin/env python3
"""Upload F:/SC_temp/sh_ccus.json to Supabase sh_ccus table."""
import json, os, sys
from pathlib import Path
from supabase import create_client

CACHE = Path("F:/SC_temp/sh_ccus.json")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
BATCH = 500

with open(CACHE, encoding="utf-8") as f:
    data = json.load(f)

scraped_at = data["scraped_at"]
edges = data["edges"]
print(f"Loaded {len(edges)} edges (scraped {scraped_at[:19]})")

rows = [
    {"from_ship": e["from"], "to_ship": e["to"], "price": e["price"], "scraped_at": scraped_at}
    for e in edges
]

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
total = 0
for i in range(0, len(rows), BATCH):
    batch = rows[i:i+BATCH]
    res = sb.table("sh_ccus").upsert(batch, on_conflict="from_ship,to_ship").execute()
    total += len(batch)
    print(f"  {total}/{len(rows)} upserted")

print(f"Done — {total} rows in sh_ccus.")
