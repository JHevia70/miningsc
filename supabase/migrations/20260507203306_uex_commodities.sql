-- UEX commodity price data
-- Raw minerals (is_raw=1) have id_parent pointing to the refined version
-- price_sell on raw = sell price at terminals, price_sell on refined = refined sell price

create table public.commodities (
  id              integer primary key,   -- UEX id
  id_parent       integer,               -- UEX id of refined counterpart (for raw) or raw counterpart (for refined)
  mineral_id      smallint references public.minerals(id),
  name            text not null,
  code            text,
  kind            text,                  -- "Metal", "Mineral", etc.
  is_raw          boolean not null default false,
  is_refined      boolean not null default false,
  is_refinable    boolean not null default false,
  price_buy       integer not null default 0,   -- aUEC
  price_sell      integer not null default 0,   -- aUEC
  is_available    boolean not null default false,
  wiki            text,
  uex_updated_at  timestamptz,
  synced_at       timestamptz not null default now()
);

create index on public.commodities (mineral_id);
create index on public.commodities (is_raw);
create index on public.commodities (is_refined);
create index on public.commodities (code);

alter table public.commodities enable row level security;
create policy "public read" on public.commodities for select using (true);

-- Also extend systems and bodies tables with UEX ids for sync
alter table public.systems add column if not exists uex_id integer unique;
alter table public.bodies  add column if not exists uex_id integer unique;
