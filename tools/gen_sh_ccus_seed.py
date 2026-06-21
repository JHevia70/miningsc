#!/usr/bin/env python3
"""Generate SQL seed file for sh_ccus from F:/SC_temp/sh_ccus.json."""
import json
from pathlib import Path

IN  = Path("F:/SC_temp/sh_ccus_clean.json")
OUT = Path("F:/SC_temp/sh_ccus_seed.sql")

with open(IN, encoding="utf-8") as f:
    data = json.load(f)

scraped_at = data["scraped_at"]
edges = data["edges"]
print(f"Loaded {len(edges)} edges (scraped {scraped_at[:19]})")

def esc(s):
    return s.replace("'", "''")

lines = []
for e in edges:
    lines.append(f"('{esc(e['from'])}', '{esc(e['to'])}', {e['price']}, '{scraped_at}')")

sql = (
    "INSERT INTO public.sh_ccus (from_ship, to_ship, price, scraped_at) VALUES\n"
    + ",\n".join(lines)
    + "\nON CONFLICT (from_ship, to_ship) DO UPDATE"
    + " SET price = EXCLUDED.price, scraped_at = EXCLUDED.scraped_at;\n"
)

OUT.write_text(sql, encoding="utf-8")
print(f"Written {len(edges)} rows to {OUT}")
