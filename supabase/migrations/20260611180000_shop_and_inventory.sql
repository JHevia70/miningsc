-- Shop items catalogue: what each station sells
-- Components affect ship stats when equipped
create table shop_items (
  id           serial primary key,
  key          text    not null unique,
  name         text    not null,
  category     text    not null check (category in ('laser','module','mining_head','cargo','livery')),
  ship_type    text    check (ship_type in ('prospector','mole','any')),
  description  text    not null default '',
  color_hex    text    not null default '#888888',
  price_auec   integer not null default 0,
  -- stat modifiers (NULL = no effect)
  mining_time_mult  numeric,   -- e.g. 0.8 = 20% faster
  cargo_bonus_scu   integer,   -- extra SCU capacity
  yield_mult        numeric,   -- e.g. 1.2 = 20% more yield
  sort_order   integer not null default 0
);

-- Which items each station sells (NULL station_key = all stations)
create table station_shop (
  station_key  text not null,
  item_key     text not null references shop_items(key) on delete cascade,
  primary key (station_key, item_key)
);

-- Player inventory: items owned (liveries already in player_liveries, this covers components)
create table player_inventory (
  id           bigserial primary key,
  player_id    uuid not null references players(id) on delete cascade,
  item_key     text not null references shop_items(key) on delete cascade,
  purchased_at timestamptz not null default now(),
  unique (player_id, item_key)
);

alter table player_inventory enable row level security;
create policy "own inventory" on player_inventory for all using (player_id = auth.uid());
create policy "anon insert inventory" on player_inventory for insert with check (true);

-- Ship loadout: which item is equipped in each slot per ship
create table ship_loadout (
  player_id   uuid not null references players(id) on delete cascade,
  ship_type   text not null check (ship_type in ('prospector','mole')),
  slot        text not null,   -- 'laser', 'module_1', 'module_2', 'mining_head_l', etc.
  item_key    text references shop_items(key) on delete set null,
  primary key (player_id, ship_type, slot)
);

alter table ship_loadout enable row level security;
create policy "own loadout" on ship_loadout for all using (player_id = auth.uid());
create policy "anon insert loadout" on ship_loadout for insert with check (true);

-- Refinery queue (simple)
create table refinery_queue (
  id            bigserial primary key,
  player_id     uuid not null references players(id) on delete cascade,
  station_key   text not null,
  mineral       text not null,
  raw_scu       numeric not null,
  refined_scu   numeric,           -- set when ready
  cost_auec     integer not null,
  started_at    timestamptz not null default now(),
  ready_at      timestamptz not null,
  collected     boolean not null default false
);

alter table refinery_queue enable row level security;
create policy "own refinery" on refinery_queue for all using (player_id = auth.uid());
create policy "anon insert refinery" on refinery_queue for insert with check (true);

-- RPC: buy shop item (component or livery-via-shop)
create or replace function buy_shop_item(p_player_id uuid, p_item_key text)
returns jsonb language plpgsql security definer as $$
declare
  v_price  integer;
  v_wallet bigint;
  v_cat    text;
begin
  select price_auec, category into v_price, v_cat from shop_items where key = p_item_key;
  if not found then return jsonb_build_object('error','item_not_found'); end if;

  if exists (select 1 from player_inventory where player_id = p_player_id and item_key = p_item_key) then
    return jsonb_build_object('error','already_owned');
  end if;

  select auec into v_wallet from players where id = p_player_id;
  if v_wallet < v_price then return jsonb_build_object('error','insufficient_funds'); end if;

  update players set auec = auec - v_price where id = p_player_id;
  insert into player_inventory (player_id, item_key) values (p_player_id, p_item_key);

  return jsonb_build_object('ok', true, 'new_balance', v_wallet - v_price);
end;
$$;
grant execute on function buy_shop_item(uuid, text) to anon, authenticated;

-- RPC: equip item to ship slot
create or replace function equip_item(p_player_id uuid, p_ship_type text, p_slot text, p_item_key text)
returns jsonb language plpgsql security definer as $$
begin
  if p_item_key is not null and not exists (
    select 1 from player_inventory where player_id = p_player_id and item_key = p_item_key
  ) then
    return jsonb_build_object('error','not_owned');
  end if;

  insert into ship_loadout (player_id, ship_type, slot, item_key)
  values (p_player_id, p_ship_type, p_slot, p_item_key)
  on conflict (player_id, ship_type, slot) do update set item_key = excluded.item_key;

  return jsonb_build_object('ok', true);
end;
$$;
grant execute on function equip_item(uuid, text, text, text) to anon, authenticated;

-- RPC: start refinery job (simple: 1h, 70% yield, 50 aUEC/SCU cost)
create or replace function start_refinery(p_player_id uuid, p_station_key text, p_mineral text, p_raw_scu numeric)
returns jsonb language plpgsql security definer as $$
declare
  v_cost   integer;
  v_wallet bigint;
