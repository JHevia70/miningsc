-- Ship liveries: catalogue of available paint jobs + player ownership
-- Liveries are purchased with aUEC earned from mining operations

create table ship_liveries (
  id          serial primary key,
  ship_type   text    not null check (ship_type in ('prospector','mole')),
  key         text    not null unique,          -- e.g. paint_prospector_dolivine_green
  name        text    not null,
  color_hex   text    not null,                 -- dominant tint colour for 3D viewer
  price_auec  integer not null default 0,       -- 0 = default livery (free)
  sort_order  integer not null default 0
);

create table player_liveries (
  player_id   uuid  not null references players(id) on delete cascade,
  livery_key  text  not null references ship_liveries(key) on delete cascade,
  purchased_at timestamptz not null default now(),
  primary key (player_id, livery_key)
);

alter table player_liveries enable row level security;

create policy "own liveries" on player_liveries
  for all using (player_id = auth.uid());

-- Allow anon select on catalogue
alter table ship_liveries enable row level security;
create policy "public read liveries" on ship_liveries
  for select using (true);

-- Active livery per player per ship (null = default)
alter table players
  add column if not exists active_livery_prospector text references ship_liveries(key),
  add column if not exists active_livery_mole        text references ship_liveries(key);

-- aUEC wallet on players
alter table players
  add column if not exists auec bigint not null default 0;

-- RPC: purchase a livery
create or replace function purchase_livery(p_player_id uuid, p_livery_key text)
returns jsonb language plpgsql security definer as $$
declare
  v_price  integer;
  v_wallet bigint;
begin
  select price_auec into v_price from ship_liveries where key = p_livery_key;
  if not found then return jsonb_build_object('error','livery_not_found'); end if;

  -- already owned?
  if exists (select 1 from player_liveries where player_id = p_player_id and livery_key = p_livery_key) then
    return jsonb_build_object('error','already_owned');
  end if;

  select auec into v_wallet from players where id = p_player_id;
  if v_wallet < v_price then return jsonb_build_object('error','insufficient_funds'); end if;

  update players set auec = auec - v_price where id = p_player_id;
  insert into player_liveries (player_id, livery_key) values (p_player_id, p_livery_key);
  return jsonb_build_object('ok', true, 'new_balance', v_wallet - v_price);
end;
$$;

grant execute on function purchase_livery(uuid, text) to anon, authenticated;

-- RPC: equip a livery
create or replace function equip_livery(p_player_id uuid, p_livery_key text)
returns jsonb language plpgsql security definer as $$
declare
  v_ship text;
begin
  select ship_type into v_ship from ship_liveries where key = p_livery_key;
  if not found then return jsonb_build_object('error','livery_not_found'); end if;

  -- must own it (or price=0)
  if not exists (
    select 1 from player_liveries where player_id = p_player_id and livery_key = p_livery_key
  ) and (select price_auec from ship_liveries where key = p_livery_key) > 0 then
    return jsonb_build_object('error','not_owned');
  end if;

  if v_ship = 'prospector' then
    update players set active_livery_prospector = p_livery_key where id = p_player_id;
  else
    update players set active_livery_mole = p_livery_key where id = p_player_id;
  end if;

  return jsonb_build_object('ok', true);
end;
$$;

grant execute on function equip_livery(uuid, text) to anon, authenticated;

-- RPC: credit aUEC when a mining run completes (called by complete_mining_run)
-- We amend complete_mining_run to also credit aUEC at 100 aUEC/SCU
create or replace function complete_mining_run(
  p_operation_id bigint,
  p_mineral      text,
  p_station_key  text,
  p_quantity_scu numeric
) returns jsonb language plpgsql security definer as $$
declare
  v_player uuid;
  v_auec   bigint;
begin
  select player_id into v_player from mining_operations where id = p_operation_id;
  if not found then return jsonb_build_object('error','op_not_found'); end if;

  -- Credit aUEC: 100 per SCU
  v_auec := greatest(0, floor(p_quantity_scu * 100))::bigint;
  update players set auec = auec + v_auec where id = v_player;

  -- Reset operation to docked
  update mining_operations set
    state            = 'docked',
    state_changed_at = now(),
    arrives_at       = null,
    cargo_scu        = 0,
    origin_x = null, origin_y = null, origin_z = null,
    dest_x   = null, dest_y   = null, dest_z   = null
  where id = p_operation_id;

  return jsonb_build_object('ok', true, 'auec_earned', v_auec);
end;
$$;

-- ── Seed: Prospector liveries ─────────────────────────────────────────────────
insert into ship_liveries (ship_type, key, name, color_hex, price_auec, sort_order) values
  ('prospector','paint_prospector_default',                   'Default',              '#4a6080',      0,  0),
  ('prospector','paint_prospector_iae2950_grey_blue',         'IAE Grey Blue',        '#00abff',  15000,  1),
  ('prospector','paint_prospector_iae2950_grey_white',        'IAE Grey White',       '#c8e8ff',  15000,  2),
  ('prospector','paint_prospector_dolivine_green',            'Dolivine Green',       '#6a9940',  25000,  3),
  ('prospector','paint_prospector_hadanite_pink',             'Hadanite Pink',        '#e06080',  25000,  4),
  ('prospector','paint_prospector_aphorite_purple',           'Aphorite Purple',      '#8855cc',  25000,  5),
  ('prospector','paint_prospector_luminalia_2953_green_red',  'Luminalia Red',        '#cc2200',  20000,  6),
  ('prospector','paint_prospector_luminalia_2953_white_blue', 'Luminalia White',      '#aaccff',  20000,  7),
  ('prospector','paint_prospector_workersweek_white_blue_blue','Workers Week',        '#2266cc',  18000,  8),
  ('prospector','paint_prospector_ninetails',                 'Nine-Tails',           '#cc3333',  30000,  9),
  ('prospector','paint_prospector_scavengers_black_black_black','Scavengers Black',   '#333333',  30000, 10),
  ('prospector','paint_prospector_blue_turquoise',            'Unity Turquoise',      '#00d4cc',  35000, 11),
  ('prospector','paint_prospector_iae_2952_black',            'IAE 2952 Black',       '#555566',  20000, 12);

-- ── Seed: MOLE liveries ───────────────────────────────────────────────────────
insert into ship_liveries (ship_type, key, name, color_hex, price_auec, sort_order) values
  ('mole','paint_mole_orange',             'Default Orange',    '#e07020',      0,  0),
  ('mole','paint_mole_yellow_black_blue',  'Pyrotechnic',       '#ffc600',  20000,  1),
  ('mole','paint_mole_yellow_grey_black',  'Greycat',           '#cc7700',  20000,  2),
  ('mole','paint_mole_bronze_black_brown', 'Shubin Bronze',     '#c84400',  25000,  3),
  ('mole','paint_mole_dolivine_green',     'Dolivine Green',    '#6a9940',  25000,  4),
  ('mole','paint_mole_hadanite_pink',      'Hadanite Pink',     '#e06080',  25000,  5),
  ('mole','paint_mole_aphorite_purple',    'Aphorite Purple',   '#8855cc',  25000,  6),
  ('mole','paint_mole_workersweek_white_blue_blue','Workers Week','#2266cc',18000,  7),
  ('mole','paint_mole_lovestruck_pink_black','Lovestruck',       '#cc4466',  20000,  8),
  ('mole','paint_mole_black_vip',          'Carbon Black',      '#222233',  40000,  9),
  ('mole','paint_mole_grey',               'Talus Grey',        '#888899',  15000, 10);
