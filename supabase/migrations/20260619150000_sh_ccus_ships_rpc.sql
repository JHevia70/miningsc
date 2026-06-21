-- RPC para lista de naves únicas (evita el límite de filas de PostgREST)
create or replace function public.get_sh_ships()
returns table(ship_name text)
language sql
security definer
stable
as $$
    select distinct ship_name
    from (
        select from_ship as ship_name from public.sh_ccus
        union
        select to_ship   as ship_name from public.sh_ccus
    ) t
    order by ship_name;
$$;

grant execute on function public.get_sh_ships() to anon, authenticated;
