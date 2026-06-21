-- ── locations ────────────────────────────────────────────────────────────────
-- All navigable locations in the simulator: stations, cities, outposts.
-- Drives UI rules: what tabs show, what the player can do here.

create table public.locations (
  key               text primary key,
  name              text    not null,
  system            text    not null default 'Stanton',
  location_type     text    not null check (location_type in ('station','city','outpost')),
  has_refinery      boolean not null default false,
  sells_ships       boolean not null default false,
  sells_mining_gear boolean not null default false,
  -- UEX terminal code(s) that serve commodity trading here (comma-separated if >1)
  uex_codes         text,
  -- 3D scene position for the starmap (matches existing bodies/stations coords)
  scene_x           real,
  scene_y           real,
  scene_z           real,
  sort_order        integer not null default 0
);

alter table public.locations enable row level security;
create policy "public read locations" on public.locations for select using (true);

-- ── Seed: Stanton locations ───────────────────────────────────────────────────

insert into public.locations (key, name, system, location_type, has_refinery, sells_ships, sells_mining_gear, uex_codes, sort_order) values
  -- Stations WITH refinery (buy raw + refined, sell mining gear)
  ('everus_harbor',  'Everus Harbor',              'Stanton', 'station', true,  false, true,  'EVERU,RCHL1',  10),
  ('hur_l2',         'HUR-L2 Faithful Dream',      'Stanton', 'station', true,  false, true,  'HURL2,RCHL2',  11),
  ('arc_l1',         'ARC-L1 Wide Forest',         'Stanton', 'station', true,  false, true,  'ARCL1,RCAL1',  20),
  ('arc_l2',         'ARC-L2 Lively Pathway',      'Stanton', 'station', true,  false, true,  'ARCL2,RCAL2',  21),
  ('arc_l4',         'ARC-L4 Faint Glen',          'Stanton', 'station', true,  false, true,  'ARCL4,RCAL4',  22),
  ('mic_l1',         'MIC-L1 Shallow Frontier',    'Stanton', 'station', true,  false, true,  'MICL1,RCML1',  30),
  ('mic_l2',         'MIC-L2 Long Forest',         'Stanton', 'station', true,  false, true,  'MICL2,RCML2',  31),
  ('mic_l5',         'MIC-L5 Modern Icarus',       'Stanton', 'station', true,  false, true,  'MICL5,RCML5',  32),
  ('cru_l1',         'CRU-L1 Ambitious Dream',     'Stanton', 'station', true,  false, true,  'CRUL1,RCCL1',  40),
  -- Stations WITHOUT refinery (buy refined only, sell mining gear)
  ('baijini',        'Baijini Point',              'Stanton', 'station', false, false, true,  'BAIJI',        50),
  ('port_tressler',  'Port Tressler',              'Stanton', 'station', false, false, true,  'TRESS',        51),
  ('arc_l3',         'ARC-L3 Modern Express',      'Stanton', 'station', false, false, false, 'ARCL3',        23),
  ('arc_l5',         'ARC-L5 Yellow Core',         'Stanton', 'station', false, false, false, 'ARCL5',        24),
  ('hur_l1',         'HUR-L1 Green Glade',         'Stanton', 'station', false, false, true,  'HURL1',        12),
  ('hur_l3',         'HUR-L3 Thundering Express',  'Stanton', 'station', false, false, false, 'HURL3',        13),
  ('hur_l4',         'HUR-L4 Melodic Fields',      'Stanton', 'station', false, false, false, 'HURL4',        14),
  ('hur_l5',         'HUR-L5 High Course',         'Stanton', 'station', false, false, false, 'HURL5',        15),
  ('cru_l4',         'CRU-L4 Shallow Fields',      'Stanton', 'station', false, false, false, 'CRUL4',        41),
  ('cru_l5',         'CRU-L5 Beautiful Glen',      'Stanton', 'station', false, false, false, 'CRUL5',        42),
  ('mic_l3',         'MIC-L3 Endless Odyssey',     'Stanton', 'station', false, false, false, 'MICL3',        33),
  ('mic_l4',         'MIC-L4 Red Crossroads',      'Stanton', 'station', false, false, false, 'MICL4',        34),
  ('grimhex',        'GrimHEX',                    'Stanton', 'station', false, false, true,  'GRIMX',        60),
  ('seraphim',       'Seraphim Station',           'Stanton', 'station', false, false, true,  null,           43),
  -- Cities (sell ships + mining gear; no refinery except Levski/Lorville rules)
  ('lorville',       'Lorville',                   'Stanton', 'city',    false, true,  true,  'CBD,L19AD',    70),
  ('area18',         'Area 18',                    'Stanton', 'city',    false, true,  true,  'TDA18,IONOR',  71),
  ('new_babbage',    'New Babbage',                'Stanton', 'city',    false, true,  true,  'MTPLA',        72),
  ('orison',         'Orison',                     'Stanton', 'city',    false, true,  true,  'ORIMS',        73),
  -- Out-of-Stanton with refinery (accessible via jump point)
  ('levski',         'Levski',                     'Nyx',     'city',    true,  true,  true,  'RCLEV',        80),
  ('ruin_station',   'Ruin Station',               'Pyro',    'station', true,  false, true,  'RCRUI',        81),
  ('checkmate',      'Checkmate',                  'Pyro',    'station', true,  false, false, 'RCCHE',        82),
  ('orbituary',      'Orbituary',                  'Pyro',    'station', true,  false, false, 'RCORB',        83);

