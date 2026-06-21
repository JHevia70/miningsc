#!/usr/bin/env python3
"""
Re-normalise ship names in F:/SC_temp/sh_ccus.json.

Strategy:
  1. Names starting with "NNNN BIS Upgrade - " are BIS editions → strip that prefix,
     keep the result as a special ship name like "2952 BIS - Aurora LX".
  2. All other noise (insurance, Upgrade suffix, extras, manufacturer prefix) → strip.
  3. Deduplicate keeping lowest price per (from, to) pair.
  4. Self-loops after normalization → discarded.
"""
import re, json
from pathlib import Path

IN  = Path("F:/SC_temp/sh_ccus.json")
OUT = Path("F:/SC_temp/sh_ccus_clean.json")
SQL = Path("F:/SC_temp/sh_ccus_seed.sql")

# ---------------------------------------------------------------------------
# Step 1 — BIS prefix normaliser:
#   "2952 BIS Upgrade - Aurora LX"  → "Aurora LX BIS 2952"
#   "Carrack BIS 2952 Upgrade"       → "Carrack BIS 2952"
#   "Carrack Best In Show 2952 Upgrade" → "Carrack Best In Show 2952"
# These produce distinct ship names that survive later stripping.
# ---------------------------------------------------------------------------
_BIS_LEAD = re.compile(r'^(\d{4})\s+BIS\s+Upgrade\s*[-–]\s*', re.IGNORECASE)

def _apply_bis_lead(name: str) -> str:
    m = _BIS_LEAD.match(name)
    if m:
        year = m.group(1)
        ship = name[m.end():].strip()
        return f"{ship} BIS {year}"
    return name

