-- Table: celestial_bodies
-- Stores all star systems, planets, moons, stations and belts with their
-- real in-game orbital positions captured from the in-game starmap.

create type body_type as enum (
  'star', 'planet', 'gas_giant', 'moon', 'dwarf_planet',
  'asteroid_belt', 'station'
);

create table public.celestial_bodies (
  id                 serial          primary key,
  key                text            not null unique,
  name               text            not null,
  type               body_type       not null,
  system             text            not null,
  parent_key         text            references public.celestial_bodies(key) on delete set null,
  orbital_radius_km  double precision not null default 0,
  angle_deg          double precision,
  body_radius_km     double precision not null default 1,
  color              text,
  texture            text,
  updated_at         timestamptz     not null default now()
);

create index on public.celestial_bodies (system);
create index on public.celestial_bodies (parent_key);

alter table public.celestial_bodies enable row level security;
create policy "public read" on public.celestial_bodies
  for select using (true);

comment on table public.celestial_bodies is
  'All celestial bodies and stations across Stanton, Pyro and Nyx with real in-game orbital positions.';
comment on column public.celestial_bodies.orbital_radius_km is
  'Distance from parent body in km. For star children this is distance from the star.';
comment on column public.celestial_bodies.angle_deg is
  'Fixed placement angle in degrees (in-game longitude). NULL = dynamic orbit.';
