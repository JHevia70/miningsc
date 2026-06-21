-- Add new_balance to sell_minerals return value for consistent client-side wallet update

create or replace function public.sell_minerals(
  p_player_id   uuid,
  p_station_key text,
  p_mineral     text,
  p_quantity_scu real,
  p_is_refined  boolean
) returns jsonb language plpgsql security definer as $$
declare
  v_location    record;
  v_price_auec  numeric;
  v_total       bigint;
  v_inventory   real;
  v_new_balance bigint;
begin
  -- Verify location exists and has the right capability
  select * into v_location from public.locations where key = p_station_key;
  if not found then
    return jsonb_build_object('error', 'location_not_found');
  end if;

  if p_is_refined = false and not v_location.has_refinery then
    return jsonb_build_object('error', 'no_refinery_at_location');
  end if;

  -- Get best available price for this mineral
  if p_is_refined then
    select price_sell into v_price_auec
      from public.commodity_prices cp
      join public.commodities c on cp.id_commodity = c.id
     where lower(c.name) = lower(p_mineral)
     order by price_sell desc nulls last
     limit 1;
  else
    select price_sell into v_price_auec
      from public.commodity_raw_prices crp
      join public.commodities c on crp.id_commodity = c.id
     where lower(c.name) = lower(p_mineral)
     order by price_sell desc nulls last
     limit 1;
  end if;

  if v_price_auec is null or v_price_auec <= 0 then
    return jsonb_build_object('error', 'no_price_available');
  end if;

  -- Check inventory
  select quantity_scu into v_inventory
    from public.ship_inventory
   where player_id = p_player_id
     and station_key = p_station_key
     and mineral = p_mineral;

  if not found or v_inventory < p_quantity_scu then
    return jsonb_build_object('error', 'insufficient_inventory');
  end if;

  v_total := floor(v_price_auec * p_quantity_scu)::bigint;

  -- Deduct inventory
  update public.ship_inventory
     set quantity_scu = quantity_scu - p_quantity_scu
   where player_id = p_player_id
     and station_key = p_station_key
     and mineral = p_mineral;

  -- Credit aUEC and capture new balance
  update public.players
     set auec = auec + v_total
   where id = p_player_id
  returning auec into v_new_balance;

  return jsonb_build_object(
    'ok',          true,
    'auec_earned', v_total,
    'price_per_scu', v_price_auec,
    'new_balance', v_new_balance
  );
end;
$$;

grant execute on function public.sell_minerals(uuid, text, text, real, boolean) to authenticated;