-- ── player_ships ─────────────────────────────────────────────────────────────
-- Which ships a player owns. Prospector is granted automatically on first login.

create table public.player_ships (
  player_id   uuid not null references public.players(id) on delete cascade,
  ship_type   text not null check (ship_type in ('prospector','mole')),
  acquired_at timestamptz not null default now(),
  primary key (player_id, ship_type)
);

alter table public.player_ships enable row level security;
create policy "own ships" on public.player_ships for all using (player_id = auth.uid());
create policy "public read ships" on public.player_ships for select using (true);

-- ── players: add location_key ────────────────────────────────────────────────
alter table public.players
  add column if not exists location_key text not null default 'everus_harbor'
    references public.locations(key) on update cascade;

-- ── on_auth_user_created: grant Prospector + set starting location ────────────
-- Replaces (or extends) the existing trigger that creates the players row.
-- The trigger just needs to ensure player_ships gets a prospector row.
-- We use a separate trigger on players INSERT to avoid rewriting auth trigger.

create or replace function public.on_player_created()
returns trigger language plpgsql security definer as $$
begin
  -- Grant starting ship
  insert into public.player_ships (player_id, ship_type)
  values (new.id, 'prospector')
  on conflict do nothing;

  return new;
end;
$$;

create trigger player_created_grant_ship
  after insert on public.players
  for each row execute function public.on_player_created();

-- ── sell_minerals RPC ─────────────────────────────────────────────────────────
-- Player sells minerals from ship_inventory at their current location.
-- Validates location rules (refinery needed for raw, no-refinery for refined).
-- Uses commodity_prices / commodity_raw_prices for UEX prices.

create or replace function public.sell_minerals(
  p_player_id   uuid,
  p_station_key text,
  p_mineral     text,
  p_quantity_scu real,
  p_is_refined  boolean
) returns jsonb language plpgsql security definer as $$
declare
  v_location    record;
  v_price_auec  numeric;
  v_total       bigint;
  v_inventory   real;
begin
  -- Verify location exists and has the right capability
  select * into v_location from public.locations where key = p_station_key;
  if not found then
    return jsonb_build_object('error', 'location_not_found');
  end if;

  if p_is_refined = false and not v_location.has_refinery then
    return jsonb_build_object('error', 'no_refinery_at_location');
  end if;

  -- Get best available price for this mineral at this location
  -- (commodity_raw_prices for raw, commodity_prices for refined)
  if p_is_refined then
    select price_sell into v_price_auec
      from public.commodity_prices cp
      join public.commodities c on cp.id_commodity = c.id
     where lower(c.name) = lower(p_mineral)
     order by price_sell desc nulls last
     limit 1;
  else
    select price_sell into v_price_auec
      from public.commodity_raw_prices crp
      join public.commodities c on crp.id_commodity = c.id
     where lower(c.name) = lower(p_mineral)
     order by price_sell desc nulls last
     limit 1;
  end if;

  if v_price_auec is null or v_price_auec <= 0 then
    return jsonb_build_object('error', 'no_price_available');
  end if;

  -- Check inventory
  select quantity_scu into v_inventory
    from public.ship_inventory
   where player_id = p_player_id
     and station_key = p_station_key
     and mineral = p_mineral;

  if not found or v_inventory < p_quantity_scu then
    return jsonb_build_object('error', 'insufficient_inventory');
  end if;

  v_total := floor(v_price_auec * p_quantity_scu)::bigint;

  -- Deduct inventory
  update public.ship_inventory
     set quantity_scu = quantity_scu - p_quantity_scu
   where player_id = p_player_id
     and station_key = p_station_key
     and mineral = p_mineral;

  -- Credit aUEC
  update public.players
     set auec = auec + v_total
   where id = p_player_id;

  return jsonb_build_object(
    'ok',          true,
    'auec_earned', v_total,
    'price_per_scu', v_price_auec
  );
end;
$$;

grant execute on function public.sell_minerals(uuid, text, text, real, boolean) to authenticated;

-- ── buy_ship RPC ─────────────────────────────────────────────────────────────
-- Player buys a ship. Must be at a location with sells_ships = true.

create or replace function public.buy_ship(
  p_player_id   uuid,
  p_ship_type   text,
  p_station_key text
) returns jsonb language plpgsql security definer as $$
declare
  v_price  bigint;
  v_wallet bigint;
  v_loc    record;
begin
  select * into v_loc from public.locations where key = p_station_key;
  if not found or not v_loc.sells_ships then
    return jsonb_build_object('error', 'ships_not_sold_here');
  end if;

  if exists (select 1 from public.player_ships where player_id = p_player_id and ship_type = p_ship_type) then
    return jsonb_build_object('error', 'already_owned');
  end if;

  v_price := case p_ship_type
    when 'prospector' then 2850000
    when 'mole'       then 5130000
    else null
  end;

  if v_price is null then
    return jsonb_build_object('error', 'unknown_ship');
  end if;

  select auec into v_wallet from public.players where id = p_player_id;
  if v_wallet < v_price then
    return jsonb_build_object('error', 'insufficient_funds');
  end if;

  update public.players set auec = auec - v_price where id = p_player_id;
  insert into public.player_ships (player_id, ship_type) values (p_player_id, p_ship_type);

  return jsonb_build_object('ok', true, 'new_balance', v_wallet - v_price);
end;
$$;

grant execute on function public.buy_ship(uuid, text, text) to authenticated;
