-- Add lat_deg: latitude above the orbital plane (in-game starmap coordinate).
-- Used for inclined objects like Pyro Gateway (-5.42°) and Nyx Gateway (16.88°).

alter table public.celestial_bodies
  add column if not exists lat_deg double precision;

comment on column public.celestial_bodies.lat_deg is
  'Latitude above the orbital plane in degrees (in-game starmap). NULL = on the plane.';
