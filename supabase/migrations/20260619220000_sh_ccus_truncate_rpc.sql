-- RPC para truncar la tabla sh_ccus (solo invocable por service role)
create or replace function public.truncate_sh_ccus()
returns void
language plpgsql
security definer
as $$
begin
    truncate table public.sh_ccus restart identity;
end;
$$;

-- Solo service role puede invocarla (revocamos acceso a anon/authenticated)
revoke execute on function public.truncate_sh_ccus() from public, anon, authenticated;
grant  execute on function public.truncate_sh_ccus() to service_role;
