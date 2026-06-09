-- Add Z coordinate to scans for full 3D position storage
alter table public.scans
  add column if not exists coord_z double precision;