# ---------------------------------------------------------------------------
# Leading noise strips (applied left-to-right, repeated until stable)
# ---------------------------------------------------------------------------
_LEAD = [
    re.compile(r'^"\s*UPGRADE\s*"\s*[-–]\s*',          re.IGNORECASE),
    re.compile(r'^\(CCU\s+Upgrade\)\s*',               re.IGNORECASE),
    re.compile(r'^CCU\s+(?:from|Upgrade\s*[-–]?)\s*',  re.IGNORECASE),
    re.compile(r'^Ship\s+upgrade\s*[-–]\s*',           re.IGNORECASE),
    re.compile(r'^Upgrade\s*[>–-]\s*',                 re.IGNORECASE),
    re.compile(r'^Upgrade\s+from\s+',                  re.IGNORECASE),
    re.compile(r'^Upgrade\s+(?=[A-Z0-9])',             re.IGNORECASE),
    re.compile(r'^Upgrade\s*[-–]\s*',                  re.IGNORECASE),
    re.compile(r'^to\s+',                              re.IGNORECASE),   # "to Reclaimer Best In Show..."
    re.compile(r'^the\s+',                             re.IGNORECASE),   # "the Anvil Carrack"
    re.compile(r'^a\s+(?=[A-Z])',                      re.IGNORECASE),   # "a Redeemer", "a Drake Buccaneer"
    re.compile(r'^(?:RSI|MISC|Anvil|Aegis|Crusader|Argo|Aopoa|Origin|Drake|Mirai|Banu|'
               r'Esperia|Gatac|Kruger|Consolidated Outland|Tumbril|Roberts Space Industries|'
               r'Musashi Industrial|MSIC|CNOU|Agro|Mirau)\s+',
               re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Trailing noise strips (applied in order)
# ---------------------------------------------------------------------------
_TRAIL = [
    # "- Upgrade w/urance!" / "- Upgrade w/ Ship Poster, Exclusive Livery &urance!"
    re.compile(r'\s*[-–]\s*Upgrade\s+w[/&].*$',            re.IGNORECASE),
    # "- Upgrade plus Salvage Career Kit"
    re.compile(r'\s*[-–]\s*Upgrade\s+plus\b.*$',           re.IGNORECASE),
    # "- Upgrade - Foundation Festival..."
    re.compile(r'\s*[-–]\s*Upgrade\s*[-–].*$',             re.IGNORECASE),
    # Plain " Upgrade" or " Upgrade." at very end
    re.compile(r'\s+Upgrade\.?\s*$',                        re.IGNORECASE),
    # "Upgrade Subscriber" leftover
    re.compile(r'\s+Upgrade\s+Subscriber\b.*$',             re.IGNORECASE),
    # Insurance variants
    re.compile(r'\s*[-–+,]\s*(?:With\s+)?(?:Life\s+Time|Life-?Time|LTI)\s+Insurance\b.*$', re.IGNORECASE),
    re.compile(r'\s*\bLTI\b.*$',                            re.IGNORECASE),
    re.compile(r'\s*[-–]\s*(?:with\s+)?\d+\s*(?:yr|year|month)s?\s*ins(?:urance)?\.?\b.*$', re.IGNORECASE),
    re.compile(r'\s*[+,]\s*\d+\s*(?:yr|year|month)s?\s+ins(?:urance)?\.?\b.*$', re.IGNORECASE),
    re.compile(r'\s*[+,]\s*(?:With\s+)?\d+\s*(?:yr|year|month)s?\s+Insurance\b.*$', re.IGNORECASE),
    re.compile(r'\s*,\s*\d+\s*month\s+insurance\b.*$',     re.IGNORECASE),
    re.compile(r'\s*[-–+&]?urance\b.*$',                    re.IGNORECASE),  # +urance, &urance, -urance, withurance
    re.compile(r'\s+with\s*urance\b.*$',                    re.IGNORECASE),
    re.compile(r'\s+Edition\s+w[/&](?:r?u?a?nce|urance)\b.*$', re.IGNORECASE),  # w/ruance, w/urance
    re.compile(r',\s+(?:with|edition)\b.*$',               re.IGNORECASE),   # ", with" / ", Edition ..."
    re.compile(r'\s*[-–]\s*\d+y\s+assurance\b.*$',         re.IGNORECASE),
    re.compile(r'\s*[-–]\s*\d+y\s+assurance\b.*$',         re.IGNORECASE),
    re.compile(r'\s*[-–]\s*\d+y\s+(?:INS|Insurance)\b.*$', re.IGNORECASE),
    re.compile(r'\s*[-–+]\s*\d+\s*(?:yr|year|month)s?\s*(?:ins|insurance)\.?\s*$', re.IGNORECASE),
    re.compile(r'\s*[-–]\s*\+\s*\d+y\s+Insurance\b.*$',   re.IGNORECASE),
    re.compile(r'\s*[-–]\s*\d+m\s+insurance\b.*$',         re.IGNORECASE),
    re.compile(r'\s*\d+m\s+insurance\b.*$',                 re.IGNORECASE),
    re.compile(r'\s*[-–]\s*\d+M\s*$',                      re.IGNORECASE),  # "- 120M" (meses de seguro)
    # Extras
    re.compile(r'\s*[+,]\s*(?:Paint|Poster|Flair|Career Kit|Name Reservation|Module Add-On Kit|Flight Jacket|Flight Ready\b[^)]*)\b.*$', re.IGNORECASE),
    re.compile(r'\s*w/\s*(?:Paint|Poster|Flair|C8X)\b.*$', re.IGNORECASE),
    re.compile(r'\s*with\s+C8X\b.*$',                      re.IGNORECASE),
    re.compile(r'\s*W/?C8X\b.*$',                          re.IGNORECASE),
    re.compile(r'\s*Expedition\s+W(?:/|ith)C8X\b.*$',      re.IGNORECASE),
    re.compile(r'\s*[+,]\s*(?:Cargo|Medical|Salvage)\s+Career Kit\b.*$', re.IGNORECASE),
    re.compile(r'\s*[-–+,]\s*(?:Gear Kit|Foundation Festival)\b.*$', re.IGNORECASE),
    # BIS paint-only editions (not a separate ship, just livery)
    re.compile(r'\s*[-–]\s*\d{4}\s+Best\s+In\s+Show\s+Paint.*$', re.IGNORECASE),
    re.compile(r'\s*[-–]\s*\d{4}\s+BIS\s+Paint.*$',        re.IGNORECASE),
    re.compile(r'\s*\+\s*\d{4}\s+BIS\s+Paint\b.*$',        re.IGNORECASE),
    # Warbond / CCU markers
    re.compile(r'\s*\(Warbond[^)]*\)',                      re.IGNORECASE),
    re.compile(r'\s+Warbond\b',                             re.IGNORECASE),
    re.compile(r'\s+(?:WB)?CCU\b.*$',                      re.IGNORECASE),
    re.compile(r"\s*CCU'ed",                                re.IGNORECASE),
    # "- Best in show 2021" suffix (already-clean BIS ships keep "BIS NNNN" from step 1)
    re.compile(r'\s*[-–]\s*Best\s+in\s+Show\s+\d{4}\b.*$', re.IGNORECASE),
    re.compile(r'\s+Upgrade\s*[-–]\s*Best\s+in\s+Show\b.*$', re.IGNORECASE),
    # Edition suffixes
    re.compile(r'\s+Edition\s*$',                           re.IGNORECASE),
    re.compile(r'\s+Ed\.\s*$',                              re.IGNORECASE),
    # Misc junk
    re.compile(r'\s*Standard Edition$',                     re.IGNORECASE),
    re.compile(r'\s*Pirate Edition$',                       re.IGNORECASE),
    re.compile(r'\s*\+\s*Extras',                           re.IGNORECASE),
    re.compile(r'\s*[-–]\s*Star Citizen.*$',                re.IGNORECASE),
    re.compile(r'\s*[-–]\s*$'),
    re.compile(r'\s+upgrade\s+with\b.*$',                   re.IGNORECASE),  # "Nomad upgrade with"
    re.compile(r'\s+(?:Upg?rade|Update)\s*$',               re.IGNORECASE),  # trailing "Update" / typo "Upagrade"
    re.compile(r'\s*!\s*$'),  # trailing "!"
]

# ---------------------------------------------------------------------------
# Canonical alias table (exact match after all stripping)
# ---------------------------------------------------------------------------
CANONICAL: dict[str, str] = {
    "Hull-A": "Hull A", "Hull-B": "Hull B", "Hull-C": "Hull C",
    "Hull-D": "Hull D", "Hull-E": "Hull E",
    "HULL B": "Hull B", "HULL C": "Hull C", "HULL D": "Hull D", "HULL E": "Hull E",
    "85x": "85X", "135C": "135c",
    "C1 Spirit": "Spirit C1", "A1 Spirit": "Spirit A1", "E1 Spirit": "Spirit E1",
    "A2 Hercules": "Hercules A2", "C2 Hercules": "Hercules C2", "M2 Hercules": "Hercules M2",
    "C2": "Hercules C2",
    "Mole": "MOLE", "Raft": "RAFT",
    "Genesis": "Genesis Starliner",
    "Agro Mole": "MOLE",
    "Paladin to Paladin": "Paladin",
    # Subscriber variants → base ship
    "Prowler Subscriber": "Prowler",
    "Prowler Subscribers": "Prowler",
    "Prowler Subscriber Edition": "Prowler",
    "Mercury Star Runner Subscriber": "Mercury Star Runner",
    "Mercury Star Runner Subscribers": "Mercury Star Runner",
    "Nomad Subscriber": "Nomad",
    "Nomad Subscriber Ed.": "Nomad",
    "Carrack Subscriber Edition": "Carrack",
    "Carrack Subscribers": "Carrack",
    "Carrack Subscribers Edition": "Carrack",
    "125A Subscribers": "125a",
    "600i Explorer Subscribers": "600i Explorer",
    "Talon Subscribers Edition": "Talon",
    "Talon Shrike Subscribers Edition": "Talon Shrike",
    "R Subscribers": "Razor",           # best guess
    "Razor EX Subscribers": "Razor EX",
    "M50 Subscriber Edition": "M50",
    "Sabre Subscriber Edition with bonus": "Sabre",
    "Scorpius - Subscriber Exclusive w/ 24 Months Insurance": "Scorpius",
    # "Grey's Market Shiv" is the base Shiv
    "Grey's Market Shiv": "Shiv",
    # Terrapin Medic
    "Terrapin Medic": "Terrapin Medic",
    # Mirau Guardian MX → Guardian MX
    "Mirau Guardian MX": "Guardian MX",
    # L-21 Wolf
    "L-21 Wolf": "L-21 Wolf",
    # Residual BIS+insurance combos
    "Gladiator w/ 2955 Best in Show Paint & Poster and 120 month insurance": "Gladiator Best In Show 2955",
    "Ironclad + 10y INS": "Ironclad",
    "M80 + 10y Ins": "M80",
    "Mercury BIS 2952 with Red Alert Paint and 10y Insurance": "Mercury BIS 2952",
    # assurance variant
    "Constellation Andromeda - 10y assurance": "Constellation Andromeda",
    "Eclipse withurance": "Eclipse",
    "Perseus withurance": "Perseus",
    "Caterpillar -urance": "Caterpillar",
    "Caterpillar Edition w/urance": "Caterpillar",
    "Guardian MX - + 10y Ins": "Guardian MX",
    "Ironclad 120m ins": "Ironclad",
    "Paladin - + 10y Ins": "Paladin",
    "Ironclad - 120M": "Ironclad",
}


def normalize(raw: str) -> str:
    name = raw.strip()

    # Step 1: BIS Upgrade prefix (e.g. "2953 BIS Upgrade - Defender" → "Defender BIS 2953")
    name = _apply_bis_lead(name)

    # Check alias before stripping
    if name in CANONICAL:
        return CANONICAL[name]

    # Step 2: Leading strips (repeated)
    for _ in range(5):
        prev = name
        for pat in _LEAD:
            name = pat.sub("", name).strip()
        if name == prev:
            break

    # Step 3: Trailing strips (repeated once for chains like "- Upgrade w/urance!")
    for _ in range(2):
        prev = name
        for pat in _TRAIL:
            name = pat.sub("", name).strip()
        if name == prev:
            break

    # Collapse multiple spaces
    name = re.sub(r'\s{2,}', ' ', name).strip()
    # Final alias
    return CANONICAL.get(name, name)


# ---------------------------------------------------------------------------
# Load, renormalize, deduplicate
# ---------------------------------------------------------------------------
with open(IN, encoding="utf-8") as f:
    data = json.load(f)

scraped_at = data["scraped_at"]
best: dict[tuple[str, str], float] = {}

for e in data["edges"]:
    frm = normalize(e["from"])
    to  = normalize(e["to"])
    if frm == to:
        continue
    key = (frm, to)
    if key not in best or e["price"] < best[key]:
        best[key] = e["price"]

ships_before = set(e["from"] for e in data["edges"]) | set(e["to"] for e in data["edges"])
ships_after  = set(f for f, _ in best) | set(t for _, t in best)
print(f"Edges  before: {len(data['edges']):>6}  after: {len(best)}")
print(f"Ships  before: {len(ships_before):>6}  after: {len(ships_after)}")

changed = {}
for e in data["edges"]:
    for raw in (e["from"], e["to"]):
        c = normalize(raw)
        if c != raw and raw not in changed:
            changed[raw] = c
print(f"\nSample renames ({len(changed)} unique):")
for raw, clean in sorted(changed.items())[:30]:
    print(f"  {raw!r:60s} -> {clean!r}")

# Save
edges_clean = [
    {"from": f, "to": t, "price": p, "scraped_at": scraped_at}
    for (f, t), p in sorted(best.items())
]
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"scraped_at": scraped_at, "edges": edges_clean}, f, ensure_ascii=False, indent=2)
print(f"\nClean JSON -> {OUT}  ({len(edges_clean)} edges)")

def esc(s): return s.replace("'", "''")
lines = [f"('{esc(f)}', '{esc(t)}', {p}, '{scraped_at}')" for (f, t), p in sorted(best.items())]
sql = (
    "INSERT INTO public.sh_ccus (from_ship, to_ship, price, scraped_at) VALUES\n"
    + ",\n".join(lines)
    + "\nON CONFLICT (from_ship, to_ship) DO UPDATE"
    + " SET price = EXCLUDED.price, scraped_at = EXCLUDED.scraped_at;\n"
)
SQL.write_text(sql, encoding="utf-8")
print(f"Seed SQL   -> {SQL}")
