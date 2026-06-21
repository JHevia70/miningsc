#!/usr/bin/env python3
"""Upload sh_ccus_clean.json to Supabase via the sync-sh edge function (action=load)."""
import json, sys, time
from pathlib import Path
import urllib.request, urllib.error

CACHE       = Path("F:/SC_temp/sh_ccus_clean.json")
EDGE_URL    = "https://dtfkyacafqkrbyhgoxjk.supabase.co/functions/v1/sync-sh"
SYNC_SECRET = "b174c47090b8c16cb14b0fe70409ec226aa9ff1429a492e0691a420d0014ed2a"
ANON_KEY    = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
               ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR0Zmt5YWNhZnFrcmJ5aGdveGprIiwi"
               "cm9sZSI6ImFub24iLCJpYXQiOjE3NzgxNzQ2OTUsImV4cCI6MjA5Mzc1MDY5NX0"
               ".gKpTVsoleSQ9M7uXM-9glz2eINgnlto8EA7CF4LQKjE")

BATCH = 2000  # send in chunks to avoid payload size limits

with open(CACHE, encoding="utf-8") as f:
    data = json.load(f)

edges      = data["edges"]
scraped_at = data["scraped_at"]
print(f"Loaded {len(edges)} clean edges")

headers = {
    "x-sync-secret": SYNC_SECRET,
    "Authorization":  f"Bearer {ANON_KEY}",
    "Content-Type":   "application/json",
}

# Step 1: truncate
print("Truncating table...")
req = urllib.request.Request(EDGE_URL, data=b'{"action":"truncate"}', headers=headers, method="POST")
with urllib.request.urlopen(req, timeout=30) as resp:
    print(f"  {json.loads(resp.read())}")

# Step 2: insert in batches
total = 0
for i in range(0, len(edges), BATCH):
    chunk = edges[i:i+BATCH]
    payload = json.dumps({
        "action":     "load",
        "scraped_at": scraped_at,
        "edges":      chunk,
    }).encode("utf-8")
    req = urllib.request.Request(EDGE_URL, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            total += result.get("inserted", len(chunk))
            print(f"  batch {i//BATCH + 1}: +{result.get('inserted', '?')} total={total}")
            if i + BATCH < len(edges):
                time.sleep(0.5)
    except urllib.error.HTTPError as e:
        print(f"  ERROR batch {i}: {e.code} {e.read().decode()}")
        sys.exit(1)

print(f"\nDone — {total} rows in sh_ccus.")
