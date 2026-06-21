-- Terra Gateway: correct lat_deg (-4.82°), angle_deg (-5.88°), orbital_radius_km (51570000 km = 51.57 Gm)
UPDATE public.bodies
SET lat_deg = -4.82, angle_deg = -5.88, orbital_radius_km = 51570000
WHERE key = 'terra_gateway';
