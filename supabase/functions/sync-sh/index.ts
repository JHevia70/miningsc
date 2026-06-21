/**
 * sync-sh: Scrapes Star Hangar CCU listings and upserts them into sh_ccus.
 *
 * Protected — only callable with the SYNC_SECRET header or service role key.
 * Triggered from the MiningSC web admin panel (POST /api/ccus/sync).
 *
 * Returns: { ok, inserted, skipped, errors, scraped_at }
 */
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL  = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY   = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const SYNC_SECRET   = Deno.env.get("SYNC_SECRET") ?? "";

const BASE_URL   = "https://star-hangar.com";
const PAGE_SIZE  = 50;
const DELAY_MS   = 2000;

// ---------------------------------------------------------------------------
// Ship catalogue — (display_name, manufacturer_slug, ship_slug)
// ---------------------------------------------------------------------------
const SHIPS: [string, string, string][] = [
  // Aegis Dynamics
  ["Avenger",             "aegis-dynamics", "avenger"],
  ["Eclipse",             "aegis-dynamics", "eclipse"],
  ["Gladius",             "aegis-dynamics", "gladius"],
  ["Hammerhead",          "aegis-dynamics", "hammerhead"],
  ["Idris",               "aegis-dynamics", "idris-ships"],
  ["Nautilus",            "aegis-dynamics", "nautilus"],
  ["Reclaimer",           "aegis-dynamics", "reclaimer"],
  ["Redeemer",            "aegis-dynamics", "redeemer"],
  ["Retaliator",          "aegis-dynamics", "retaliator"],
  ["Sabre",               "aegis-dynamics", "sabre"],
  ["Tiburon",             "aegis-dynamics", "tiburon"],
  ["Vanguard",            "aegis-dynamics", "vanguard"],
  ["Vulcan",              "aegis-dynamics", "vulcan"],
  // Anvil Aerospace
  ["Arrow",               "anvil-aerospace", "arrow"],
  ["Asgard",              "anvil-aerospace", "asgard"],
  ["Carrack",             "anvil-aerospace", "carrack"],
  ["Crucible",            "anvil-aerospace", "crucible"],
  ["Gladiator",           "anvil-aerospace", "gladiator"],
  ["Hawk",                "anvil-aerospace", "hawk"],
  ["Hornet",              "anvil-aerospace", "hornet"],
  ["Hurricane",           "anvil-aerospace", "hurricane"],
  ["Legionnaire",         "anvil-aerospace", "legionnaire"],
  ["Liberator",           "anvil-aerospace", "liberator"],
  ["Lightning F8C",       "anvil-aerospace", "f8c-lighting"],
  ["Paladin",             "anvil-aerospace", "paladin"],
  ["Pisces",              "anvil-aerospace", "pisces"],
  ["Terrapin",            "anvil-aerospace", "terrapin"],
  ["Valkyrie",            "anvil-aerospace", "valkyrie"],
  // Aopoa
  ["Aopoa Khartu-Al",     "aopoa", "khartu-al"],
  ["Aopoa Nox",           "aopoa", "nox"],
  ["Aopoa San'tok.yai",   "aopoa", "santok-yai"],
  // Argo Astronautics
  ["MOLE",                "argo-astronautics", "mole"],
  ["MPUV",                "argo-astronautics", "mpuv"],
  ["MOTH",                "argo-astronautics", "moth"],
  ["RAFT",                "argo-astronautics", "raft"],
  ["SRV",                 "argo-astronautics", "srv"],
  // Banu
  ["Banu Defender",       "banu", "defender"],
  ["Banu Merchantman",    "banu", "merchantman"],
  // Consolidated Outland
  ["HCV",                 "consolidated-outland", "hcv"],
  ["Mustang",             "consolidated-outland", "mustang"],
  ["Nomad",               "consolidated-outland", "nomad"],
  // Crusader Industries
  ["Ares Ion",            "crusader-industries", "ares/ion"],
  ["Ares Inferno",        "crusader-industries", "ares/inferno"],
  ["Genesis Starliner",   "crusader-industries", "genesis-starliner"],
  ["Hercules A2",         "crusader-industries", "hercules/a2"],
  ["Hercules C2",         "crusader-industries", "hercules/c2"],
  ["Hercules M2",         "crusader-industries", "hercules/m2"],
  ["Intrepid",            "crusader-industries", "intrepid"],
  ["Mercury Star Runner", "crusader-industries", "mercury"],
  ["Spirit A1",           "crusader-industries", "spirit/a1"],
  ["Spirit C1",           "crusader-industries", "spirit/c1"],
  ["Spirit E1",           "crusader-industries", "spirit/e1"],
  // Drake Interplanetary
  ["Buccaneer",           "drake-interplanetary", "buccaneer"],
  ["Caterpillar",         "drake-interplanetary", "caterpillar"],
  ["Clipper",             "drake-interplanetary", "clipper"],
  ["Corsair",             "drake-interplanetary", "corsair"],
  ["Cutlass",             "drake-interplanetary", "cutlass"],
  ["Cutter",              "drake-interplanetary", "cutter"],
  ["Golem",               "drake-interplanetary", "golem"],
  ["Herald",              "drake-interplanetary", "herald"],
  ["Ironclad",            "drake-interplanetary", "ironclad"],
  ["Pitbull",             "drake-interplanetary", "pitbull"],
  ["Vulture",             "drake-interplanetary", "vulture"],
  // Esperia
  ["Blade",               "esperia", "blade"],
  ["Glaive",              "esperia", "glaive"],
  ["Prowler",             "esperia", "prowler"],
  ["Talon",               "esperia", "talon"],
  // Gatac
  ["Railen",              "gatac", "railen"],
  ["Syulen",              "gatac", "syulen"],
  // Kruger
  ["P-52 Merlin",         "kruger-intergalactic", "p-52-merlin"],
  ["P-72 Archimedes",     "kruger-intergalactic", "p-72-archimedes"],
  // Mirai
  ["Fury",                "mirai", "fury"],
  ["Guardian",            "mirai", "guardian"],
  // MISC
  ["Endeavor",            "musashi-industrial-starflight-concern", "endeavor"],
  ["Expanse",             "musashi-industrial-starflight-concern", "expanse"],
  ["Fortune",             "musashi-industrial-starflight-concern", "misc-fortune"],
  ["Freelancer",          "musashi-industrial-starflight-concern", "freelancer"],
  ["Hull Series",         "musashi-industrial-starflight-concern", "hull"],
  ["Odyssey",             "musashi-industrial-starflight-concern", "odyssey"],
  ["Prospector",          "musashi-industrial-starflight-concern", "prospector"],
  ["Razor",               "musashi-industrial-starflight-concern", "razor"],
  ["Reliant",             "musashi-industrial-starflight-concern", "reliant"],
  ["Starfarer",           "musashi-industrial-starflight-concern", "starfarer"],
  ["Starlancer",          "musashi-industrial-starflight-concern", "starlancer"],
  ["Starlite",            "musashi-industrial-starflight-concern", "starlite"],
  // Origin Jumpworks
  ["85X",                 "origin-jumpworks", "85x"],
  ["100 Series",          "origin-jumpworks", "100-series"],
  ["300i Series",         "origin-jumpworks", "300i-series"],
  ["400i",                "origin-jumpworks", "400i"],
  ["600 Series",          "origin-jumpworks", "600-series"],
  ["890 Jump",            "origin-jumpworks", "890-jump"],
  ["M50",                 "origin-jumpworks", "m50"],
  ["M80",                 "origin-jumpworks", "m80"],
  // Roberts Space Industries
  ["Apollo",              "roberts-space-industries", "apollo"],
  ["Arrastra",            "roberts-space-industries", "arrastra"],
  ["Aurora",              "roberts-space-industries", "aurora"],
  ["Constellation",       "roberts-space-industries", "constellation"],
  ["Galaxy",              "roberts-space-industries", "galaxy"],
  ["Hermes",              "roberts-space-industries", "hermes"],
  ["Mantis",              "roberts-space-industries", "mantis"],
  ["Meteor",              "roberts-space-industries", "meteor"],
  ["Orion",               "roberts-space-industries", "orion"],
  ["Perseus",             "roberts-space-industries", "perseus"],
  ["Polaris",             "roberts-space-industries", "polaris"],
  ["Salvation",           "roberts-space-industries", "salvation"],
  ["Scorpius",            "roberts-space-industries", "scorpius"],
  ["Zeus MK II",          "roberts-space-industries", "zeus"],
  // Vanduul
  ["Scythe",              "vanduul", "scythe"],
  ["Glaive (Vanduul)",    "vanduul", "glaive"],
];

