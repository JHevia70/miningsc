# MiningSC — Claude Code Guide

## Project overview

**MiningSC** (`H:\Projects\SC`) is a community mining intelligence platform for Star Citizen. Three components:

1. **Web app** — Next.js 16 + Supabase, live at https://miningsc.vercel.app
2. **Desktop overlay** — Python tray app that OCRs the in-game mining panel (F9 scan, F10 toggle)
3. **Data pipeline** — Python tools that extract mineral spawn data from game files and push to Supabase

---

## Critical rules

### i18n — always bilingual
**Never hardcode user-visible strings in components.** Every string must go through `next-intl`:
1. Add key to `web/messages/en.json`
2. Add Spanish translation to `web/messages/es.json`
3. Use `t("key")` in the component via `useTranslations` / `getTranslations`

### Temp files
All intermediate/temp files go to `F:\SC_temp\` — never to `C:\` or the repo.

---

## Directory layout

```
H:\Projects\SC/
├── web/                        # Next.js web app
│   ├── src/app/[locale]/       # Pages: home, map, minerals, auth/*, account
│   ├── src/components/         # Navbar, Footer, AuthProvider, PlanetGlobe
│   ├── src/lib/supabase/       # client.ts (browser), server.ts (SSR)
│   ├── src/lib/mineral-aliases.ts
│   ├── src/i18n/               # routing.ts, request.ts
│   ├── messages/               # en.json, es.json
│   └── public/images/planets/  # Planet textures + overlay PNGs
├── supabase/
│   ├── migrations/             # SQL schema + seed data
│   └── functions/              # Deno edge functions (verify-sc-handle, sync-uex)
├── src/                        # Python overlay modules
│   ├── panel_detector.py       # Screenshot -> MineralLine list
│   ├── digit_reader.py         # Template matching + CNN
│   ├── digit_cnn.py            # PyTorch model
│   ├── uploader.py             # Supabase upload
│   ├── config.py               # Config persistence
│   └── config_window.py        # Tkinter settings UI
├── tools/                      # Data pipeline scripts
│   ├── update_spawn_data.py    # StarBreaker -> DCB -> mineral_spawns table
│   ├── gen_mineral_overlays.py # Splat DDS -> zone overlay PNGs
│   ├── gen_clim_overlays.py    # Clim DDS -> polar/equatorial zone PNGs
│   ├── gen_biome_overlays.py   # Splat DDS -> colorized biome PNGs
│   ├── process_ui_starmap.py   # UI starmap DDS -> 1024x512 web PNGs
│   ├── extract_hpp_zones.py    # Mineral -> biome tag from HPP JSON
│   ├── analyze_clims.py        # Per-channel stats for clim PNGs
│   ├── body_map.json           # HPP stem -> planet metadata
│   └── mineral_map.json        # Name substrings -> canonical mineral names
├── data/
│   ├── digit_templates/        # Pre-extracted digit images (0-9, ., %)
│   ├── digit_cnn.pt            # Trained PyTorch model
│   └── fonts/Electrolize-Regular.ttf
├── overlay.py                  # Main overlay window
├── overlay.spec                # PyInstaller build spec
├── requirements.txt
└── INSTALL.md                  # Spanish installation guide for overlay
```

---

## Web app

### Tech stack
- Next.js 16.2.6, React 19, TypeScript, Tailwind CSS 4
- Supabase JS (`@supabase/ssr` for SSR, `@supabase/supabase-js` for browser)
- next-intl (locales: `en`, `es`, default `en`)
- Three.js for 3D planet globes
- Deployed on Vercel

### Deploy
```powershell
cd H:\Projects\SC\web
npx vercel --prod
```

### Routes
| Route | Component | Notes |
|-------|-----------|-------|
| `/` | `app/page.tsx` | Redirects to `/en` |
| `/[locale]` | `app/[locale]/page.tsx` | Homepage (hero, features, stats) |
| `/[locale]/map` | `MapClient.tsx` | Interactive spawn map + 3D globe |
| `/[locale]/minerals` | `MineralsTable.tsx` | Pricing table (raw + refined) |
| `/[locale]/auth/login` | `auth/login/page.tsx` | Email + Google OAuth |
| `/[locale]/auth/register` | `auth/register/page.tsx` | Email + Google signup |
| `/[locale]/auth/callback` | `auth/callback/route.ts` | OAuth callback |
| `/[locale]/account` | `AccountClient.tsx` | SC handle verification |

### Minerals page classification
- No `is_raw`/`is_refined` filter on fetch (those flags are unreliable for FPS/GV minerals)
- Classification logic: suffix `(Raw)`/`(Ore)` + `is_refined` flag
- FPS/GV minerals (Aphorite, Beradom, Dolivine, Feynmaline, Glacosite, Hadanite, Janalite, Ouratite) have no refinery prices — fall back to `commodities.price_sell` for raw column
- Mineral name links to `/map?mineral=<name>`
- Alias table: `web/src/lib/mineral-aliases.ts`

### Planet globe assets (`public/images/planets/`)
- `<stem>.png` — base texture (e.g. `stanton1a.png`, `pyro1.png`)
- `<stem>_biome.png` — colorized biome overlay (Stanton only: 1a/1b/1c/1d/2b/2c/3b)
- `<stem>_zone_<tag>.png` — mineral zone mask (e.g. `stanton1a_zone_acidic.png`)
- `BODY_TEXTURE` map in `MapClient.tsx` maps body name → stem
- `BODY_HAS_BIOME` set lists bodies that have biome overlay
- `BODY_ZONES` map lists zone→mineral mappings per body

---

## Supabase

**Project**: `dtfkyacafqkrbyhgoxjk.supabase.co`

### Key tables
| Table | Access | Notes |
|-------|--------|-------|
| `systems` | Public SELECT | Stanton, Pyro, Nyx |
| `bodies` | Public SELECT | Planets, moons, belts |
| `minerals` | Public SELECT | 23 canonical names |
| `commodity_prices` | Public SELECT | Per-terminal refined prices (UEX) |
| `commodity_raw_prices` | Public SELECT | Per-terminal raw prices (UEX) |
| `mineral_spawns` | Public SELECT | 400+ rows, spawn prob data v4.x |
| `players` | Own row SELECT; anon INSERT | SC handle + verification state |
| `scans` | Public INSERT | One row per F9 scan |
| `scan_minerals` | Public INSERT | One row per mineral per scan |

### RLS policies
- Static reference tables (systems, bodies, minerals, commodities): public SELECT
- `players`: authenticated users SELECT own row; anon INSERT allowed (overlay creates player row)
- `scans`/`scan_minerals`: public INSERT (overlay submits without login)

### Edge functions
- `verify-sc-handle` — POST, auth required. Fetches RSI profile HTML, checks bio for `SCMINE-XXXXXX` code.
- `sync-uex` — POST (internal). Syncs commodities/prices from UEX Corp API.

### RPC
- `generate_sc_verify_code(p_sc_handle)` — Generates `SCMINE-XXXXXX` code, stores in `players` row.

### Triggers
- `on_auth_user_created` — auto-creates `players` row when `auth.users` record is inserted.

---

## Desktop scanner (MiningScanner)

### Architecture
Windows tray app compiled with PyInstaller + Inno Setup installer. Runs as admin (global keyboard hook requires elevated permissions). Entry point is `overlay.py` (name kept for historical reasons).

### Key files
| File | Purpose |
|------|---------|
| `overlay.py` | Main window: tkinter transparent always-on-top, tray icon, F9/F10 hotkeys |
| `src/panel_detector.py` | Screenshot via MSS, color-masks orange panel region, returns `MineralLine` list |
| `src/digit_reader.py` | Template matching against `data/digit_templates/`, CNN fallback |
| `src/digit_cnn.py` | **ONNX Runtime** inference — loads `data/digit_cnn.onnx`, CPU only |
| `src/uploader.py` | Async Supabase upload to `scans` + `scan_minerals` |
| `src/config.py` | Config persistence to `config.json` beside `.exe` |
| `src/config_window.py` | Settings dialog (transparency, font size, alignment, upload toggle) |
| `scanner.spec` | PyInstaller spec — produces `F:\SC_temp\dist\MiningScanner\` |
| `installer.iss` | Inno Setup script — produces `F:\SC_temp\installer\MiningScanner_Setup.exe` |
| `build_installer.py` | Orchestrates full build: PyInstaller → strip GPU DLLs → Inno Setup → ZIP |
| `export_onnx.py` | One-time script: converts `digit_cnn.pt` → `digit_cnn.onnx` (run if model is retrained) |

### Model: ONNX, not PyTorch
The digit CNN (`src/digit_cnn.py`) uses **onnxruntime** (CPU only), NOT torch.

**Why:** torch+CUDA weighs ~800 MB. The CNN classifies 16×16 px glyphs into 12 classes — CPU inference takes <1 ms. Bundling CUDA for this is absurd and produced a 1 GB installer.

**Current sizes:**
| Artifact | Size |
|---|---|
| `data/digit_cnn.onnx` | 611 KB |
| PyInstaller bundle (`dist/MiningScanner/`) | ~133 MB |
| `MiningScanner_Setup.exe` | ~45 MB |
| `web/private/MiningScanner.zip` | ~44.5 MB |

**If the model is retrained** (via `train_digits.py`), re-export to ONNX before building:
```powershell
cd H:\Projects\SC
python export_onnx.py   # reads data/digit_cnn.pt → writes data/digit_cnn.onnx
```

**Do NOT reintroduce torch as a runtime dependency** in `src/digit_cnn.py`. Keep it dev-only (for training/export).

### GPU DLL stripping (critical)
`onnxruntime` ships with `onnxruntime_providers_cuda.dll` (307 MB) even though we only use `CPUExecutionProvider`. PyInstaller copies it regardless of `excludes`. The build script removes it explicitly after PyInstaller runs:

```
dist/MiningScanner/_internal/onnxruntime/capi/
  onnxruntime_providers_cuda.dll      ← DELETED by build_installer.py (307 MB)
  onnxruntime_providers_tensorrt.dll  ← DELETED by build_installer.py
  onnxruntime.dll                     ← kept (15 MB, needed)
  onnxruntime_pybind11_state.pyd      ← kept (18 MB, needed)
