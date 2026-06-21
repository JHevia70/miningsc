-- Clear stale scene coordinates from city-travel operations.
-- These were saved with planet-centre coords (bug). Setting them to NULL
-- forces the client to recalculate from station_key on next render.
-- New operations launched after this migration will save correct coords.
UPDATE mining_operations
SET origin_x = NULL, origin_y = NULL, origin_z = NULL,
    dest_x   = NULL, dest_y   = NULL, dest_z   = NULL
WHERE destination_type = 'city'
   OR (destination_type IS NULL AND mineral = '');
