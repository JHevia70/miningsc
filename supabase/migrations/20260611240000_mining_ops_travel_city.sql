-- Support travel to cities (ship dealer, etc.) in the mining state machine.
-- A "city trip" is traveling_out with no mineral — arrives → docked at destination city.

-- Add destination_type to distinguish mining trips from city travel
alter table public.mining_operations
  add column if not exists destination_type text not null default 'body'
    check (destination_type in ('body', 'city'));

-- destination_key holds the city location key when destination_type = 'city'
alter table public.mining_operations
  add column if not exists destination_key text references public.locations(key) on update cascade;

-- Update complete_mining_run to also handle city arrivals (no-op for city trips — handled client-side)
-- No SQL change needed: client advances city trips directly via update, not via RPC.

-- Grant authenticated role to update station_key (needed when arriving at city)
-- (already granted via RLS "players manage own ops" if it exists)
