import json
with open("F:/SC_temp/sh_ccus_clean.json", encoding="utf-8") as f:
    d = json.load(f)
frm = [e for e in d["edges"] if e["from"] == "Hull B"]
to  = [e for e in d["edges"] if e["to"]   == "Hull B"]
print(f"Edges FROM 'Hull B': {len(frm)}")
for e in frm[:5]:
    print(f"  {e['from']} -> {e['to']}: ${e['price']}")
print(f"Edges TO 'Hull B': {len(to)}")
for e in to[:5]:
    print(f"  {e['from']} -> {e['to']}: ${e['price']}")

# También buscar variantes
variants = set(e["from"] for e in d["edges"] if "hull" in e["from"].lower())
variants |= set(e["to"] for e in d["edges"] if "hull" in e["to"].lower())
print(f"\nAll Hull variants in edges: {sorted(variants)}")
