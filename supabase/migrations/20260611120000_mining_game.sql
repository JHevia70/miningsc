-- Mining idle game: operations + inventory
-- Operations are public (all players see each other's ships on the starmap)

-- ── mining_operations ─────────────────────────────────────────────────────────
create type public.mining_op_state as enum (
  'docked',           -- at station, idle or loading
  'traveling_out',    -- heading to mining site
  'mining',           -- on site, extracting
  'traveling_back'    -- returning to station
);

create table public.mining_operations (
  id                bigint generated always as identity primary key,
  player_id         uuid        not null references public.players(id) on delete cascade,
  ship_type         text        not null check (ship_type in ('prospector', 'mole')),

  -- Selected mission parameters
  mineral           text        not null,
  system            text        not null default 'Stanton',
  body              text        not null,          -- planet/moon where the spawn is
  station_key       text        not null,          -- home station (refinery)

  -- State machine
  state             public.mining_op_state not null default 'docked',
  state_changed_at  timestamptz not null default now(),
  arrives_at        timestamptz,                   -- ETA for current leg (null when docked/mining completes)

  -- Position interpolation (scene units, from StarmapClient scale)
  origin_x          real,
  origin_y          real,
  origin_z          real,
  dest_x            real,
  dest_y            real,
  dest_z            real,

  -- Cargo
  cargo_scu         real        not null default 0,
  cargo_max_scu     real        not null default 32,  -- prospector=32, mole=96

  -- Health / fuel (0–100)
  hull_pct          real        not null default 100 check (hull_pct between 0 and 100),
  fuel_pct          real        not null default 100 check (fuel_pct between 0 and 100),

  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- One active operation per ship type per player
create unique index mining_ops_one_per_ship
  on public.mining_operations (player_id, ship_type);

-- Public read (all players see all ships)
alter table public.mining_operations enable row level security;

create policy "anyone can view operations"
  on public.mining_operations for select
  using (true);

create policy "players manage own operations"
  on public.mining_operations for all
  using  (auth.uid() = player_id)
  with check (auth.uid() = player_id);

-- ── ship_inventory ─────────────────────────────────────────────────────────────
-- Accumulated mineral at each station per player
create table public.ship_inventory (
  id            bigint generated always as identity primary key,
  player_id     uuid    not null references public.players(id) on delete cascade,
  station_key   text    not null,
  mineral       text    not null,
  quantity_scu  real    not null default 0 check (quantity_scu >= 0),
  updated_at    timestamptz not null default now(),

  unique (player_id, station_key, mineral)
);

alter table public.ship_inventory enable row level security;

create policy "anyone can view inventory"
  on public.ship_inventory for select
  using (true);

create policy "players manage own inventory"
  on public.ship_inventory for all
  using  (auth.uid() = player_id)
  with check (auth.uid() = player_id);

-- ── updated_at trigger ────────────────────────────────────────────────────────
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger mining_ops_updated_at
  before update on public.mining_operations
  for each row execute function public.set_updated_at();

create trigger ship_inventory_updated_at
  before update on public.ship_inventory
  for each row execute function public.set_updated_at();

-- ── complete_mining_run RPC ───────────────────────────────────────────────────
-- Called by client when a ship arrives back at station.
-- Atomically: credits inventory + resets operation to docked.
create or replace function public.complete_mining_run(
  p_operation_id  bigint,
  p_mineral       text,
  p_station_key   text,
  p_quantity_scu  real
) returns void
language plpgsql security definer as $$
declare
  v_player_id uuid;
begin
  -- Verify ownership
  select player_id into v_player_id
    from public.mining_operations
   where id = p_operation_id and auth.uid() = player_id;

  if not found then
    raise exception 'operation not found or not owned by caller';
  end if;

  -- Credit inventory
  insert into public.ship_inventory (player_id, station_key, mineral, quantity_scu)
    values (v_player_id, p_station_key, p_mineral, p_quantity_scu)
  on conflict (player_id, station_key, mineral)
    do update set quantity_scu = ship_inventory.quantity_scu + excluded.quantity_scu;

  -- Reset ship to docked
  update public.mining_operations
     set state          = 'docked',
         state_changed_at = now(),
         arrives_at     = null,
         cargo_scu      = 0,
         fuel_pct       = greatest(fuel_pct - (10 + random() * 10), 0)
   where id = p_operation_id;
end;
$$;

grant execute on function public.complete_mining_run to authenticated;

-- ── Realtime ──────────────────────────────────────────────────────────────────
alter publication supabase_realtime add table public.mining_operations;
