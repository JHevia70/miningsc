#!/usr/bin/env python3
"""
star-hangar.com CCU scraper
============================
Scrapes all Cross-Chassis Upgrade listings from star-hangar.com and saves
the minimum price per (from_ship, to_ship) pair to a JSON cache file.

Usage
-----
  python sh_scraper.py                          # scrape all ships, save to F:/SC_temp/sh_ccus.json
  python sh_scraper.py --ship galaxy            # scrape only upgrades targeting "galaxy"
  python sh_scraper.py --out my_cache.json      # custom output path
  python sh_scraper.py --delay 2.5             # seconds between requests (default 2.0)
  python sh_scraper.py --limit 10              # max ships to scrape (for testing)

Output format (sh_ccus.json)
-----------------------------
{
  "scraped_at": "2026-06-19T12:00:00",
  "edges": [
    {"from": "Hull B", "to": "Galaxy", "price": 160.64, "url": "..."},
    ...
  ]
}
"""

import re
import json
import time
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Ship catalogue — (display_name, manufacturer_slug, ship_slug)
# Each entry is a PAGE on star-hangar.com that lists CCUs for that ship family.
# Use the family/group URL (e.g. /vanguard.html) not individual variant URLs.
# Verified against the live site navigation, June 2026.
# ---------------------------------------------------------------------------
SHIPS = [
    # ── Aegis Dynamics ──────────────────────────────────────────────────────
    ("Avenger",                "aegis-dynamics", "avenger"),
    ("Eclipse",                "aegis-dynamics", "eclipse"),
    ("Gladius",                "aegis-dynamics", "gladius"),
    ("Hammerhead",             "aegis-dynamics", "hammerhead"),
    ("Idris",                  "aegis-dynamics", "idris-ships"),
    ("Nautilus",               "aegis-dynamics", "nautilus"),
    ("Reclaimer",              "aegis-dynamics", "reclaimer"),
    ("Redeemer",               "aegis-dynamics", "redeemer"),
    ("Retaliator",             "aegis-dynamics", "retaliator"),
    ("Sabre",                  "aegis-dynamics", "sabre"),
    ("Tiburon",                "aegis-dynamics", "tiburon"),
    ("Vanguard",               "aegis-dynamics", "vanguard"),
    ("Vulcan",                 "aegis-dynamics", "vulcan"),

    # ── Anvil Aerospace ─────────────────────────────────────────────────────
    ("Arrow",                  "anvil-aerospace", "arrow"),
    ("Asgard",                 "anvil-aerospace", "asgard"),
    ("Carrack",                "anvil-aerospace", "carrack"),
    ("Crucible",               "anvil-aerospace", "crucible"),
    ("Gladiator",              "anvil-aerospace", "gladiator"),
    ("Hawk",                   "anvil-aerospace", "hawk"),
    ("Hornet",                 "anvil-aerospace", "hornet"),
    ("Hurricane",              "anvil-aerospace", "hurricane"),
    ("Legionnaire",            "anvil-aerospace", "legionnaire"),
    ("Liberator",              "anvil-aerospace", "liberator"),
    ("Lightning F8C",          "anvil-aerospace", "f8c-lighting"),
    ("Paladin",                "anvil-aerospace", "paladin"),
    ("Pisces",                 "anvil-aerospace", "pisces"),
    ("Terrapin",               "anvil-aerospace", "terrapin"),
    ("Valkyrie",               "anvil-aerospace", "valkyrie"),

    # ── Aopoa ───────────────────────────────────────────────────────────────
    ("Aopoa Khartu-Al",        "aopoa", "khartu-al"),
    ("Aopoa Nox",              "aopoa", "nox"),
    ("Aopoa San'tok.yai",      "aopoa", "santok-yai"),

    # ── Argo Astronautics ───────────────────────────────────────────────────
    ("MOLE",                   "argo-astronautics", "mole"),
    ("MPUV",                   "argo-astronautics", "mpuv"),
    ("MOTH",                   "argo-astronautics", "moth"),
    ("RAFT",                   "argo-astronautics", "raft"),
    ("SRV",                    "argo-astronautics", "srv"),

    # ── Banu ────────────────────────────────────────────────────────────────
    ("Banu Defender",          "banu", "defender"),
    ("Banu Merchantman",       "banu", "merchantman"),

    # ── Consolidated Outland ────────────────────────────────────────────────
    ("HCV",                    "consolidated-outland", "hcv"),
    ("Mustang",                "consolidated-outland", "mustang"),
    ("Nomad",                  "consolidated-outland", "nomad"),

    # ── Crusader Industries ─────────────────────────────────────────────────
    ("Ares Ion",               "crusader-industries", "ares/ion"),
    ("Ares Inferno",           "crusader-industries", "ares/inferno"),
    ("Genesis Starliner",      "crusader-industries", "genesis-starliner"),
    ("Hercules A2",            "crusader-industries", "hercules/a2"),
    ("Hercules C2",            "crusader-industries", "hercules/c2"),
    ("Hercules M2",            "crusader-industries", "hercules/m2"),
    ("Intrepid",               "crusader-industries", "intrepid"),
    ("Mercury Star Runner",    "crusader-industries", "mercury"),
    ("Spirit A1",              "crusader-industries", "spirit/a1"),
    ("Spirit C1",              "crusader-industries", "spirit/c1"),
    ("Spirit E1",              "crusader-industries", "spirit/e1"),

    # ── Drake Interplanetary ────────────────────────────────────────────────
    ("Buccaneer",              "drake-interplanetary", "buccaneer"),
    ("Caterpillar",            "drake-interplanetary", "caterpillar"),
    ("Clipper",                "drake-interplanetary", "clipper"),
    ("Corsair",                "drake-interplanetary", "corsair"),
    ("Cutlass",                "drake-interplanetary", "cutlass"),
    ("Cutter",                 "drake-interplanetary", "cutter"),
    ("Golem",                  "drake-interplanetary", "golem"),
    ("Herald",                 "drake-interplanetary", "herald"),
    ("Ironclad",               "drake-interplanetary", "ironclad"),
    ("Pitbull",                "drake-interplanetary", "pitbull"),
    ("Vulture",                "drake-interplanetary", "vulture"),

    # ── Esperia ─────────────────────────────────────────────────────────────
    ("Blade",                  "esperia", "blade"),
    ("Glaive",                 "esperia", "glaive"),
    ("Prowler",                "esperia", "prowler"),
    ("Talon",                  "esperia", "talon"),

    # ── Gatac ───────────────────────────────────────────────────────────────
    ("Railen",                 "gatac", "railen"),
    ("Syulen",                 "gatac", "syulen"),

    # ── Kruger ──────────────────────────────────────────────────────────────
    ("P-52 Merlin",            "kruger-intergalactic", "p-52-merlin"),
    ("P-72 Archimedes",        "kruger-intergalactic", "p-72-archimedes"),

    # ── Mirai ───────────────────────────────────────────────────────────────
    ("Fury",                   "mirai", "fury"),
    ("Guardian",               "mirai", "guardian"),

    # ── MISC ────────────────────────────────────────────────────────────────
    ("Endeavor",               "musashi-industrial-starflight-concern", "endeavor"),
    ("Expanse",                "musashi-industrial-starflight-concern", "expanse"),
    ("Fortune",                "musashi-industrial-starflight-concern", "misc-fortune"),
    ("Freelancer",             "musashi-industrial-starflight-concern", "freelancer"),
    ("Hull Series",            "musashi-industrial-starflight-concern", "hull"),
    ("Odyssey",                "musashi-industrial-starflight-concern", "odyssey"),
    ("Prospector",             "musashi-industrial-starflight-concern", "prospector"),
    ("Razor",                  "musashi-industrial-starflight-concern", "razor"),
    ("Reliant",                "musashi-industrial-starflight-concern", "reliant"),
    ("Starfarer",              "musashi-industrial-starflight-concern", "starfarer"),
    ("Starlancer",             "musashi-industrial-starflight-concern", "starlancer"),
    ("Starlite",               "musashi-industrial-starflight-concern", "starlite"),

    # ── Origin Jumpworks ────────────────────────────────────────────────────
    ("85X",                    "origin-jumpworks", "85x"),
    ("100 Series",             "origin-jumpworks", "100-series"),
    ("300i Series",            "origin-jumpworks", "300i-series"),
    ("400i",                   "origin-jumpworks", "400i"),
    ("600 Series",             "origin-jumpworks", "600-series"),
    ("890 Jump",               "origin-jumpworks", "890-jump"),
    ("M50",                    "origin-jumpworks", "m50"),
    ("M80",                    "origin-jumpworks", "m80"),

    # ── Roberts Space Industries ────────────────────────────────────────────
    ("Apollo",                 "roberts-space-industries", "apollo"),
    ("Arrastra",               "roberts-space-industries", "arrastra"),
    ("Aurora",                 "roberts-space-industries", "aurora"),
    ("Constellation",          "roberts-space-industries", "constellation"),
    ("Galaxy",                 "roberts-space-industries", "galaxy"),
    ("Hermes",                 "roberts-space-industries", "hermes"),
    ("Mantis",                 "roberts-space-industries", "mantis"),
    ("Meteor",                 "roberts-space-industries", "meteor"),
    ("Orion",                  "roberts-space-industries", "orion"),
    ("Perseus",                "roberts-space-industries", "perseus"),
    ("Polaris",                "roberts-space-industries", "polaris"),
    ("Salvation",              "roberts-space-industries", "salvation"),
    ("Scorpius",               "roberts-space-industries", "scorpius"),
    ("Zeus MK II",             "roberts-space-industries", "zeus"),

    # ── Vanduul ─────────────────────────────────────────────────────────────
    ("Scythe",                 "vanduul", "scythe"),
    ("Glaive (Vanduul)",       "vanduul", "glaive"),
]

