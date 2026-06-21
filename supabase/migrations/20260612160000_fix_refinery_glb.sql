-- Corrige los station_glb de refinerías en Stanton.
-- Everus Harbor es un rest stop (no refinería) → sin smap_shubin.glb.
-- HUR-L1 sí tiene refinería pero faltaba el glb.

update public.bodies set station_glb = null
where key = 'everus';

update public.bodies set station_glb = 'smap_shubin.glb'
where key = 'hur_l1';
