-- Deduplication RPC for scan uploads
--
-- insert_scan_dedup() replaces direct INSERT on scans + scan_minerals.
-- Before inserting, it checks if any scan exists within DEDUP_RADIUS_M metres
-- and DEDUP_WINDOW_INTERVAL of the new scan's timestamp (across all players).
-- If a duplicate is found, returns the existing scan id with duplicate=true.
-- If no duplicate, inserts the scan and its minerals, returns new id with duplicate=false.
--
-- Called by the overlay uploader instead of direct table inserts.

create or replace function public.insert_scan_dedup(
    p_player_id    uuid,
    p_scanned_at   timestamptz,
    p_system_id    smallint,
    p_body_id      smallint,
    p_zone         text,
    p_station      text,
    p_altitude_m   real,
    p_coord_x      double precision,
    p_coord_y      double precision,
    p_coord_z      double precision,
    p_raw_location text,
    p_minerals     jsonb   -- array of {mineral_id, name_raw, percent, quality, is_inert}
)
returns jsonb
language plpgsql
security invoker
as $$
declare
    v_dedup_radius_m     constant double precision := 200.0;
    v_dedup_window       constant interval         := interval '1 hour';
    v_existing_scan_id   bigint;
    v_new_scan_id        bigint;
    v_mineral            jsonb;
begin
    -- Only attempt spatial dedup when coordinates are available
    if p_coord_x is not null and p_coord_y is not null and p_coord_z is not null then
        select id into v_existing_scan_id
        from public.scans
        where scanned_at >= p_scanned_at - v_dedup_window
          and scanned_at <= p_scanned_at + v_dedup_window
          and coord_x is not null
          and sqrt(
                power(coord_x - p_coord_x, 2) +
                power(coord_y - p_coord_y, 2) +
                power(coord_z - p_coord_z, 2)
              ) <= v_dedup_radius_m
        order by scanned_at desc
        limit 1;

        if v_existing_scan_id is not null then
            return jsonb_build_object(
                'duplicate',  true,
                'scan_id',    v_existing_scan_id
            );
        end if;
    end if;

    -- Insert scan
    insert into public.scans (
        player_id, scanned_at, system_id, body_id, zone,
        station, altitude_m, coord_x, coord_y, coord_z, raw_location
    ) values (
        p_player_id, p_scanned_at, p_system_id, p_body_id, p_zone,
        p_station, p_altitude_m, p_coord_x, p_coord_y, p_coord_z, p_raw_location
    )
    returning id into v_new_scan_id;

    -- Insert minerals
    for v_mineral in select * from jsonb_array_elements(p_minerals) loop
        insert into public.scan_minerals (
            scan_id, mineral_id, name_raw, percent, quality, is_inert
        ) values (
            v_new_scan_id,
            (v_mineral->>'mineral_id')::smallint,
            v_mineral->>'name_raw',
            (v_mineral->>'percent')::real,
            (v_mineral->>'quality')::smallint,
            coalesce((v_mineral->>'is_inert')::boolean, false)
        );
    end loop;

    return jsonb_build_object(
        'duplicate', false,
        'scan_id',   v_new_scan_id
    );
end;
$$;

-- Allow anon (overlay) to call this function
grant execute on function public.insert_scan_dedup to anon;

comment on function public.insert_scan_dedup is
    'Insert a scan with deduplication: skips insert if a scan exists within 500 m and 1 hour window (all players). Returns {duplicate: bool, scan_id: bigint}.';
