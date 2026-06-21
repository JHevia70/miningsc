-- CRU-L3 does not exist in game — remove from map
DELETE FROM public.bodies WHERE key = 'cru_l3';
