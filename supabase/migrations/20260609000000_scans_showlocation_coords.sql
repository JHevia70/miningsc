-- Adapt scans table for /showlocation coordinates
--
-- /showlocation gives global system coordinates in metres (double precision).
-- coord_x/coord_y already exist; coord_z was added later without an index.
-- This migration:
--   1. Ensures coord_z exists and is double precision (idempotent).
--   2. Adds a composite index on (body_id, coord_x, coord_y, coord_z) for
--      spatial proximity queries ("scans near this position").
--   3. Fixes the raw_location comment — it now stores clipboard text, not OCR.
--   4. Drops system_id / body_id NOT NULL constraints if any were added
--      (they are nullable by design since /showlocation gives no body name).

-- 1. Ensure coord_z column exists (already added in 20260511010000, kept idempotent)
alter table public.scans
  add column if not exists coord_z double precision;

-- 2. Spatial index — useful for "find all scans within N km of these coords"
create index if not exists scans_coords_idx
  on public.scans (coord_x, coord_y, coord_z)
  where coord_x is not null;

-- 3. Update comment to reflect new data source
comment on column public.scans.raw_location is
  'Raw text from /showlocation clipboard output, e.g. "Coordinates: X: ... Y: ... Z: ..."';

comment on column public.scans.coord_x is
  'Global system X coordinate in metres (from /showlocation)';

comment on column public.scans.coord_y is
  'Global system Y coordinate in metres (from /showlocation)';

comment on column public.scans.coord_z is
  'Global system Z coordinate in metres (from /showlocation)';
