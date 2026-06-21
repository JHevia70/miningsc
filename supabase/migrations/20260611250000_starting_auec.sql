-- Give new players 20,000 aUEC as starting funds.
-- Also top-up existing players who currently have 0 (never earned anything yet).

-- 1. Update the trigger function to set auec = 20000 on account creation
create or replace function public.on_player_created()
returns trigger language plpgsql security definer as $$
begin
  -- Grant starting ship
  insert into public.player_ships (player_id, ship_type)
  values (new.id, 'prospector')
  on conflict do nothing;

  -- Grant starting funds
  update public.players set auec = 20000 where id = new.id and auec = 0;

  return new;
end;
$$;

-- 2. Top-up existing players who still have 0 aUEC
update public.players set auec = 20000 where auec = 0;