BASE_URL = "https://star-hangar.com"
DEFAULT_OUT = Path("F:/SC_temp/sh_ccus.json")
PAGE_SIZE = 50

log = logging.getLogger("sh_scraper")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    # Warm-up request to get session cookies
    try:
        s.get(BASE_URL, timeout=30)
    except Exception:
        pass
    return s


def fetch_page(session: requests.Session, url: str, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=45)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            log.warning(f"  attempt {attempt+1} failed for {url}: {e}")
            time.sleep(3 * (attempt + 1))
    return None


def parse_price(text: str) -> float | None:
    m = re.search(r"\$?([\d,]+\.?\d*)", text.replace(",", ""))
    return float(m.group(1)) if m else None


# Manufacturer prefixes that appear in some listing titles
_MFR_PREFIXES = re.compile(
    r"^(?:RSI|MISC|Anvil|Aegis|Crusader|Argo|Aopoa|Origin|Drake|Mirai|Banu|Esperia|Gatac|"
    r"Kruger|Consolidated Outland|Tumbril|Roberts Space Industries|"
    r"Musashi Industrial|MSIC)\s+",
    re.IGNORECASE,
)

# Trailing noise patterns to strip from ship names (applied in order)
_NOISE_PATTERNS = [
    r"\s*-\s*Upgrade\b.*$",               # " - Upgrade - Star Citizen"
    r"\s*-\s*Star Citizen.*$",             # " - Star Citizen ..."
    r"\s+CCU\b.*$",                        # " CCU" / " WBCCU"
    r"\s*Standard Edition$",              # " Standard Edition"
    r"\s*Best In Show Edition \d+",       # " Best In Show Edition 2949"
    r"\s*Pirate Edition$",                # " Pirate Edition"
    r"\s*\(Warbond[^)]*\)",              # "(Warbond...)"
    r"\s+Warbond\b",
    r"\s*-\s*LTI\b",
    r"\s*\bLTI\b",
    r"\s*\d+\s*(?:yr|year)s?\s*ins\.?",  # "10yr ins."
    r"\s*OC\b",
    r"\s*\+\s*Extras",
    r"\s*CCU'ed",
    r"\s+-\s*$",                           # trailing " -"
]
_NOISE_RE = [re.compile(p, re.IGNORECASE) for p in _NOISE_PATTERNS]

