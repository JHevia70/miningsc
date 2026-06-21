-- Add station_glb to bodies: per-body GLB override.
-- When set, the starmap uses this model instead of the system-level default.
-- Refinery stations use smap_shubin.glb; rest stops use the system default (everus.glb).

alter table public.bodies
  add column if not exists station_glb text;

-- Stanton refinery stations → smap_shubin.glb
-- (Everus Harbor es rest stop, no refinería)
update public.bodies set station_glb = 'smap_shubin.glb'
where name in (
  'HUR-L1 Green Glade Station', 'HUR-L2 Faithful Dream Station',
  'CRU-L1 Ambitious Dream Station',
  'ARC-L1 Wide Forest Station', 'ARC-L2 Lively Pathway Station', 'ARC-L4 Faint Glen Station',
  'MIC-L1 Shallow Frontier Station', 'MIC-L2 Long Forest Station', 'MIC-L5 Modern Icarus Station'
);