```

If onnxruntime is upgraded, check whether new GPU provider DLLs appear and add them to `GPU_DLLS` in `build_installer.py`.

### Build (full, recommended)
```powershell
cd H:\Projects\SC
python build_installer.py
```
Produces:
- `F:\SC_temp\dist\MiningScanner\` — PyInstaller bundle (133 MB)
- `F:\SC_temp\installer\MiningScanner_Setup.exe` — Inno Setup installer (45 MB)
- `web\private\MiningScanner.zip` — ready for web download (44.5 MB)

### Build (manual steps)
```powershell
# Step 1 — PyInstaller
python -m PyInstaller scanner.spec --distpath F:/SC_temp/dist --workpath F:/SC_temp/build --noconfirm

# Step 2 — strip GPU DLLs manually
Remove-Item "F:\SC_temp\dist\MiningScanner\_internal\onnxruntime\capi\onnxruntime_providers_cuda.dll"
Remove-Item "F:\SC_temp\dist\MiningScanner\_internal\onnxruntime\capi\onnxruntime_providers_tensorrt.dll"

# Step 3 — Inno Setup (requires Inno Setup 6 installed)
& "C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss

# Step 4 — zip for web
Compress-Archive F:\SC_temp\installer\MiningScanner_Setup.exe web\private\MiningScanner.zip -Force
```

### Inno Setup
- Installed at: `C:\Program Files (x86)\Inno Setup 6\iscc.exe`
- Downloaded from: `https://jrsoftware.org/download.php/is.exe`
- Script: `installer.iss`
- Features: UAC admin manifest, Start Menu shortcut, optional Desktop shortcut, optional startup entry, uninstaller, kills running process before upgrade, bilingual (EN + ES)