# Manual canonical aliases: maps messy scraped names → clean canonical name
# Add more as discovered via --verbose runs
SHIP_ALIASES: dict[str, str] = {
    # Galaxy variants
    "RSI Galaxy":                  "Galaxy",
    "Galaxy Standard Edition":     "Galaxy",
    "RSI Galaxy -":                "Galaxy",
    "Galaxy -":                    "Galaxy",
    "RSI Galaxy CCU":              "Galaxy",
    "RSI Galaxy - Upgrade - Star Citizen": "Galaxy",
    # Hull series
    "MISC Hull B":                 "Hull B",
    "MISC Hull C":                 "Hull C",
    "MISC Hull C -":               "Hull C",
    "MISC Hull D":                 "Hull D",
    "MISC Hull E":                 "Hull E",
    "MISC Hull E -":               "Hull E",
    "MISC Odyssey -":              "Odyssey",
    "MISC Odyssey":                "Odyssey",
    # Aegis
    "Aegis Hammerhead -":          "Hammerhead",
    "Aegis Nautilus -":            "Nautilus",
    "Aegis Reclaimer -":           "Reclaimer",
    "Reclaimer":                   "Reclaimer",
    # Anvil
    "Anvil Carrack -":             "Carrack",
    "Anvil Liberator -":           "Liberator",
    # RSI
    "RSI Arrastra -":              "Arrastra",
    "RSI Orion -":                 "Orion",
    "RSI Perseus -":               "Perseus",
    "Perseus":                     "Perseus",
    "RSI Polaris -":               "Polaris",
    # Banu
    "Banu Merchantman -":          "Merchantman",
    # Crusader
    "Crusader A2 Hercules Starlifter -": "Hercules A2",
    "Crusader C2 Hercules -":      "Hercules C2",
    "C2 Hercules":                 "Hercules C2",
    "Crusader M2 Hercules -":      "Hercules M2",
    "Crusader Genesis Starliner -": "Genesis",
    "Genesis":                     "Genesis",
    # Esperia
    "Esperia Prowler -":           "Prowler",
    # Origin
    "Origin 600i Explorer -":      "600i Explorer",
    "Origin 600i Touring -":       "600i Touring",
    # Misc
    "RAFT WBCCU":                  "RAFT",
    "Argo Mole":                   "MOLE",
    "Argo MOLE":                   "MOLE",
    "Constellation Phoenix":       "Constellation Phoenix",
}


