-- Add session tracking and body resolution from Game.log
--
-- session_id : server session hex (32 chars) from Channel Connected lines
-- shard      : human-readable shard name (e.g. "pub-sc-alpha-480-11825000")
--
-- body_id and system_id were already present but never populated (OCR was unreliable).
-- Now they are filled from Game.log OOC body name detection.
--
-- Dedup logic update:
--   Same player + same session + within 200 m + within 1 hour = duplicate (skip).
--   Different sessions = allowed even at same coordinates (different server instances).

alter table public.scans
  add column if not exists session_id text,
  add column if not exists shard     text;

comment on column public.scans.session_id is
  'Server session hex from Game.log Channel Connected (32 chars). Identifies the server shard instance.';
comment on column public.scans.shard is
  'Human-readable shard name from Game.log @env_session (e.g. "pub-sc-alpha-480-11825000").';

-- Index for session-based queries
create index if not exists scans_session_idx on public.scans (session_id)
  where session_id is not null;

-- Replace dedup function: same player + same session = duplicate; different sessions = allowed
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
    p_session_id   text,
    p_shard        text,
    p_minerals     jsonb
)
returns jsonb
language plpgsql
security invoker
as $$
declare
    v_dedup_radius_m constant double precision := 200.0;
    v_dedup_window   constant interval         := interval '1 hour';
    v_existing_id    bigint;
    v_new_id         bigint;
    v_mineral        jsonb;
begin
    -- Spatial dedup: same player, same session, same rock
    if p_coord_x is not null
       and p_coord_y is not null
       and p_coord_z is not null
       and p_session_id is not null
    then
        select id into v_existing_id
        from public.scans
        where player_id   = p_player_id
          and session_id  = p_session_id
          and scanned_at >= p_scanned_at - v_dedup_window
          and scanned_at <= p_scanned_at + v_dedup_window
          and coord_x is not null
          and sqrt(
                power(coord_x - p_coord_x, 2) +
                power(coord_y - p_coord_y, 2) +
                power(coord_z - p_coord_z, 2)
              ) <= v_dedup_radius_m
        order by scanned_at desc
        limit 1;

        if v_existing_id is not null then
            return jsonb_build_object('duplicate', true, 'scan_id', v_existing_id);
        end if;
    end if;

    -- Insert scan
    insert into public.scans (
        player_id, scanned_at,
        system_id, body_id, zone, station, altitude_m,
        coord_x, coord_y, coord_z, raw_location,
        session_id, shard
    ) values (
        p_player_id, p_scanned_at,
        p_system_id, p_body_id, p_zone, p_station, p_altitude_m,
        p_coord_x, p_coord_y, p_coord_z, p_raw_location,
        p_session_id, p_shard
    )
    returning id into v_new_id;

    -- Insert minerals
    for v_mineral in select * from jsonb_array_elements(p_minerals) loop
        insert into public.scan_minerals (
            scan_id, mineral_id, name_raw, percent, quality, is_inert
        ) values (
            v_new_id,
            (v_mineral->>'mineral_id')::smallint,
            v_mineral->>'name_raw',
            (v_mineral->>'percent')::real,
            (v_mineral->>'quality')::smallint,
            coalesce((v_mineral->>'is_inert')::boolean, false)
        );
    end loop;

    return jsonb_build_object('duplicate', false, 'scan_id', v_new_id);
end;
$$;

grant execute on function public.insert_scan_dedup(
    uuid, timestamptz, smallint, smallint, text, text, real,
    double precision, double precision, double precision, text,
    text, text, jsonb
) to anon;

-- Drop old signature (no session_id/shard params) now that it's replaced
drop function if exists public.insert_scan_dedup(
    uuid, timestamptz, smallint, smallint, text, text, real,
    double precision, double precision, double precision, text,
    jsonb
);