begin
  v_cost := greatest(1, floor(p_raw_scu * 50))::integer;
  select auec into v_wallet from players where id = p_player_id;
  if v_wallet < v_cost then return jsonb_build_object('error','insufficient_funds'); end if;

  update players set auec = auec - v_cost where id = p_player_id;

  insert into refinery_queue (player_id, station_key, mineral, raw_scu, refined_scu, cost_auec, ready_at)
  values (p_player_id, p_station_key, p_mineral, p_raw_scu,
          round(p_raw_scu * 0.70, 1),
          v_cost,
          now() + interval '1 hour');

  return jsonb_build_object('ok', true, 'new_balance', v_wallet - v_cost, 'ready_in_minutes', 60);
end;
$$;
grant execute on function start_refinery(uuid, text, text, numeric) to anon, authenticated;

-- Public read on catalogue tables
alter table shop_items     enable row level security;
alter table station_shop   enable row level security;
create policy "public read shop_items"   on shop_items   for select using (true);
create policy "public read station_shop" on station_shop for select using (true);

-- ── Seed: shop items ─────────────────────────────────────────────────────────

-- Mining lasers (Prospector)
insert into shop_items (key, name, category, ship_type, description, color_hex, price_auec, mining_time_mult, sort_order) values
  ('laser_arbor_1sc',   'Arbor MDS-100',  'laser', 'prospector', 'Láser estándar. Equilibrado.',        '#aaaacc', 0,      1.00, 0),
  ('laser_hofstede_s1', 'Hofstede S1',    'laser', 'prospector', 'Mayor potencia, más calor.',           '#cc8844', 12000, 0.85, 1),
  ('laser_helix_1',     'Helix I',        'laser', 'prospector', 'Especializado en roca dura.',          '#44aacc', 18000, 0.80, 2),
  ('laser_impact_1',    'Impact I',       'laser', 'prospector', 'Máxima potencia. Alto coste.',         '#cc4444', 28000, 0.72, 3);

-- Mining heads (MOLE — 3 slots: front, left, right)
insert into shop_items (key, name, category, ship_type, description, color_hex, price_auec, mining_time_mult, sort_order) values
  ('head_arbor_2sc',    'Arbor MDS-200',  'mining_head', 'mole', 'Cabeza estándar MOLE.',               '#aaaacc', 0,      1.00, 0),
  ('head_helix_2',      'Helix II',       'mining_head', 'mole', 'Extracción rápida, menos calor.',     '#44aacc', 22000, 0.82, 1),
  ('head_hofstede_s2',  'Hofstede S2',    'mining_head', 'mole', 'Potencia bruta, rocas grandes.',      '#cc8844', 30000, 0.78, 2),
  ('head_impact_2',     'Impact II',      'mining_head', 'mole', 'El más potente del mercado.',         '#cc4444', 45000, 0.68, 3);

-- Laser modules (both ships, 2 slots each)
insert into shop_items (key, name, category, ship_type, description, color_hex, price_auec, yield_mult, sort_order) values
  ('mod_stampede',   'Stampede',      'module', 'any', 'Aumenta la velocidad de extracción.',  '#88ccaa', 8000,  1.10, 0),
  ('mod_surge',      'Surge',         'module', 'any', 'Pico de potencia breve pero intenso.', '#ccaa44', 10000, 1.15, 1),
  ('mod_rieger_c2',  'Rieger C2',     'module', 'any', 'Reduce el sobrecalentamiento.',        '#4488cc', 12000, 1.12, 2),
  ('mod_lifeline',   'Lifeline',      'module', 'any', 'Estabiliza la ventana de extracción.', '#44cc88', 14000, 1.18, 3),
  ('mod_brandt',     'Brandt',        'module', 'any', 'Fragmenta rocas grandes.',             '#cc6644', 16000, 1.20, 4);

-- Cargo upgrades
insert into shop_items (key, name, category, ship_type, description, color_hex, price_auec, cargo_bonus_scu, sort_order) values
  ('cargo_prosp_ext', 'Bolsa de carga +8 SCU',  'cargo', 'prospector', 'Amplía la tolva de la Prospector.',  '#8888cc', 20000, 8,  0),
  ('cargo_mole_ext',  'Contenedor +24 SCU',      'cargo', 'mole',       'Contenedor adicional para la MOLE.', '#8888cc', 35000, 24, 0);

-- ── Seed: station_shop (all stations sell the same catalogue for now) ─────────
insert into station_shop (station_key, item_key)
select s.key, i.key
from (values
  ('cru_l1'),('cru_l5'),('hur_l1'),('hur_l2'),('arc_l1'),('mic_l1'),
  ('orison'),('port_tressler'),('baijini'),('everus_harbor')
) as s(key)
cross join shop_items i;