def normalize_ship_name(raw: str) -> str:
    """Return canonical ship name from a raw scraped string."""
    name = raw.strip()

    # 1. Check alias table first (exact match)
    if name in SHIP_ALIASES:
        return SHIP_ALIASES[name]

    # 2. Strip "Upgrade - " prefix (e.g. "Upgrade - Crucible" -> "Crucible")
    name = re.sub(r"^Upgrade\s*-\s*", "", name, flags=re.IGNORECASE).strip()

    # 3. Strip noise suffixes
    for pat in _NOISE_RE:
        name = pat.sub("", name).strip()

    # 4. Strip manufacturer prefix
    name = _MFR_PREFIXES.sub("", name).strip()

    # 4. Check alias table again after stripping
    if name in SHIP_ALIASES:
        return SHIP_ALIASES[name]

    return name


# CCU title patterns:
#   "Hull B to Galaxy"
#   "Hull B to Galaxy Upgrade"
#   "Scorpius to Vanguard Warden (Warbond)"
#   "MISC Hull B to RSI Galaxy - Upgrade - Star Citizen"
CCU_RE = re.compile(
    r"^(.+?)\s+to\s+(.+?)(?:\s+(?:Upgrade|CCU|upgrade))?(?:\s*[\(\[].*)?$",
    re.IGNORECASE,
)


def parse_ccu_title(title: str) -> tuple[str, str] | None:
    """Return (from_ship, to_ship) or None if not a CCU listing."""
    title = title.strip()
    m = CCU_RE.match(title)
    if not m:
        return None
    from_ship = normalize_ship_name(m.group(1))
    to_ship   = normalize_ship_name(m.group(2))
    if len(from_ship) < 2 or len(to_ship) < 2:
        return None
    return from_ship, to_ship


