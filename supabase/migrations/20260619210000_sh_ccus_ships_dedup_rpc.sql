-- RPC que devuelve nombres de naves deduplicados por capitalización.
-- Para cada grupo de nombres que difieren solo en mayúsculas/minúsculas,
-- devuelve el que tiene más edges (el más representativo del reseed limpio).
create or replace function public.get_sh_ships_json()
returns json
language sql
security definer
stable
as $$
    select json_agg(canonical order by canonical)
    from (
        select distinct on (lower(ship_name))
            ship_name as canonical
        from (
            select from_ship as ship_name, count(*) as n
            from public.sh_ccus group by from_ship
            union all
            select to_ship as ship_name, count(*) as n
            from public.sh_ccus group by to_ship
        ) t
        group by ship_name
        order by lower(ship_name), sum(n) desc
    ) u;
$$;
