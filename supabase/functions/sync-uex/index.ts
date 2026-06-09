/**
 * sync-uex: Syncs commodity prices, star systems, and planets from UEX Corp API.
 * Called by pg_cron every 24h, or manually via POST.
 */
import { createClient } from "jsr:@supabase/supabase-js@2";

const UEX_BASE    = "https://uexcorp.space/api/2.0";
const UEX_TOKEN   = Deno.env.get("UEX_API_TOKEN")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const uexHeaders = { "Authorization": `Bearer ${UEX_TOKEN}` };

async function fetchUEX(path: string) {
  const res = await fetch(`${UEX_BASE}${path}`, { headers: uexHeaders });
  if (!res.ok) throw new Error(`UEX ${path} → ${res.status}`);
  const json = await res.json();
  return json.data as Record<string, unknown>[];
}

Deno.serve(async (_req) => {
  const sb = createClient(SUPABASE_URL, SUPABASE_KEY);
  const results: Record<string, unknown> = {};

  // ── 1. Sync star systems ──────────────────────────────────────────────
  const systems = await fetchUEX("/star_systems");
  const activeSystems = systems.filter((s) => s.is_available_live);
  for (const s of activeSystems) {
    await sb.from("systems").upsert(
      { name: s.name as string, uex_id: s.id as number },
      { onConflict: "name" },
    );
  }
  results.systems = activeSystems.length;

  // ── 2. Sync planets & moons ───────────────────────────────────────────
  const [planets, moons] = await Promise.all([
    fetchUEX("/planets"),
    fetchUEX("/moons"),
  ]);

  // Build system name→id map
  const { data: sysRows } = await sb.from("systems").select("id, name, uex_id");
  const sysById: Record<number, number> = {};
  for (const r of sysRows ?? []) sysById[r.uex_id] = r.id;

  for (const p of [...planets, ...moons].filter((b) => b.is_available_live)) {
    const systemId = sysById[p.id_star_system as number];
    if (!systemId) continue;
    const type = moons.includes(p) ? "moon" : "planet";
    await sb.from("bodies").upsert(
      { name: p.name as string, system_id: systemId, type, uex_id: p.id as number },
      { onConflict: "uex_id" },
    );
  }
  results.bodies = planets.filter((p) => p.is_available_live).length +
    moons.filter((m) => m.is_available_live).length;

  // ── 3. Sync mineral commodities ───────────────────────────────────────
  const commodities = await fetchUEX("/commodities?is_mineral=1");

  // Build mineral name→id map (case-insensitive, strip " (Ore)" / " (Raw)" suffixes)
  const { data: minRows } = await sb.from("minerals").select("id, name");
  const mineralByName: Record<string, number> = {};
  for (const m of minRows ?? []) mineralByName[m.name.toUpperCase()] = m.id;

  function resolveMineralId(name: string): number | null {
    const clean = name.toUpperCase()
      .replace(/\s*\(ORE\)|\s*\(RAW\)|\s*\(REFINED\)/g, "")
      .trim();
    return mineralByName[clean] ?? null;
  }

  const commRows = commodities.map((c) => ({
    id:           c.id as number,
    id_parent:    c.id_parent as number | null,
    mineral_id:   resolveMineralId(c.name as string),
    name:         c.name as string,
    code:         c.code as string,
    kind:         c.kind as string,
    is_raw:       c.is_raw === 1,
    is_refined:   c.is_refined === 1,
    is_refinable: c.is_refinable === 1,
    price_buy:    (c.price_buy as number) ?? 0,
    price_sell:   (c.price_sell as number) ?? 0,
    is_available: c.is_available_live === 1,
    wiki:         c.wiki as string | null,
    uex_updated_at: c.date_modified
      ? new Date((c.date_modified as number) * 1000).toISOString()
      : null,
    synced_at:    new Date().toISOString(),
  }));

  const { error: commErr } = await sb.from("commodities").upsert(commRows, { onConflict: "id" });
  if (commErr) throw new Error(`commodities upsert: ${commErr.message}`);
  results.commodities = commRows.length;

  // ── 4. Sync per-terminal prices (refined) + raw prices ───────────────
  // Build terminal location lookup from /terminals
  const terminals = await fetchUEX("/terminals");
  const terminalLocation: Record<number, string> = {};
  for (const t of terminals) {
    const id = t.id as number;
    const loc = (t.city_name ?? t.space_station_name ?? t.moon_name ?? t.planet_name ?? t.orbit_name ?? "") as string;
    terminalLocation[id] = loc;
  }

  const mineralCommIds = new Set(commRows.map((c) => c.id));
  const batchSize = 500;

  // Refined prices
  const allPrices = await fetchUEX("/commodities_prices_all");
  const priceRows = allPrices
    .filter((p) => mineralCommIds.has(p.id_commodity as number) && (p.price_sell as number) > 0)
    .map((p) => ({
      id_commodity:   p.id_commodity as number,
      id_terminal:    p.id_terminal as number,
      terminal_name:  p.terminal_name as string,
      location:       terminalLocation[p.id_terminal as number] ?? null,
      price_sell:     Math.round(p.price_sell as number),
      price_sell_avg: Math.round((p.price_sell_avg as number) ?? 0),
      scu_sell:       Math.round((p.scu_sell as number) ?? 0),
      date_modified:  p.date_modified ? new Date((p.date_modified as number) * 1000).toISOString() : null,
      synced_at:      new Date().toISOString(),
    }));

  await sb.from("commodity_prices").delete().neq("id", 0);
  for (let i = 0; i < priceRows.length; i += batchSize) {
    const { error } = await sb.from("commodity_prices").upsert(priceRows.slice(i, i + batchSize), { onConflict: "id_commodity,id_terminal" });
    if (error) throw new Error(`commodity_prices upsert: ${error.message}`);
  }
  results.commodity_prices = priceRows.length;

  // Raw prices (refinery buy prices for unprocessed ore)
  const allRawPrices = await fetchUEX("/commodities_raw_prices_all");
  const rawPriceRows = allRawPrices
    .filter((p) => mineralCommIds.has(p.id_commodity as number) && (p.price_sell as number) > 0)
    .map((p) => ({
      id_commodity:   p.id_commodity as number,
      id_terminal:    p.id_terminal as number,
      terminal_name:  p.terminal_name as string,
      location:       terminalLocation[p.id_terminal as number] ?? null,
      price_sell:     Math.round(p.price_sell as number),
      price_sell_avg: Math.round((p.price_sell_avg as number) ?? 0),
      date_modified:  p.date_modified ? new Date((p.date_modified as number) * 1000).toISOString() : null,
      synced_at:      new Date().toISOString(),
    }));

  await sb.from("commodity_raw_prices").delete().neq("id", 0);
  for (let i = 0; i < rawPriceRows.length; i += batchSize) {
    const { error } = await sb.from("commodity_raw_prices").upsert(rawPriceRows.slice(i, i + batchSize), { onConflict: "id_commodity,id_terminal" });
    if (error) throw new Error(`commodity_raw_prices upsert: ${error.message}`);
  }
  results.commodity_raw_prices = rawPriceRows.length;

  return new Response(JSON.stringify({ ok: true, ...results }), {
    headers: { "Content-Type": "application/json" },
  });
});
