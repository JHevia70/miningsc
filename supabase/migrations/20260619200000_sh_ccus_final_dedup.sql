-- Elimina todas las filas cuyo (from_ship, to_ship) no coincide exactamente
-- con los nombres del reseed limpio (sh_ccus_clean.json).
-- Primero borra duplicados de capitalización, luego los nombres sucios restantes.

-- Paso 1: para cada par (lower, lower) que tiene más de una fila,
-- conservar solo el que tiene el precio más bajo (que es el del reseed limpio).
delete from public.sh_ccus a
using public.sh_ccus b
where lower(a.from_ship) = lower(b.from_ship)
  and lower(a.to_ship)   = lower(b.to_ship)
  and a.id > b.id;

-- Paso 2: eliminar filas con nombres que contienen el patrón sucio original
-- '" UPGRADE "' (comillas tipográficas dentro del nombre)
delete from public.sh_ccus
where from_ship like '%"%" UPGRADE %"%"%'
   or to_ship   like '%"%" UPGRADE %"%"%'
   or from_ship like '%" UPGRADE "%'
   or to_ship   like '%" UPGRADE "%';
