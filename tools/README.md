# MiningSC — Spawn Data Pipeline

Extracts mineral spawn probability data from Star Citizen's `Data.p4k` and
uploads it to the MiningSC Supabase database.

---

## Quick start — new SC patch

```
cd H:\Projects\SC\tools

python update_spawn_data.py \
  --p4k "G:\Roberts Space Industries\StarCitizen\StarCitizen\LIVE\Data.p4k" \
  --version 4.2
```

That's it. The script:
1. Calls **StarBreaker** to extract `Game2.dcb` records to `F:\SC_temp\dcb_extracted`
2. Parses all `HarvestableProviderPreset` files
3. Deletes old rows for that version from `mineral_spawns`
4. Inserts fresh rows

---

## Re-parse without re-extracting (fastest)

```
python update_spawn_data.py --dcb-dir F:\SC_temp\dcb_unfiltered --version 4.2
```

## Preview changes first

```
python update_spawn_data.py --dcb-dir F:\SC_temp\dcb_unfiltered --version 4.2 --diff-only
```

Shows added / removed / changed entries vs the current DB. No writes.

## Generate JSON only (no Supabase)

```
python update_spawn_data.py --dcb-dir F:\SC_temp\dcb_unfiltered --version 4.2 --dry-run
```

Writes `tools/mining_spawn_data_4_2.json`.

---

## Dependencies

```
pip install supabase
```

StarBreaker is not a Python package — download it from
<https://github.com/alistairfink/starbreaker/releases> and place the exe at
`F:\SC_temp\starbreaker\starbreaker.exe` (or set `STARBREAKER_EXE` env var).

---

## Configuration files

| File | Purpose |
|------|---------|
| `body_map.json` | Maps HPP file names → planet/moon metadata. **Edit this** when CIG adds new bodies. |
| `mineral_map.json` | Maps name substrings → canonical mineral names. **Edit this** when CIG adds new minerals. |

### Adding a new planet (e.g. when Nyx gets moons)

1. Open `body_map.json`
2. Add an entry:
   ```json
   "hpp_nyx_asterope": {"name": "Asterope", "type": "moon", "system": "Nyx", "parent": "Nyx III"}
   ```
3. Re-run the pipeline with `--version <new_version>`

### Adding a new mineral

1. Open `mineral_map.json`
2. Add an entry (more specific substrings first):
   ```json
   "newestmineral": "NewestMineral"
   ```
3. Re-run the pipeline

---

## Environment variables

Set these in `.env` (project root) or `web/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...   # service_role key, NOT the anon key
STARBREAKER_EXE=F:\SC_temp\starbreaker\starbreaker.exe   # optional override
```

---

## How the data flows

```
Data.p4k
  └─ Game2.dcb  (StarBreaker extract)
       └─ libs/foundry/records/harvestable/providerpresets/system/
            ├─ stanton/hpp_stanton1a.json   ← Hurston
            ├─ stanton/hpp_stanton2b.json   ← Daymar
            └─ ...
                 └─ parse_all()
                       └─ mineral_spawns table (Supabase)
                             └─ /map page (MiningSC web)
```

Each `hpp_*.json` lists **harvestable groups** (ship-asteroid, fps, ground-vehicle) each
containing **harvestables** with a `relativeProbability`. The script normalises those
within each group to percentages and stores them as `spawn_prob_pct`.
