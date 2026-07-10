-- Network latency monitoring: captured game server IPs + Globalping measurements
--
-- Star Citizen game servers (Google Cloud) block ICMP/TCP/HTTP entirely except
-- their own game UDP port, confirmed by manual testing. Measurements target the
-- last reachable hop toward the server's Google Cloud edge (via mtr over TCP),
-- not the game host itself. See CLAUDE.md / project notes for details.

-- -----------------------------------------------------------------------
-- game_server_ips — catalog of server IPs observed via Game.log during play
-- -----------------------------------------------------------------------

create table public.game_server_ips (
  id             bigint primary key generated always as identity,
  ip             text not null unique,
  system_id      smallint references public.systems(id),
  body_id        smallint references public.bodies(id),
  shard          text,
  session_id     text,
  contributed_by uuid references public.players(id),
  first_seen     timestamptz not null default now(),
  last_seen      timestamptz not null default now(),
  active         boolean not null default true
);

comment on column public.game_server_ips.active is
  'Flagged false by the network runner once an IP has not been seen recently, to stop polling it.';

-- -----------------------------------------------------------------------
-- ping_results — one row per probe-country measurement round
-- -----------------------------------------------------------------------

create table public.ping_results (
  id              bigint primary key generated always as identity,
  server_ip_id    bigint not null references public.game_server_ips(id) on delete cascade,
  probe_country   text not null,
  probe_city      text,
  hop_address     text,
  hop_index       integer,
  rtt_min_ms      real,
  rtt_avg_ms      real,
  rtt_max_ms      real,
  packet_loss_pct real,
  measured_at     timestamptz not null default now()
);

comment on column public.ping_results.hop_address is
  'IP of the last reachable hop toward the game server (Google Cloud edge), not the game host itself — the host blocks all measurable protocols.';
comment on column public.ping_results.hop_index is
  'Position of the measured hop in the traced route, so a route change between measurements can be detected.';

-- -----------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------

create index on public.game_server_ips (active) where active;
create index on public.game_server_ips (last_seen desc);

create index on public.ping_results (server_ip_id, measured_at desc);
create index on public.ping_results (probe_country, measured_at desc);

-- -----------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------

alter table public.game_server_ips enable row level security;
alter table public.ping_results    enable row level security;

create policy "public read" on public.game_server_ips for select using (true);
create policy "insert game_server_ips" on public.game_server_ips for insert with check (true);
create policy "upsert game_server_ips" on public.game_server_ips for update using (true) with check (true);

create policy "public read" on public.ping_results for select using (true);
create policy "insert ping_results" on public.ping_results for insert with check (true);