### Web download gate
The ZIP is served only to verified users via `/api/download/scanner` (Next.js route at `web/src/app/api/download/scanner/route.ts`). It reads from `web/private/MiningScanner.zip` which is never publicly accessible. Direct URL access returns 401/403.

### Runtime notes
- Font (`Electrolize-Regular.ttf`) registered at startup via `AddFontResourceExW`
- `config.json` written beside `.exe`, not inside the PyInstaller bundle (`sys.executable.parent`)
- `uac_admin=True` in spec — requires admin at launch (needed for global F9/F10 hooks)
- `sys._MEIPASS` used in `digit_cnn.py`, `digit_reader.py`, `config.py` for correct paths inside bundle

---

## Data pipeline

### Game files
- **Data.p4k**: `G:\Roberts Space Industries\StarCitizen\StarCitizen\LIVE\Data.p4k` (143 GB)
- **StarBreaker** (primary extractor): `F:\SC_temp\starbreaker\starbreaker.exe`
  - `unp4k` does NOT work with the current p4k format — use StarBreaker only.

### StarBreaker commands
```bash
# List files:
starbreaker p4k list --p4k <p4k> --filter "<glob>"

# Extract files (DDS -> PNG conversion):
starbreaker p4k extract --p4k <p4k> --output <outdir> --filter "<glob>" --convert dds-png

# Extract DCB to JSON:
starbreaker dcb extract --p4k <p4k> --output <outdir> --format json
```

