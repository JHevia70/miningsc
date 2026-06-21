"""
Reads orbital-data.ts and upserts all celestial bodies into Supabase.
Usage:
    python tools/seed_celestial_bodies.py
Requires: SUPABASE_URL and SUPABASE_SERVICE_KEY env vars (or .env file).
"""
import os, re, json, sys
from pathlib import Path

try:
    from supabase import create_client
except ImportError:
    print("pip install supabase")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / "web" / ".env.local")
except ImportError:
    pass

URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not URL or not KEY:
    print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY (or NEXT_PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_KEY)")
    sys.exit(1)

# ── Parse orbital-data.ts ─────────────────────────────────────────────────────
TS_FILE = Path(__file__).parent.parent / "web" / "src" / "lib" / "orbital-data.ts"
src = TS_FILE.read_text(encoding="utf-8")

# Extract each object literal from the arrays
# Matches: { key: "...", name: "...", ... }
obj_re = re.compile(r'\{([^{}]+)\}', re.DOTALL)

def extract_str(text, field):
    m = re.search(rf'{field}\s*:\s*"([^"]*)"', text)
    return m.group(1) if m else None

def extract_num(text, field):
    m = re.search(rf'{field}\s*:\s*([-\d_\.]+)', text)
    if not m: return None
    return float(m.group(1).replace('_', ''))

def extract_null_or_num(text, field):
    m = re.search(rf'{field}\s*:\s*([-\d_\.]+|null)', text)
    if not m: return None
    v = m.group(1)
    if v == 'null': return None
    return float(v.replace('_', ''))

rows = []
for m in obj_re.finditer(src):
    block = m.group(1)
    key = extract_str(block, 'key')
    if not key:
        continue
    name    = extract_str(block, 'name')
    btype   = extract_str(block, 'type')
    system  = extract_str(block, 'system')
    parent  = extract_str(block, 'parent')
    orb     = extract_num(block, 'orbital_radius_km')
    angle   = extract_null_or_num(block, 'angle_deg')
    lat     = extract_null_or_num(block, 'lat_deg')
    radius  = extract_num(block, 'body_radius_km')
    color   = extract_str(block, 'color')
    texture = extract_str(block, 'texture')

    if not all([key, name, btype, system]):
        continue
    if orb is None:
        continue

    rows.append({
        "key":               key,
        "name":              name,
        "type":              btype,
        "system":            system,
        "parent_key":        parent if parent != "null" else None,
        "orbital_radius_km": orb,
        "angle_deg":         angle,
        "lat_deg":           lat,
        "body_radius_km":    radius or 1,
        "color":             color,
        "texture":           texture,
    })

print(f"Parsed {len(rows)} bodies from orbital-data.ts")

# ── Upsert to Supabase ────────────────────────────────────────────────────────
sb = create_client(URL, KEY)

# Insert in two passes: parents first, then children (to satisfy FK)
# Pass 1: bodies with no parent (stars)
# Pass 2: everything else
def upsert_batch(batch):
    if not batch:
        return
    res = sb.table("celestial_bodies").upsert(batch, on_conflict="key").execute()
    return res

stars   = [r for r in rows if r["parent_key"] is None]
others  = [r for r in rows if r["parent_key"] is not None]

print(f"  Stars/roots: {len(stars)}")
upsert_batch(stars)

# Planets (parent = star key)
star_keys = {r["key"] for r in stars}
planets   = [r for r in others if r["parent_key"] in star_keys]
rest      = [r for r in others if r["parent_key"] not in star_keys]

print(f"  Planets/L-points: {len(planets)}")
upsert_batch(planets)

print(f"  Moons/sub-stations: {len(rest)}")
upsert_batch(rest)

print(f"Done. {len(rows)} rows upserted to celestial_bodies.")
