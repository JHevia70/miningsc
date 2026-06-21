-- Fix RLS for simulator tables.
--
-- Root cause: mining_operations.player_id (and other simulator tables) reference
-- players(id), which is a gen_random_uuid() different from auth.uid().
-- All existing RLS policies compared player_id = auth.uid() which is wrong.
--
-- Fix: add a stable helper function my_player_id() that returns players.id
-- for the current auth user, then rebuild all simulator RLS policies to use it.

create or replace function public.my_player_id()
returns uuid language sql stable security definer as $$
  select id from public.players where auth_id = auth.uid() limit 1;
$$;

-- ── mining_operations ─────────────────────────────────────────────────────────
drop policy if exists "players manage own operations" on public.mining_operations;
create policy "players manage own operations"
  on public.mining_operations for all
  using  (player_id = public.my_player_id())
  with check (player_id = public.my_player_id());

-- ── ship_inventory ────────────────────────────────────────────────────────────
drop policy if exists "players manage own inventory" on public.ship_inventory;
create policy "players manage own inventory"
  on public.ship_inventory for all
  using  (player_id = public.my_player_id())
  with check (player_id = public.my_player_id());

-- ── player_inventory ──────────────────────────────────────────────────────────
drop policy if exists "anon insert inventory" on public.player_inventory;
drop policy if exists "own inventory"         on public.player_inventory;
drop policy if exists "players manage own player_inventory" on public.player_inventory;
create policy "players manage own player_inventory"
  on public.player_inventory for all
  using  (player_id = public.my_player_id())
  with check (player_id = public.my_player_id());

-- ── ship_loadout ──────────────────────────────────────────────────────────────
drop policy if exists "anon insert loadout" on public.ship_loadout;
drop policy if exists "own loadout"         on public.ship_loadout;
drop policy if exists "players manage own loadout" on public.ship_loadout;
create policy "players manage own loadout"
  on public.ship_loadout for all
  using  (player_id = public.my_player_id())
  with check (player_id = public.my_player_id());

-- ── player_ships ──────────────────────────────────────────────────────────────
drop policy if exists "own ships"              on public.player_ships;
drop policy if exists "players manage own ships" on public.player_ships;
create policy "players manage own ships"
  on public.player_ships for all
  using  (player_id = public.my_player_id())
  with check (player_id = public.my_player_id());

-- ── player_liveries ───────────────────────────────────────────────────────────
drop policy if exists "own liveries"              on public.player_liveries;
drop policy if exists "players manage own liveries" on public.player_liveries;
create policy "players manage own liveries"
  on public.player_liveries for all
  using  (player_id = public.my_player_id())
  with check (player_id = public.my_player_id());

-- ── refinery_queue ────────────────────────────────────────────────────────────
drop policy if exists "anon insert refinery"      on public.refinery_queue;
drop policy if exists "own refinery"              on public.refinery_queue;
drop policy if exists "players manage own refinery" on public.refinery_queue;
create policy "players manage own refinery"
  on public.refinery_queue for all
  using  (player_id = public.my_player_id())
  with check (player_id = public.my_player_id());

-- ── players (select own row) ──────────────────────────────────────────────────
drop policy if exists "select own player" on public.players;
drop policy if exists "update own player" on public.players;
create policy "select own player" on public.players
  for select using (auth_id = auth.uid());
create policy "update own player" on public.players
  for update using (auth_id = auth.uid());
