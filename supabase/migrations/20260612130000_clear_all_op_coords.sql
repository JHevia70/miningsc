-- Invalidate all stored scene coords: scene scale changed ×20.
-- Coords stored before this migration are in the old scale and will place ships
-- in wrong positions. Setting to NULL forces recalculation from station_key.
UPDATE mining_operations
SET origin_x = NULL, origin_y = NULL, origin_z = NULL,
    dest_x   = NULL, dest_y   = NULL, dest_z   = NULL;