// ---------------------------------------------------------------------------
// Name normalisation (mirrors sh_scraper.py logic)
// ---------------------------------------------------------------------------
const MFR_PREFIX = /^(?:the\s+)?(?:RSI|MISC|Anvil|Aegis|Crusader|Argo|Aopoa|Origin|Drake|Mirai|Banu|Esperia|Gatac|Kruger|Consolidated Outland|Tumbril|Roberts Space Industries|Musashi Industrial|MSIC)\s+/i;

const NOISE: RegExp[] = [
  /\s*-\s*Upg?rade\b.*$/i,        // "- Upgrade" and typo "- Upagrade"
  /\s+Upg?rade\.?\s*$/i,          // trailing "Upgrade" / "Update" / "Upagrade"
  /\s+-\s*Update\b.*$/i,          // "- Update"
  /\s*-\s*Star Citizen.*$/i,
  /\s+CCU\b.*$/i,
  /\s*Standard Edition$/i,
  /\s*Best In Show Edition \d+/i,
  /\s*Pirate Edition$/i,
  /\s*\(Warbond[^)]*\)/i,
  /\s+Warbond\b/i,
  /\s*-\s*LTI\b/i,
  /\s*\bLTI\b/i,
  /\s*\d+\s*(?:yr|year)s?\s*ins\.?/i,
  /\s*OC\b/i,
  /\s*\+\s*Extras/i,
  /\s*CCU'ed/i,
  /,\s+(?:with|edition)\b.*$/i,   // ", with" / ", Edition ..."
  /\s+Edition\s+w[/&](?:r?u?a?nce|urance)\b.*$/i,  // "Edition w/ruance"
  /\s+-\s*$/,
];

