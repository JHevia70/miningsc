-- Vista de naves únicas para el selector del optimizador de CCUs
create or replace view public.sh_ships as
select distinct ship_name
from (
    select from_ship as ship_name from public.sh_ccus
    union
    select to_ship   as ship_name from public.sh_ccus
) t
order by ship_name;

-- RPC para obtener todas las edges (supera el límite de 1000 filas de PostgREST)
create or replace function public.get_sh_ccus()
returns table(from_ship text, to_ship text, price numeric, scraped_at timestamptz)
language sql
security definer
stable
as $$
    select from_ship, to_ship, price, scraped_at from public.sh_ccus;
$$;

grant select on public.sh_ships to anon, authenticated;
grant execute on function public.get_sh_ccus() to anon, authenticated;
