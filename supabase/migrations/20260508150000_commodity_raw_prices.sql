-- Per-terminal sell prices for raw minerals at refineries (synced from UEX /commodities_raw_prices_all)
create table public.commodity_raw_prices (
  id              bigint primary key generated always as identity,
  id_commodity    integer not null references public.commodities(id) on delete cascade,
  id_terminal     integer not null,
  terminal_name   text not null,
  location        text,
  price_sell      integer not null default 0,
  price_sell_avg  integer not null default 0,
  date_modified   timestamptz,
  synced_at       timestamptz not null default now(),
  unique (id_commodity, id_terminal)
);

create index on public.commodity_raw_prices (id_commodity);
create index on public.commodity_raw_prices (price_sell desc);

alter table public.commodity_raw_prices enable row level security;
create policy "public read" on public.commodity_raw_prices for select using (true);
grant select on public.commodity_raw_prices to anon, authenticated;