const ALIASES: Record<string, string> = {
  "RSI Galaxy": "Galaxy", "Galaxy Standard Edition": "Galaxy",
  "MISC Hull B": "Hull B", "MISC Hull C": "Hull C", "MISC Hull D": "Hull D",
  "MISC Hull E": "Hull E", "MISC Odyssey": "Odyssey",
  "Aegis Hammerhead -": "Hammerhead", "Aegis Nautilus -": "Nautilus",
  "Aegis Reclaimer -": "Reclaimer", "Reclaimer": "Reclaimer",
  "Anvil Carrack -": "Carrack", "Anvil Liberator -": "Liberator",
  "RSI Arrastra -": "Arrastra", "RSI Orion -": "Orion",
  "RSI Perseus -": "Perseus", "Perseus": "Perseus",
  "RSI Polaris -": "Polaris",
  "Banu Merchantman -": "Merchantman",
  "Crusader A2 Hercules Starlifter -": "Hercules A2",
  "Crusader C2 Hercules -": "Hercules C2", "C2 Hercules": "Hercules C2",
  "Crusader M2 Hercules -": "Hercules M2",
  "Crusader Genesis Starliner -": "Genesis Starliner", "Genesis": "Genesis Starliner",
  "Esperia Prowler -": "Prowler",
  "RAFT WBCCU": "RAFT", "Argo Mole": "MOLE", "Argo MOLE": "MOLE",
};

