-- Deduplica variantes de capitalización en sh_ccus.
-- Para cada grupo (lower(from_ship), lower(to_ship)) mantiene la fila con menor precio
-- y elimina el resto. Los nombres canónicos quedan como los del reseed (ya normalizados).
delete from public.sh_ccus
where id not in (
    select min(id)
    from public.sh_ccus
    group by lower(from_ship), lower(to_ship)
);
