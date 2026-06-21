#!/usr/bin/env python3
"""Upload sh_ccus_clean.json to Supabase via REST with service role key.
The service role key is passed via SUPABASE_SERVICE_KEY env var.
"""
import json, os, sys, time
from pathlib import Path
import urllib.request, urllib.error

CACHE = Path("F:/SC_temp/sh_ccus_clean.json")
URL   = "https://dtfkyacafqkrbyhgoxjk.supabase.co"
KEY   = os.environ["SUPABASE_SERVICE_KEY"]
BATCH = 500

with open(CACHE, encoding="utf-8") as f:
    data = json.load(f)

scraped_at = data["scraped_at"]
rows = [
    {"from_ship": e["from"], "to_ship": e["to"], "price": e["price"], "scraped_at": scraped_at}
    for e in data["edges"]
]
print(f"Loaded {len(rows)} edges (scraped {scraped_at[:19]})")

headers = {
    "apikey":        KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates",
}

total = 0
for i in range(0, len(rows), BATCH):
    batch = rows[i:i+BATCH]
    body  = json.dumps(batch).encode("utf-8")
    req   = urllib.request.Request(f"{URL}/rest/v1/sh_ccus", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req):
            total += len(batch)
            sys.stdout.write(f"\r  {total}/{len(rows)}")
            sys.stdout.flush()
    except urllib.error.HTTPError as e:
        print(f"\n  ERROR batch {i}: {e.code} {e.read().decode()}")
        sys.exit(1)

print(f"\nDone — {total} rows uploaded.")
