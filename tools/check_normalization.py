import json, sys
sys.stdout.reconfigure(encoding="utf-8")
with open("F:/SC_temp/sh_ccus_clean.json", encoding="utf-8") as f:
    d = json.load(f)
ships = sorted(set(e["from"] for e in d["edges"]) | set(e["to"] for e in d["edges"]))

# Names that still have upgrade/insurance noise (should only be BIS)
dirty = [s for s in ships if any(x.lower() in s.lower() for x in
    ["Upgrade", "Insurance", "+urance", "ins.", " INS", "LTI", "Warbond"])]
print(f"Remaining upgrade/insurance names ({len(dirty)}):")
for s in dirty:
    print(f"  {s}")

print()
bis = [s for s in ships if "BIS" in s or "best in show" in s.lower()]
print(f"BIS editions ({len(bis)}):")
for s in bis: print(f"  {s}")

print()
subs = [s for s in ships if "subscriber" in s.lower()]
print(f"Subscribers ({len(subs)}):")
for s in subs: print(f"  {s}")

print(f"\nTotal ships: {len(ships)}")
