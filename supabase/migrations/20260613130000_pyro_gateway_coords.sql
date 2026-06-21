-- Pyro Gateway: lat_deg (-5.42°), angle_deg (-83.25°), orbital_radius_km (28300000 km = 28.30 Gm)
UPDATE public.bodies
SET lat_deg = -5.42, angle_deg = -83.25, orbital_radius_km = 28300000
WHERE key = 'pyro_gateway';