function normalizeName(raw: string): string {
  let name = raw.trim();
  if (ALIASES[name]) return ALIASES[name];
  name = name.replace(/^(?:the\s+)?Upgrade\s*[-–]?\s*/i, "").trim();
  for (const pat of NOISE) name = name.replace(pat, "").trim();
  name = name.replace(MFR_PREFIX, "").trim();
  // Collapse multiple spaces
  name = name.replace(/\s{2,}/g, " ").trim();
  if (ALIASES[name]) return ALIASES[name];
  return name;
}

const CCU_RE = /^(.+?)\s+to\s+(.+?)(?:\s+(?:Upgrade|CCU|upgrade))?(?:\s*[\(\[].*)?$/i;

function parseCcuTitle(title: string): [string, string] | null {
  const m = CCU_RE.exec(title.trim());
  if (!m) return null;
  const from = normalizeName(m[1]);
  const to   = normalizeName(m[2]);
  if (from.length < 2 || to.length < 2) return null;
  return [from, to];
}

// ---------------------------------------------------------------------------
// Scraping
// ---------------------------------------------------------------------------
async function delay(ms: number) {
  await new Promise((r) => setTimeout(r, ms));
}

async function fetchPage(url: string): Promise<string | null> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(url, {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
          "Accept-Language": "en-US,en;q=0.9",
          "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        },
      });
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.text();
    } catch (e) {
      if (attempt === 2) return null;
      await delay(3000 * (attempt + 1));
    }
  }
  return null;
}

function parsePrice(text: string): number | null {
  const m = /[\d,]+\.?\d*/.exec(text.replace(/,/g, ""));
  return m ? parseFloat(m[0]) : null;
}

// Minimal HTML parser — extract product items from Magento markup
function extractItems(html: string): Array<{ title: string; price: number | null }> {
  const items: Array<{ title: string; price: number | null }> = [];

  // Find all product-item-info blocks
  const blockRe = /<(?:li|div)[^>]+class="[^"]*product-item[^"]*"[^>]*>([\s\S]*?)(?=<(?:li|div)[^>]+class="[^"]*product-item[^"]*"|<\/ul>|<\/div>\s*<\/(?:ol|ul|div)>)/gi;
  let bm: RegExpExecArray | null;

  while ((bm = blockRe.exec(html)) !== null) {
    const block = bm[1];

    // Title
    const titleM = /class="[^"]*product-item-link[^"]*"[^>]*>([\s\S]*?)<\/a>/i.exec(block);
    if (!titleM) continue;
    const title = titleM[1].replace(/<[^>]+>/g, "").trim();

    // Price — prefer data-price-amount attribute
    let price: number | null = null;
    const priceAttrM = /data-price-amount="([\d.]+)"/i.exec(block);
    if (priceAttrM) {
      price = parseFloat(priceAttrM[1]);
    } else {
      const priceTextM = /class="[^"]*price[^"]*"[^>]*>([\s\S]*?)<\/(?:span|div)>/i.exec(block);
      if (priceTextM) price = parsePrice(priceTextM[1].replace(/<[^>]+>/g, ""));
    }

    items.push({ title, price });
  }

  return items;
}

function hasNextPage(html: string): boolean {
  return /class="[^"]*action[^"]*next[^"]*"/.test(html) ||
         /class="[^"]*pages-item-next[^"]*"/.test(html);
}

