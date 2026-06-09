-- Add missing bodies and extend scans with zone field
-- for map pinpointing and zone statistics.

-- -----------------------------------------------------------------------
-- Missing bodies
-- -----------------------------------------------------------------------

-- Stanton: asteroid belt
insert into public.bodies (system_id, name, type)
select s.id, b.name, b.type
from public.systems s,
     (values
       ('Aaron Halo', 'asteroid_belt'),
       ('Lyria',      'moon'),
       ('Clio',       'moon')
     ) as b(name, type)
where s.name = 'Stanton'
on conflict (system_id, name) do nothing;

-- Nyx system
insert into public.systems (name)
values ('Nyx')
on conflict (name) do nothing;

insert into public.bodies (system_id, name, type)
select s.id, 'Delamar', 'moon'
from public.systems s
where s.name = 'Nyx'
on conflict (system_id, name) do nothing;

-- Pyro: fix/add bodies that may be missing
insert into public.bodies (system_id, name, type)
select s.id, b.name, b.type
from public.systems s,
     (values
       ('Pyro III',  'planet'),
       ('Pyro V',    'planet'),
       ('Ignis',     'moon'),
       ('Vuur',      'moon')
     ) as b(name, type)
where s.name = 'Pyro'
on conflict (system_id, name) do nothing;

-- -----------------------------------------------------------------------
-- Extend scans: zone tag for map filtering
-- -----------------------------------------------------------------------

alter table public.scans
  add column if not exists zone text;   -- biome zone tag e.g. "acidic", "ice", "desert"

comment on column public.scans.zone is
  'Biome zone tag at scan location (acidic, ice, desert, crystaline, etc.)';

-- Index for zone-based statistics queries
create index if not exists scans_body_zone_idx on public.scans (body_id, zone);
