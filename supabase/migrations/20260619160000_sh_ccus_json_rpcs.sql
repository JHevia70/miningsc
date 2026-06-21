-- RPCs que devuelven JSON completo, sin límite de filas de PostgREST
create or replace function public.get_sh_ships_json()
returns json
language sql
security definer
stable
as $$
    select json_agg(ship_name order by ship_name)
    from (
        select distinct ship_name
        from (
            select from_ship as ship_name from public.sh_ccus
            union
            select to_ship   as ship_name from public.sh_ccus
        ) t
    ) u;
$$;

create or replace function public.get_sh_ccus_json()
returns json
language sql
security definer
stable
as $$
    select json_agg(row_to_json(c))
    from (select from_ship, to_ship, price, scraped_at from public.sh_ccus) c;
$$;

grant execute on function public.get_sh_ships_json() to anon, authenticated;
grant execute on function public.get_sh_ccus_json()  to anon, authenticated;
