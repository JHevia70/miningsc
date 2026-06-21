-- Add station_glb to systems: GLB filename (under /ships/) used for all stations in that system.
-- null = use generic cross+hex icon until a model is available.

alter table public.systems
  add column if not exists station_glb text;

-- Stanton uses the util-ring-spike model (Everus Harbor style)
update public.systems set station_glb = 'everus.glb' where name = 'Stanton';
-- Pyro and Nyx: null for now, will be updated when models are ready