### Extracted data locations (all on F:)
| Data | Path |
|------|------|
| DCB records | `F:\SC_temp\dcb_unfiltered\libs\foundry\records\` |
| Splat maps (biome index DDS) | `F:\SC_temp\splats\Data\Textures\planets\global\stanton\<planet>\` |
| Clim maps | `F:\SC_temp\clims\Data\Textures\planets\global\{system}\{body}\` |
| UI starmap textures (Pyro/Nyx) | `F:\SC_temp\ui_starmap\Data\UI\starmap\textures\` |
| Stanton planet textures | `F:\SC_temp\planet_textures\Data\Textures\planets\global\stanton\` |
| Planet PNGs (web-ready) | `F:\SC_temp\planet_png\` |
| Biome overlay PNGs | `F:\SC_temp\biome_overlays\` |

### Pipeline tools
| Script | Input | Output |
|--------|-------|--------|
| `update_spawn_data.py` | DCB HPP JSON | `mineral_spawns` Supabase table |
| `gen_mineral_overlays.py` | Splat DDS | Zone mask PNGs (white alpha) — Hurston, Yela, Lyria |
| `gen_clim_overlays.py` | Clim DDS | Polar/equatorial zone PNGs — all other bodies |
| `gen_biome_overlays.py` | Splat DDS | Colorized biome overlay PNGs |
| `process_ui_starmap.py` | UI starmap DDS | 1024×512 RGB PNGs for web |
| `extract_hpp_zones.py` | HPP JSON | Mineral → biome tag mapping |
| `analyze_clims.py` | Clim PNGs | Per-channel stats |

---

## Biome zone overlays

### Splat-based (Hurston, Yela, Lyria)
Splat DDS: R8_UINT 512×512 — pixel ÷ 16 = biome index (0..15)

| Body | Zone tag | Splat indices | Coverage |
|------|----------|---------------|---------|
| Hurston | acidic | 13, 15 | ~29% |
| Yela | ice | 3, 5, 6, 8 | ~90% |
| Lyria | crystaline | 3, 15 | ~51% |

### Clim-based (all other bodies)
Clim DDS channel G = temperature/latitude (0 = cold/pole, ~200 = equator)

| Body | Zone | Type | Threshold |
|------|------|------|-----------|
| Aberdeen, Arial, Ita, Daymar | desert | equatorial | G > 100 |
| MicroTech | ice | polar | G < 40 |
| Calliope | ice | polar | G < 100 |
| Pyro I, Monox, Pyro III, Bloom, Pyro V | ice | polar | G < 100 |
| Pyro VI | ice | polar (inverted) | G > 120 |

### Known limitations
- Pyro/Nyx: no biome overlays (Pyro splats only exist for pyro5a, but its HPP has `areas=[]`)
- MicroTech, Calliope, Clio (stanton4a/4b/4c): no splat files in p4k
- Aberdeen, Arial, Ita, Daymar: HPPs have `areas=[]` or all `modifiers=0` → no zone minerals
- Biome tag → splat index mapping was inferred from sparsity (not readable directly from shaders)

---

## Known gaps / TODO

- Home page stats ("scans", "players") are hardcoded placeholders — need live Supabase aggregation
- Overlay download link on homepage goes to `#` (no release package yet)
- No scan history UI or per-user scan filtering
- No way to unlink/change a verified SC handle
- No Discord integration (referenced in footer)
- UEX sync (`sync-uex` edge function) has no pg_cron schedule — must be triggered manually
- RSI profile scraper in `verify-sc-handle` may need updates if RSI changes their HTML structure
