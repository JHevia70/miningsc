-- Star Hangar CCU price graph
-- Stores one row per (from_ship, to_ship) pair with the best (lowest) price seen.

create table if not exists public.sh_ccus (
    id          bigint generated always as identity primary key,
    from_ship   text not null,
    to_ship     text not null,
    price       numeric(10,2) not null,
    scraped_at  timestamptz not null,
    constraint sh_ccus_pair unique (from_ship, to_ship)
);

create index if not exists sh_ccus_from_idx on public.sh_ccus (from_ship);
create index if not exists sh_ccus_to_idx   on public.sh_ccus (to_ship);

-- Public read, writes only via service role (sync-sh edge function)
alter table public.sh_ccus enable row level security;
create policy "public read" on public.sh_ccus for select using (true);

comment on table public.sh_ccus is
    'Star Hangar CCU price graph. One row per (from_ship, to_ship) with the cheapest price seen. Populated by the sync-sh edge function.';
