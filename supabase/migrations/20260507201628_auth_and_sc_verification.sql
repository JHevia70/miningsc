-- Extend players table with auth and SC handle verification

alter table public.players
  add column if not exists auth_id     uuid unique references auth.users(id) on delete cascade,
  add column if not exists sc_handle   text unique,
  add column if not exists sc_verified boolean not null default false,
  add column if not exists verify_code text;

-- Index for fast lookup by auth_id and sc_handle
create index if not exists players_auth_id_idx   on public.players (auth_id);
create index if not exists players_sc_handle_idx on public.players (sc_handle);

-- Auto-create a player row when a new auth user signs up
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.players (auth_id)
  values (new.id)
  on conflict (auth_id) do nothing;
  return new;
end;
$$;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_auth_user();

-- Update RLS policies for players
drop policy if exists "own player"  on public.players;
drop policy if exists "insert player" on public.players;

-- Authenticated users can read and update their own player row
create policy "select own player" on public.players
  for select using (auth_id = auth.uid());

create policy "update own player" on public.players
  for update using (auth_id = auth.uid());

-- Allow overlay (anon) to insert players with a pre-generated UUID (no auth)
create policy "anon insert player" on public.players
  for insert with check (auth_id is null);

-- Scans: authenticated users and anon overlay can both insert
drop policy if exists "insert scan" on public.scans;
create policy "insert scan" on public.scans
  for insert with check (true);

-- Function to generate SC verification code (called from web)
create or replace function public.generate_sc_verify_code(p_sc_handle text)
returns text
language plpgsql
security definer set search_path = ''
as $$
declare
  v_code text;
  v_player_id uuid;
begin
  -- Only authenticated users can request a code
  if auth.uid() is null then
    raise exception 'Not authenticated';
  end if;

  -- Check handle not already taken by another verified user
  if exists (
    select 1 from public.players
    where sc_handle = p_sc_handle
      and sc_verified = true
      and auth_id != auth.uid()
  ) then
    raise exception 'Handle already verified by another account';
  end if;

  -- Generate code: SCMINE-XXXXXX
  v_code := 'SCMINE-' || upper(substring(encode(gen_random_bytes(4), 'hex') from 1 for 6));

  -- Update player row
  update public.players
  set sc_handle   = p_sc_handle,
      verify_code = v_code,
      sc_verified = false
  where auth_id = auth.uid()
  returning id into v_player_id;

  return v_code;
end;
$$;

-- Function to verify SC handle (called from web after user pastes code in RSI bio)
create or replace function public.verify_sc_handle()
returns boolean
language plpgsql
security definer set search_path = ''
as $$
declare
  v_handle    text;
  v_code      text;
  v_bio       text;
begin
  if auth.uid() is null then
    raise exception 'Not authenticated';
  end if;

  select sc_handle, verify_code
  into v_handle, v_code
  from public.players
  where auth_id = auth.uid();

  if v_handle is null or v_code is null then
    raise exception 'No pending verification';
  end if;

  -- Scraping is done by the web backend (Edge Function) which calls this
  -- function with the bio text. Here we just record the result.
  -- The actual HTTP fetch happens in the Edge Function verify-sc-handle.
  return false; -- placeholder: real logic in Edge Function
end;
$$;