def scrape_ship_page(
    session: requests.Session,
    display_name: str,
    manufacturer: str,
    slug: str,
    delay: float,
) -> list[dict]:
    """Scrape all CCU listings on a ship's page. Returns list of edge dicts."""
    page_url_base = f"{BASE_URL}/star-citizen/spaceships/{manufacturer}/{slug}.html"
    edges: list[dict] = []
    # Track best price per (from, to) pair seen on this page set
    best: dict[tuple[str, str], float] = {}

    page = 1
    while True:
        url = f"{page_url_base}?p={page}&product_list_limit={PAGE_SIZE}"
        log.info(f"  [{display_name}] page {page} — {url}")
        soup = fetch_page(session, url)

        if soup is None:
            log.warning(f"  [{display_name}] page {page} → 404, stopping")
            break

        # Product items: star-hangar uses Magento-style markup
        # Try multiple selectors in order of specificity
        items = (
            soup.select(".product-item-info")
            or soup.select(".product-item")
            or soup.select("li.item.product")
            or soup.select(".products-grid .item")
        )

        if not items:
            log.debug(f"  [{display_name}] page {page} — no items found, stopping")
            break

        found_on_page = 0
        for item in items:
            # Title
            title_el = (
                item.select_one(".product-item-link")
                or item.select_one("a.product-item-link")
                or item.select_one(".product-item-name a")
                or item.select_one("strong.product-item-name a")
                or item.select_one("a[href]")
            )
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            pair = parse_ccu_title(title)
            if not pair:
                continue

            # Price
            price_el = (
                item.select_one(".price-wrapper .price")
                or item.select_one(".price")
                or item.select_one("[data-price-amount]")
            )
            if price_el:
                price_attr = price_el.get("data-price-amount")
                price = float(price_attr) if price_attr else parse_price(price_el.get_text())
            else:
                price = None

            if price is None or price <= 0:
                continue

            from_ship, to_ship = pair
            key = (from_ship, to_ship)
            if key not in best or price < best[key]:
                best[key] = price
                log.debug(f"    CCU: {from_ship!r} → {to_ship!r} @ ${price:.2f}")
            found_on_page += 1

        log.info(f"  [{display_name}] page {page} — {found_on_page} CCUs parsed")

        # Check if there's a next page
        next_btn = soup.select_one("a.action.next") or soup.select_one(".pages-item-next a")
        if not next_btn:
            break

        page += 1
        time.sleep(delay)

    # Convert best map to edge list
    page_url = page_url_base
    for (frm, to), price in best.items():
        edges.append({"from": frm, "to": to, "price": price, "via_page": display_name})

    return edges


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Scrape CCU prices from star-hangar.com")
    ap.add_argument("--out",   default=str(DEFAULT_OUT), help="Output JSON path")
    ap.add_argument("--ship",  default=None, help="Scrape only this ship slug (e.g. galaxy)")
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds between page requests")
    ap.add_argument("--limit", type=int, default=None, help="Max ships to scrape")
    ap.add_argument("--merge", action="store_true", help="Merge into existing cache instead of overwriting")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    ships = SHIPS
    if args.ship:
        ships = [s for s in SHIPS if args.ship.lower() in s[2].lower() or args.ship.lower() in s[0].lower()]
        if not ships:
            log.error(f"No ship matching '{args.ship}' found in catalogue")
            return
    if args.limit:
        ships = ships[:args.limit]

    log.info(f"Scraping {len(ships)} ship pages …")
    session = make_session()
    all_edges: list[dict] = []

    for i, (display, manufacturer, slug) in enumerate(ships, 1):
        log.info(f"[{i}/{len(ships)}] {display}")
        try:
            edges = scrape_ship_page(session, display, manufacturer, slug, args.delay)
            all_edges.extend(edges)
            log.info(f"  → {len(edges)} unique CCU edges")
        except Exception as e:
            log.error(f"  ERROR scraping {display}: {e}")
        time.sleep(args.delay)

    # Deduplicate: keep minimum price per (from, to) pair across all pages scraped
    best_global: dict[tuple[str, str], dict] = {}

    # Load existing cache if merging
    out_path = Path(args.out)
    if args.merge and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)
        for e in existing.get("edges", []):
            key = (e["from"], e["to"])
            if key not in best_global or e["price"] < best_global[key]["price"]:
                best_global[key] = e
        log.info(f"Loaded {len(best_global)} existing edges from cache")

    for e in all_edges:
        key = (e["from"], e["to"])
        if key not in best_global or e["price"] < best_global[key]["price"]:
            best_global[key] = e

    final_edges = sorted(best_global.values(), key=lambda x: (x["from"], x["to"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "ship_count": len(ships),
        "edge_count": len(final_edges),
        "edges": final_edges,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info(f"\nDone. {len(final_edges)} CCU edges saved to {out_path}")


if __name__ == "__main__":
    main()