async function scrapeShip(
  display: string,
  manufacturer: string,
  slug: string,
): Promise<Map<string, number>> {
  const baseUrl = `${BASE_URL}/star-citizen/spaceships/${manufacturer}/${slug}.html`;
  const best = new Map<string, number>(); // key = "from|||to"

  let page = 1;
  while (true) {
    const url = `${baseUrl}?p=${page}&product_list_limit=${PAGE_SIZE}`;
    const html = await fetchPage(url);
    if (!html) break;

    const items = extractItems(html);
    if (items.length === 0) break;

    for (const { title, price } of items) {
      if (!price || price <= 0) continue;
      const pair = parseCcuTitle(title);
      if (!pair) continue;
      const [from, to] = pair;
      const key = `${from}|||${to}`;
      if (!best.has(key) || price < best.get(key)!) best.set(key, price);
    }

    if (!hasNextPage(html)) break;
    page++;
    await delay(DELAY_MS);
  }

  return best;
}

// ---------------------------------------------------------------------------
// Edge function entry point
// ---------------------------------------------------------------------------
Deno.serve(async (req) => {
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization, x-sync-secret, content-type",
  };

  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  // Auth — accept either service role key or SYNC_SECRET header
  const secret = req.headers.get("x-sync-secret") ?? "";
  const authHeader = req.headers.get("authorization") ?? "";
  const isServiceRole = authHeader.includes(SERVICE_KEY);
  if (secret !== SYNC_SECRET && !isServiceRole) {
    return Response.json({ error: "Forbidden" }, { status: 403, headers: cors });
  }

  const sb = createClient(SUPABASE_URL, SERVICE_KEY);

  const body = req.method === "POST" && req.headers.get("content-type")?.includes("json")
    ? await req.json().catch(() => ({}))
    : {};

  // action=truncate: wipe the table
  if (body?.action === "truncate") {
    const { error } = await sb.rpc("truncate_sh_ccus");
    if (error) return Response.json({ error: error.message }, { status: 500, headers: cors });
    return Response.json({ ok: true, action: "truncate" }, { headers: cors });
  }

  // action=load: insert a batch of pre-scraped edges (no truncate — call truncate first separately)
  if (body?.action === "load" && Array.isArray(body.edges)) {
    const scrapedAt = body.scraped_at ?? new Date().toISOString();
    const rows = (body.edges as Array<{ from: string; to: string; price: number }>).map((e) => ({
      from_ship: e.from, to_ship: e.to, price: e.price, scraped_at: scrapedAt,
    }));

    let inserted = 0;
    const batchSize = 500;
    for (let i = 0; i < rows.length; i += batchSize) {
      const { error } = await sb.from("sh_ccus").insert(rows.slice(i, i + batchSize));
      if (error) return Response.json({ error: error.message, batch: i }, { status: 500, headers: cors });
      inserted += Math.min(batchSize, rows.length - i);
    }
    return Response.json({ ok: true, action: "load", inserted }, { headers: cors });
  }

  // Full scrape — fire and forget via waitUntil so the response returns immediately
  async function runScrape() {
    const scrapedAt = new Date().toISOString();
    const globalBest = new Map<string, number>();
    const errors: string[] = [];

    for (const [display, manufacturer, slug] of SHIPS) {
      try {
        const shipBest = await scrapeShip(display, manufacturer, slug);
        for (const [key, price] of shipBest) {
          if (!globalBest.has(key) || price < globalBest.get(key)!) globalBest.set(key, price);
        }
      } catch (e) {
        errors.push(`${display}: ${e instanceof Error ? e.message : String(e)}`);
      }
      await delay(DELAY_MS);
    }

    const rows = [...globalBest.entries()].map(([key, price]) => {
      const [from_ship, to_ship] = key.split("|||");
      return { from_ship, to_ship, price, scraped_at: scrapedAt };
    });

    const batchSize = 500;
    for (let i = 0; i < rows.length; i += batchSize) {
      await sb.from("sh_ccus").upsert(
        rows.slice(i, i + batchSize),
        { onConflict: "from_ship,to_ship" },
      );
    }
  }

  // @ts-ignore — EdgeRuntime is available in Supabase Deno edge functions
  EdgeRuntime.waitUntil(runScrape());

  return Response.json({ ok: true, job: "started" }, { headers: cors });
});
