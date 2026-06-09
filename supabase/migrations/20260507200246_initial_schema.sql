-- SC Mining Database Schema

-- -----------------------------------------------------------------------
-- Reference tables (static game data)
-- -----------------------------------------------------------------------

create table public.systems (
  id   smallint primary key generated always as identity,
  name text not null unique   -- e.g. "Stanton", "Pyro"
);

create table public.bodies (
  id        smallint primary key generated always as identity,
  system_id smallint not null references public.systems(id),
  name      text not null,    -- e.g. "Hurston", "microTech", "Yela"
  type      text not null,    -- "planet" | "moon" | "asteroid_belt" | "station"
  unique (system_id, name)
);

create table public.minerals (
  id   smallint primary key generated always as identity,
  name text not null unique   -- e.g. "QUANTANIUM", "AGRICIUM"
);

-- -----------------------------------------------------------------------
-- Players (anonymous — identified by UUID stored in overlay config)
-- -----------------------------------------------------------------------

create table public.players (
  id         uuid primary key default gen_random_uuid(),
  handle     text,
  created_at timestamptz not null default now()
);

-- -----------------------------------------------------------------------
-- Scans — one row per F9 press that found a panel
-- -----------------------------------------------------------------------

create table public.scans (
  id          bigint primary key generated always as identity,
  player_id   uuid references public.players(id),
  scanned_at  timestamptz not null default now(),

  system_id   smallint references public.systems(id),
  body_id     smallint references public.bodies(id),
  station     text,
  altitude_m  real,
  coord_x     double precision,
  coord_y     double precision,

  raw_location text   -- full OCR text for debugging / re-parsing
);

-- -----------------------------------------------------------------------
-- Scan lines — one row per mineral in a scan
-- -----------------------------------------------------------------------

create table public.scan_minerals (
  id         bigint primary key generated always as identity,
  scan_id    bigint not null references public.scans(id) on delete cascade,
  mineral_id smallint references public.minerals(id),
  name_raw   text,
  percent    real not null,
  quality    smallint,
  is_inert   boolean not null default false
);

-- -----------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------

create index on public.scans (body_id);
create index on public.scans (system_id);
create index on public.scans (scanned_at desc);
create index on public.scan_minerals (scan_id);
create index on public.scan_minerals (mineral_id);

-- -----------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------

alter table public.systems       enable row level security;
alter table public.bodies        enable row level security;
alter table public.minerals      enable row level security;
alter table public.players       enable row level security;
alter table public.scans         enable row level security;
alter table public.scan_minerals enable row level security;

create policy "public read" on public.systems       for select using (true);
create policy "public read" on public.bodies        for select using (true);
create policy "public read" on public.minerals      for select using (true);
create policy "public read" on public.scans         for select using (true);
create policy "public read" on public.scan_minerals for select using (true);

create policy "own player" on public.players
  for select using (id = (current_setting('request.jwt.claims', true)::json->>'sub')::uuid);

create policy "insert scan"    on public.scans         for insert with check (true);
create policy "insert mineral" on public.scan_minerals for insert with check (true);
create policy "insert player"  on public.players       for insert with check (true);

-- -----------------------------------------------------------------------
-- Seed: known Star Citizen systems and bodies
-- -----------------------------------------------------------------------

insert into public.systems (name) values ('Stanton'), ('Pyro');

insert into public.bodies (system_id, name, type) values
  (1, 'Hurston',   'planet'),
  (1, 'Crusader',  'planet'),
  (1, 'ArcCorp',   'planet'),
  (1, 'microTech', 'planet'),
  (1, 'Aberdeen',  'moon'),
  (1, 'Magda',     'moon'),
  (1, 'Ita',       'moon'),
  (1, 'Wala',      'moon'),
  (1, 'Cellin',    'moon'),
  (1, 'Daymar',    'moon'),
  (1, 'Yela',      'moon'),
  (1, 'Euterpe',   'moon'),
  (1, 'Calliope',  'moon'),
  (1, 'Clio',      'moon'),
  (2, 'Pyro I',    'planet'),
  (2, 'Bloom',     'planet'),
  (2, 'Monox',     'planet'),
  (2, 'Fuego',     'planet'),
  (2, 'Adir',      'planet'),
  (2, 'Terminus',  'planet');

insert into public.minerals (name) values
  ('QUANTANIUM'), ('AGRICIUM'),  ('LARANITE'),  ('TARANITE'),
  ('BEXALITE'),   ('BORASE'),    ('RICCITE'),   ('BERYL'),
  ('STILERON'),   ('TITANIUM'),  ('CORUNDUM'),  ('QUARTZ'),
  ('IRON'),       ('COPPER'),    ('TUNGSTEN'),  ('DIAMOND'),
  ('GOLD'),       ('HADANITE'),  ('JANALITE'),  ('OURATITE'),
  ('FELSIC'),     ('APHORITE'),  ('DOLOMITE');
