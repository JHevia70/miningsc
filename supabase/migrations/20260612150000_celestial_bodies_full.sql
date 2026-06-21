-- Migrate all orbital data from orbital-data.ts to the database.
-- Adds missing columns to bodies and systems, seeds all bodies, and creates jump_points table.

-- ── bodies: add orbital columns ──────────────────────────────────────────────
alter table public.bodies
  add column if not exists key               text unique,
  add column if not exists orbital_radius_km double precision not null default 0,
  add column if not exists body_radius_km    double precision not null default 1,
  add column if not exists color             text not null default '#aaaaaa',
  add column if not exists texture           text,
  add column if not exists angle_deg         double precision,
  add column if not exists lat_deg           double precision,
  add column if not exists parent_key        text;
  -- station_glb already added in 20260612140000

-- ── systems: add galactic position ───────────────────────────────────────────
alter table public.systems
  add column if not exists pos_x double precision not null default 0,
  add column if not exists pos_y double precision not null default 0,
  add column if not exists pos_z double precision not null default 0;

update public.systems set pos_x =   0,     pos_y =  0,     pos_z =  0     where name = 'Stanton';
update public.systems set pos_x =  -9.40,  pos_y = 11.05,  pos_z = -33.70 where name = 'Pyro';
update public.systems set pos_x = -29.53,  pos_y = 11.05,  pos_z = -33.70 where name = 'Nyx';

-- ── jump_points ───────────────────────────────────────────────────────────────
create table if not exists public.jump_points (
  id         smallint primary key generated always as identity,
  from_system text not null,
  to_system   text not null,
  name        text,
  unique (from_system, to_system)
);

insert into public.jump_points (from_system, to_system, name) values
  ('Stanton', 'Pyro', 'Stanton ↔ Pyro'),
  ('Stanton', 'Nyx',  'Stanton ↔ Nyx'),
  ('Pyro',    'Nyx',  'Pyro ↔ Nyx')
on conflict do nothing;

grant select on public.jump_points to anon, authenticated;

-- ── Helper: upsert body ──────────────────────────────────────────────────────
-- Two-step: first UPDATE rows that already exist by (system_id, name),
-- then INSERT only rows whose key doesn't exist yet.
-- This avoids violating the unique constraint on (system_id, name).

-- Step 1: assign key + orbital fields to existing rows
update public.bodies b
set
  key               = v.key,
  type              = v.type::text,
  orbital_radius_km = v.orbital_radius_km,
  body_radius_km    = v.body_radius_km,
  color             = v.color,
  texture           = v.texture,
  angle_deg         = v.angle_deg,
  lat_deg           = v.lat_deg,
  parent_key        = v.parent_key,
  station_glb       = coalesce(v.station_glb, b.station_glb)
from (values
  -- ── STANTON ──────────────────────────────────────────────────────────────
  ('Stanton','stanton_star','Stanton',        'star',          0,           116000, '#fff7e0', null,        null,    null,   null,           null),
  ('Stanton','hurston',    'Hurston',         'planet',        12850000,    1000,   '#8b4513', 'stanton1',  0,       null,   'stanton_star', null),
  ('Stanton','arial',      'Arial',           'moon',          52659,       345,    '#c2a068', 'stanton1a', -36.71,  null,   'hurston',      null),
  ('Stanton','aberdeen',   'Aberdeen',        'moon',          68815,       274,    '#a0522d', 'stanton1b', 36.52,   null,   'hurston',      null),
  ('Stanton','magda',      'Magda',           'moon',          94247,       341,    '#b87333', 'stanton1c', -127.80, null,   'hurston',      null),
  ('Stanton','ita',        'Ita',             'moon',          116686,      325,    '#8b6914', 'stanton1d', 100.00,  null,   'hurston',      null),
  ('Stanton','lorville',   'Lorville',        'city',          1000,        1,      '#88aacc', null,        0,       null,   'hurston',      null),
  ('Stanton','everus',     'Everus Harbor',   'station',       1149,        1,      '#88aacc', null,        -119.3,  null,   'hurston',      null),
  ('Stanton','hur_l1',     'HUR-L1 Green Glade Station',       'station',   11560000,  1, '#667799', null, 0,       null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','hur_l2',     'HUR-L2 Faithful Dream Station',    'station',   14130000,  1, '#667799', null, 0,       null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','hur_l3',     'HUR-L3 Thundering Express Station','station',   12850000,  1, '#667799', null, 180,     null,   'stanton_star', null),
  ('Stanton','hur_l4',     'HUR-L4 Melodic Fields Station',    'station',   12850000,  1, '#667799', null, 60,      null,   'stanton_star', null),
  ('Stanton','hur_l5',     'HUR-L5 High Course Station',       'station',   12850000,  1, '#667799', null, -59.99,  null,   'stanton_star', null),
  ('Stanton','crusader',   'Crusader',        'gas_giant',     19140000,    7450,   '#e8a87c', 'stanton2',  -172,    null,   'stanton_star', null),
  ('Stanton','cellin',     'Cellin',          'moon',          50866,       260,    '#d4a96a', 'stanton2a', -120.00, null,   'crusader',     null),
  ('Stanton','daymar',     'Daymar',          'moon',          63277,       295,    '#c68642', 'stanton2b', 60.00,   null,   'crusader',     null),
  ('Stanton','yela',       'Yela',            'moon',          79289,       313,    '#b0c4de', 'stanton2c', 140.00,  null,   'crusader',     null),
  ('Stanton','yela_belt',  'Yela Belt',       'asteroid_belt', 640,         1,      '#556677', null,        null,    null,   'yela',         null),
  ('Stanton','orison',     'Orison',          'city',          7529,        1,      '#88aacc', null,        -9.3,    null,   'crusader',     null),
  ('Stanton','grimhex',    'GrimHEX',         'station',       686,         1,      '#993322', null,        146.0,   null,   'yela',         null),
  ('Stanton','seraphim',   'Seraphim Station','station',       8241,        1,      '#88aacc', null,        -4.5,    null,   'crusader',     null),
  ('Stanton','cru_l1',     'CRU-L1 Ambitious Dream Station',   'station',   17230000,  1, '#667799', null, -171.99, null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','cru_l2',     'CRU-L2 Deep Thought Station',      'station',   21060000,  1, '#667799', null, -172,    null,   'stanton_star', null),
  ('Stanton','cru_l3',     'CRU-L3 Shady Glen Station',        'station',   19150000,  1, '#667799', null, 8,       null,   'stanton_star', null),
  ('Stanton','cru_l4',     'CRU-L4 Shallow Fields Station',    'station',   19140000,  1, '#667799', null, -112,    null,   'stanton_star', null),
  ('Stanton','cru_l5',     'CRU-L5 Beautiful Glen Station',    'station',   19150000,  1, '#667799', null, 128,     null,   'stanton_star', null),
  ('Stanton','arccorp',    'ArcCorp',         'planet',        28910000,    800,    '#4a90d9', 'stanton3',  -50,     null,   'stanton_star', null),
  ('Stanton','lyria',      'Lyria',           'moon',          119828,      223,    '#9b7fff', 'stanton3a', 14.63,   null,   'arccorp',      null),
  ('Stanton','wala',       'Wala',            'moon',          257308,      283,    '#aaaaaa', 'stanton3b', 143.94,  null,   'arccorp',      null),
  ('Stanton','area18',     'Area18',          'city',          800,         1,      '#88aacc', null,        -50,     null,   'arccorp',      null),
  ('Stanton','baijini',    'Baijini Point',   'station',       910,         1,      '#88aacc', null,        -157.4,  null,   'arccorp',      null),
  ('Stanton','arc_l1',     'ARC-L1 Wide Forest Station',       'station',   26020000,  1, '#667799', null, -50,     null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','arc_l2',     'ARC-L2 Lively Pathway Station',    'station',   31810000,  1, '#667799', null, -49.99,  null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','arc_l3',     'ARC-L3 Modern Express Station',    'station',   28920000,  1, '#667799', null, 150,     null,   'stanton_star', null),
  ('Stanton','arc_l4',     'ARC-L4 Faint Glen Station',        'station',   28910000,  1, '#667799', null, 9.99,    null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','arc_l5',     'ARC-L5 Yellow Core Station',       'station',   28920000,  1, '#667799', null, -110,    null,   'stanton_star', null),
  ('Stanton','microtech',  'microTech',       'planet',        43440000,    1000,   '#aad4f5', 'stanton4',  58.86,   null,   'stanton_star', null),
  ('Stanton','calliope',   'Calliope',        'moon',          65920,       240,    '#cce0f0', 'stanton4a', -165.14, null,   'microtech',    null),
  ('Stanton','clio',       'Clio',            'moon',          95850,       337,    '#b0d0e8', 'stanton4b', -81.21,  null,   'microtech',    null),
  ('Stanton','euterpe',    'Euterpe',         'moon',          107810,      213,    '#d0e8ff', 'stanton4c', -76.03,  null,   'microtech',    null),
  ('Stanton','new_babbage','New Babbage',     'city',          1000,        1,      '#88aacc', null,        58.86,   null,   'microtech',    null),
  ('Stanton','port_tressler','Port Tressler', 'station',       1126,        1,      '#88aacc', null,        44.2,    null,   'microtech',    null),
  ('Stanton','mic_l1',     'MIC-L1 Shallow Frontier Station',  'station',   39090000,  1, '#667799', null, 58.86,   null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','mic_l2',     'MIC-L2 Long Forest Station',       'station',   47790000,  1, '#667799', null, 58.86,   null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','mic_l3',     'MIC-L3 Endless Odyssey Station',   'station',   43440000,  1, '#667799', null, 239,     null,   'stanton_star', null),
  ('Stanton','mic_l4',     'MIC-L4 Red Crossroads Station',    'station',   43456000,  1, '#667799', null, 118.85,  null,   'stanton_star', null),
  ('Stanton','mic_l5',     'MIC-L5 Modern Icarus Station',     'station',   43450000,  1, '#667799', null, -1.13,   null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','pyro_gateway','Pyro Gateway',   'station',       28300000,    1,      '#ff9944', null,        -83.25,  -5.42,  'stanton_star', null),
  ('Stanton','terra_gateway','Terra Gateway', 'station',       51570000,    1,      '#44aaff', null,        -5.88,   null,   'stanton_star', null),
  ('Stanton','nyx_gateway', 'Nyx Gateway',   'station',       69550000,    1,      '#8899ff', null,        159.35,  16.88,  'stanton_star', null),
  ('Stanton','aaron_halo',  'Aaron Halo',    'asteroid_belt', 35000000,    500,    '#666655', null,        null,    null,   'stanton_star', null),

  -- ── PYRO ─────────────────────────────────────────────────────────────────
  ('Pyro','pyro_star',  'Pyro',            'star',          0,           57072,  '#ff6a00', null,     null,  null, null,       null),
  ('Pyro','pyro1',      'Pyro I',          'planet',        8200000,     412,    '#cc3300', 'pyro1',  40,    null, 'pyro_star',null),
  ('Pyro','p1_l2',      'PYAM-FARSTAT-1-2','station',       8200000,     1,      '#885533', null,     220,   null, 'pyro_star',null),
  ('Pyro','p1_l3',      'PYAM-FARSTAT-1-3','station',       8200000,     1,      '#885533', null,     216,   null, 'pyro_star',null),
  ('Pyro','p1_l5',      'PYAM-FARSTAT-1-5','station',       8200000,     1,      '#885533', null,     340,   null, 'pyro_star',null),
  ('Pyro','pyro2',      'Monox',           'planet',        10528000,    530,    '#888888', 'pyro2',  130,   null, 'pyro_star',null),
  ('Pyro','p2_orbituary_0','PYAM-FARSTAT-2-0','station',    600,         1,      '#885533', null,     null,  null, 'pyro2',    null),
  ('Pyro','p2_l3',      'PYAM-FARSTAT-2-3','station',       10528000,    1,      '#885533', null,     306,   null, 'pyro_star',null),
  ('Pyro','p2_l4',      'Checkmate',       'station',       10528000,    1,      '#885533', null,     190,   null, 'pyro_star',null),
  ('Pyro','pyro3',      'Pyro III',        'planet',        17643000,    414,    '#7a5c3a', 'pyro3',  220,   null, 'pyro_star',null),
  ('Pyro','p3_orbit',   'Orbituary',       'station',       600,         1,      '#885533', null,     null,  null, 'pyro3',    null),
  ('Pyro','p3_l1',      'Starlight Service Station','station',17643000,  1,      '#885533', null,     220,   null, 'pyro_star',null),
  ('Pyro','p3_l3',      'Patch City',      'station',       17643000,    1,      '#885533', null,     36,    null, 'pyro_star',null),
  ('Pyro','p3_l5',      'PYAM-FARSTAT-3-5','station',       17643000,    1,      '#885533', null,     160,   null, 'pyro_star',null),
  ('Pyro','pyro5',      'Pyro V',          'gas_giant',     72290000,    7812,   '#e8732a', 'pyro5',  310,   null, 'pyro_star',null),
  ('Pyro','pyro5a',     'Ignis',           'moon',          55325,       393,    '#dd4400', 'pyro5a', null,  null, 'pyro5',    null),
  ('Pyro','pyro5b',     'Vatra',           'moon',          64099,       366,    '#cc6633', 'pyro5b', null,  null, 'pyro5',    null),
  ('Pyro','pyro5c',     'Adir',            'moon',          85111,       431,    '#bb5522', 'pyro5c', null,  null, 'pyro5',    null),
  ('Pyro','pyro5d',     'Fairo',           'moon',          112096,      393,    '#aa4411', 'pyro5d', null,  null, 'pyro5',    null),
  ('Pyro','pyro5e',     'Fuego',           'moon',          146903,      466,    '#ff7744', 'pyro5e', null,  null, 'pyro5',    null),
  ('Pyro','pyro5f',     'Vuur',            'moon',          200000,      453,    '#994422', 'pyro5f', null,  null, 'pyro5',    null),
  ('Pyro','pyro4',      'Pyro IV',         'moon',          199524,      321,    '#ff9966', 'pyro4',  null,  null, 'pyro5',    null),
  ('Pyro','p5_l1',      'PYAM-FARSTAT-5-1','station',       72290000,    1,      '#885533', null,     310,   null, 'pyro_star',null),
  ('Pyro','p5_l2',      'Gaslight',        'station',       72290000,    1,      '#885533', null,     130,   null, 'pyro_star',null),
  ('Pyro','p5_l3',      'PYAM-FARSTAT-5-3','station',       72290000,    1,      '#885533', null,     126,   null, 'pyro_star',null),
  ('Pyro','p5_l4',      'Rod''s Fuel ''N Supplies','station',72290000,   1,      '#885533', null,     10,    null, 'pyro_star',null),
  ('Pyro','p5_l5',      'Rat''s Nest',     'station',       72290000,    1,      '#885533', null,     250,   null, 'pyro_star',null),
  ('Pyro','pyro6',      'Pyro VI',         'planet',        164965000,   285,    '#5588aa', 'pyro6',  55,    null, 'pyro_star',null),
  ('Pyro','ruin_station','Ruin Station',   'station',       400,         1,      '#993322', null,     null,  null, 'pyro6',    null),
  ('Pyro','p6_l2',      'PYAM-FARSTAT-6-2','station',       164965000,   1,      '#885533', null,     235,   null, 'pyro_star',null),
  ('Pyro','p6_l3',      'Endgame',         'station',       164965000,   1,      '#885533', null,     231,   null, 'pyro_star',null),
  ('Pyro','p6_l4',      'Dudley & Daughters','station',     164965000,   1,      '#885533', null,     115,   null, 'pyro_star',null),
  ('Pyro','p6_l5',      'Megumi Refueling', 'station',      164965000,   1,      '#885533', null,     355,   null, 'pyro_star',null),
  ('Pyro','checkmate_belt','Checkmate Belt','asteroid_belt', 40000000,   400,    '#555544', null,     null,  null, 'pyro_star',null),

  -- ── NYX ──────────────────────────────────────────────────────────────────
  ('Nyx','nyx_star',      'Nyx',             'star',          0,          57072,  '#e8e8ff', null,      null, null, null,       null),
  ('Nyx','nyx1',          'Nyx I',           'planet',        18929000,   1000,   '#cc4400', 'nyx1',    60,   null, 'nyx_star', null),
  ('Nyx','nyx2',          'Nyx II',          'planet',        31524000,   1000,   '#888866', 'nyx2',    150,  null, 'nyx_star', null),
  ('Nyx','glaciem_ring',  'Glaciem Ring',    'asteroid_belt', 44105000,   300,    '#aabbcc', null,      null, null, 'nyx_star', null),
  ('Nyx','delamar',       'Delamar',         'dwarf_planet',  44105000,   75,     '#696969', 'delamar', 240,  null, 'nyx_star', null),
  ('Nyx','levski',        'Levski',          'city',          100,        1,      '#88aacc', null,      null, null, 'delamar',  null),
  ('Nyx','glaciem_social','Glaciem Social Station 001','station',44105000,1,      '#667799', null,      60,   null, 'nyx_star', null),
  ('Nyx','nyx3',          'Nyx III',         'planet',        161760000,  1000,   '#aac8e0', 'nyx3',    270,  null, 'nyx_star', null),
  ('Nyx','keeger_belt',   'Keeger Belt',     'asteroid_belt', 180000000,  300,    '#778899', null,      null, null, 'nyx_star', null),
  ('Nyx','pss_alpha',     'People''s Service Station Alpha',  'station', 180000000,1,'#667799',null,    30,   null, 'nyx_star', null),
  ('Nyx','pss_delta',     'People''s Service Station Delta',  'station', 180000000,1,'#667799',null,   120,   null, 'nyx_star', null),
  ('Nyx','pss_theta',     'People''s Service Station Theta',  'station', 180000000,1,'#667799',null,   210,   null, 'nyx_star', null),
  ('Nyx','pss_lambda',    'People''s Service Station Lambda', 'station', 180000000,1,'#667799',null,   300,   null, 'nyx_star', null),
  ('Nyx','keeger_social', 'Keeger Social Station 001',        'station', 180000000,1,'#667799',null,   340,   null, 'nyx_star', null)
) as v(system_name, key, name, type, orbital_radius_km, body_radius_km, color, texture, angle_deg, lat_deg, parent_key, station_glb)
join public.systems s on s.name = v.system_name
where b.system_id = s.id and b.name = v.name;

-- Step 2: insert rows that don't exist yet (new bodies not in the original seed)
insert into public.bodies
  (system_id, key, name, type, orbital_radius_km, body_radius_km, color, texture, angle_deg, lat_deg, parent_key, station_glb)
select s.id, v.key, v.name, v.type::text, v.orbital_radius_km, v.body_radius_km, v.color, v.texture, v.angle_deg, v.lat_deg, v.parent_key, v.station_glb
from public.systems s
join (values
  ('Stanton','stanton_star','Stanton',        'star',          0,           116000, '#fff7e0', null,        null,    null,   null,           null),
  ('Stanton','hurston',    'Hurston',         'planet',        12850000,    1000,   '#8b4513', 'stanton1',  0,       null,   'stanton_star', null),
  ('Stanton','arial',      'Arial',           'moon',          52659,       345,    '#c2a068', 'stanton1a', -36.71,  null,   'hurston',      null),
  ('Stanton','aberdeen',   'Aberdeen',        'moon',          68815,       274,    '#a0522d', 'stanton1b', 36.52,   null,   'hurston',      null),
  ('Stanton','magda',      'Magda',           'moon',          94247,       341,    '#b87333', 'stanton1c', -127.80, null,   'hurston',      null),
  ('Stanton','ita',        'Ita',             'moon',          116686,      325,    '#8b6914', 'stanton1d', 100.00,  null,   'hurston',      null),
  ('Stanton','lorville',   'Lorville',        'city',          1000,        1,      '#88aacc', null,        0,       null,   'hurston',      null),
  ('Stanton','everus',     'Everus Harbor',   'station',       1149,        1,      '#88aacc', null,        -119.3,  null,   'hurston',      null),
  ('Stanton','hur_l1',     'HUR-L1 Green Glade Station',       'station',   11560000,  1, '#667799', null, 0,       null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','hur_l2',     'HUR-L2 Faithful Dream Station',    'station',   14130000,  1, '#667799', null, 0,       null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','hur_l3',     'HUR-L3 Thundering Express Station','station',   12850000,  1, '#667799', null, 180,     null,   'stanton_star', null),
  ('Stanton','hur_l4',     'HUR-L4 Melodic Fields Station',    'station',   12850000,  1, '#667799', null, 60,      null,   'stanton_star', null),
  ('Stanton','hur_l5',     'HUR-L5 High Course Station',       'station',   12850000,  1, '#667799', null, -59.99,  null,   'stanton_star', null),
  ('Stanton','crusader',   'Crusader',        'gas_giant',     19140000,    7450,   '#e8a87c', 'stanton2',  -172,    null,   'stanton_star', null),
  ('Stanton','cellin',     'Cellin',          'moon',          50866,       260,    '#d4a96a', 'stanton2a', -120.00, null,   'crusader',     null),
  ('Stanton','daymar',     'Daymar',          'moon',          63277,       295,    '#c68642', 'stanton2b', 60.00,   null,   'crusader',     null),
  ('Stanton','yela',       'Yela',            'moon',          79289,       313,    '#b0c4de', 'stanton2c', 140.00,  null,   'crusader',     null),
  ('Stanton','yela_belt',  'Yela Belt',       'asteroid_belt', 640,         1,      '#556677', null,        null,    null,   'yela',         null),
  ('Stanton','orison',     'Orison',          'city',          7529,        1,      '#88aacc', null,        -9.3,    null,   'crusader',     null),
  ('Stanton','grimhex',    'GrimHEX',         'station',       686,         1,      '#993322', null,        146.0,   null,   'yela',         null),
  ('Stanton','seraphim',   'Seraphim Station','station',       8241,        1,      '#88aacc', null,        -4.5,    null,   'crusader',     null),
  ('Stanton','cru_l1',     'CRU-L1 Ambitious Dream Station',   'station',   17230000,  1, '#667799', null, -171.99, null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','cru_l2',     'CRU-L2 Deep Thought Station',      'station',   21060000,  1, '#667799', null, -172,    null,   'stanton_star', null),
  ('Stanton','cru_l3',     'CRU-L3 Shady Glen Station',        'station',   19150000,  1, '#667799', null, 8,       null,   'stanton_star', null),
  ('Stanton','cru_l4',     'CRU-L4 Shallow Fields Station',    'station',   19140000,  1, '#667799', null, -112,    null,   'stanton_star', null),
  ('Stanton','cru_l5',     'CRU-L5 Beautiful Glen Station',    'station',   19150000,  1, '#667799', null, 128,     null,   'stanton_star', null),
  ('Stanton','arccorp',    'ArcCorp',         'planet',        28910000,    800,    '#4a90d9', 'stanton3',  -50,     null,   'stanton_star', null),
  ('Stanton','lyria',      'Lyria',           'moon',          119828,      223,    '#9b7fff', 'stanton3a', 14.63,   null,   'arccorp',      null),
  ('Stanton','wala',       'Wala',            'moon',          257308,      283,    '#aaaaaa', 'stanton3b', 143.94,  null,   'arccorp',      null),
  ('Stanton','area18',     'Area18',          'city',          800,         1,      '#88aacc', null,        -50,     null,   'arccorp',      null),
  ('Stanton','baijini',    'Baijini Point',   'station',       910,         1,      '#88aacc', null,        -157.4,  null,   'arccorp',      null),
  ('Stanton','arc_l1',     'ARC-L1 Wide Forest Station',       'station',   26020000,  1, '#667799', null, -50,     null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','arc_l2',     'ARC-L2 Lively Pathway Station',    'station',   31810000,  1, '#667799', null, -49.99,  null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','arc_l3',     'ARC-L3 Modern Express Station',    'station',   28920000,  1, '#667799', null, 150,     null,   'stanton_star', null),
  ('Stanton','arc_l4',     'ARC-L4 Faint Glen Station',        'station',   28910000,  1, '#667799', null, 9.99,    null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','arc_l5',     'ARC-L5 Yellow Core Station',       'station',   28920000,  1, '#667799', null, -110,    null,   'stanton_star', null),
  ('Stanton','microtech',  'microTech',       'planet',        43440000,    1000,   '#aad4f5', 'stanton4',  58.86,   null,   'stanton_star', null),
  ('Stanton','calliope',   'Calliope',        'moon',          65920,       240,    '#cce0f0', 'stanton4a', -165.14, null,   'microtech',    null),
  ('Stanton','clio',       'Clio',            'moon',          95850,       337,    '#b0d0e8', 'stanton4b', -81.21,  null,   'microtech',    null),
  ('Stanton','euterpe',    'Euterpe',         'moon',          107810,      213,    '#d0e8ff', 'stanton4c', -76.03,  null,   'microtech',    null),
  ('Stanton','new_babbage','New Babbage',     'city',          1000,        1,      '#88aacc', null,        58.86,   null,   'microtech',    null),
  ('Stanton','port_tressler','Port Tressler', 'station',       1126,        1,      '#88aacc', null,        44.2,    null,   'microtech',    null),
  ('Stanton','mic_l1',     'MIC-L1 Shallow Frontier Station',  'station',   39090000,  1, '#667799', null, 58.86,   null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','mic_l2',     'MIC-L2 Long Forest Station',       'station',   47790000,  1, '#667799', null, 58.86,   null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','mic_l3',     'MIC-L3 Endless Odyssey Station',   'station',   43440000,  1, '#667799', null, 239,     null,   'stanton_star', null),
  ('Stanton','mic_l4',     'MIC-L4 Red Crossroads Station',    'station',   43456000,  1, '#667799', null, 118.85,  null,   'stanton_star', null),
  ('Stanton','mic_l5',     'MIC-L5 Modern Icarus Station',     'station',   43450000,  1, '#667799', null, -1.13,   null,   'stanton_star', 'smap_shubin.glb'),
  ('Stanton','pyro_gateway','Pyro Gateway',   'station',       28300000,    1,      '#ff9944', null,        -83.25,  -5.42,  'stanton_star', null),
  ('Stanton','terra_gateway','Terra Gateway', 'station',       51570000,    1,      '#44aaff', null,        -5.88,   null,   'stanton_star', null),
  ('Stanton','nyx_gateway', 'Nyx Gateway',   'station',       69550000,    1,      '#8899ff', null,        159.35,  16.88,  'stanton_star', null),
  ('Stanton','aaron_halo',  'Aaron Halo',    'asteroid_belt', 35000000,    500,    '#666655', null,        null,    null,   'stanton_star', null),
  ('Pyro','pyro_star',  'Pyro',            'star',          0,           57072,  '#ff6a00', null,     null,  null, null,       null),
  ('Pyro','pyro1',      'Pyro I',          'planet',        8200000,     412,    '#cc3300', 'pyro1',  40,    null, 'pyro_star',null),
  ('Pyro','p1_l2',      'PYAM-FARSTAT-1-2','station',       8200000,     1,      '#885533', null,     220,   null, 'pyro_star',null),
  ('Pyro','p1_l3',      'PYAM-FARSTAT-1-3','station',       8200000,     1,      '#885533', null,     216,   null, 'pyro_star',null),
  ('Pyro','p1_l5',      'PYAM-FARSTAT-1-5','station',       8200000,     1,      '#885533', null,     340,   null, 'pyro_star',null),
  ('Pyro','pyro2',      'Monox',           'planet',        10528000,    530,    '#888888', 'pyro2',  130,   null, 'pyro_star',null),
  ('Pyro','p2_orbituary_0','PYAM-FARSTAT-2-0','station',    600,         1,      '#885533', null,     null,  null, 'pyro2',    null),
  ('Pyro','p2_l3',      'PYAM-FARSTAT-2-3','station',       10528000,    1,      '#885533', null,     306,   null, 'pyro_star',null),
  ('Pyro','p2_l4',      'Checkmate',       'station',       10528000,    1,      '#885533', null,     190,   null, 'pyro_star',null),
  ('Pyro','pyro3',      'Pyro III',        'planet',        17643000,    414,    '#7a5c3a', 'pyro3',  220,   null, 'pyro_star',null),
  ('Pyro','p3_orbit',   'Orbituary',       'station',       600,         1,      '#885533', null,     null,  null, 'pyro3',    null),
  ('Pyro','p3_l1',      'Starlight Service Station','station',17643000,  1,      '#885533', null,     220,   null, 'pyro_star',null),
  ('Pyro','p3_l3',      'Patch City',      'station',       17643000,    1,      '#885533', null,     36,    null, 'pyro_star',null),
  ('Pyro','p3_l5',      'PYAM-FARSTAT-3-5','station',       17643000,    1,      '#885533', null,     160,   null, 'pyro_star',null),
  ('Pyro','pyro5',      'Pyro V',          'gas_giant',     72290000,    7812,   '#e8732a', 'pyro5',  310,   null, 'pyro_star',null),
  ('Pyro','pyro5a',     'Ignis',           'moon',          55325,       393,    '#dd4400', 'pyro5a', null,  null, 'pyro5',    null),
  ('Pyro','pyro5b',     'Vatra',           'moon',          64099,       366,    '#cc6633', 'pyro5b', null,  null, 'pyro5',    null),
  ('Pyro','pyro5c',     'Adir',            'moon',          85111,       431,    '#bb5522', 'pyro5c', null,  null, 'pyro5',    null),
  ('Pyro','pyro5d',     'Fairo',           'moon',          112096,      393,    '#aa4411', 'pyro5d', null,  null, 'pyro5',    null),
  ('Pyro','pyro5e',     'Fuego',           'moon',          146903,      466,    '#ff7744', 'pyro5e', null,  null, 'pyro5',    null),
  ('Pyro','pyro5f',     'Vuur',            'moon',          200000,      453,    '#994422', 'pyro5f', null,  null, 'pyro5',    null),
  ('Pyro','pyro4',      'Pyro IV',         'moon',          199524,      321,    '#ff9966', 'pyro4',  null,  null, 'pyro5',    null),
  ('Pyro','p5_l1',      'PYAM-FARSTAT-5-1','station',       72290000,    1,      '#885533', null,     310,   null, 'pyro_star',null),
  ('Pyro','p5_l2',      'Gaslight',        'station',       72290000,    1,      '#885533', null,     130,   null, 'pyro_star',null),
  ('Pyro','p5_l3',      'PYAM-FARSTAT-5-3','station',       72290000,    1,      '#885533', null,     126,   null, 'pyro_star',null),
  ('Pyro','p5_l4',      'Rod''s Fuel ''N Supplies','station',72290000,   1,      '#885533', null,     10,    null, 'pyro_star',null),
  ('Pyro','p5_l5',      'Rat''s Nest',     'station',       72290000,    1,      '#885533', null,     250,   null, 'pyro_star',null),
  ('Pyro','pyro6',      'Pyro VI',         'planet',        164965000,   285,    '#5588aa', 'pyro6',  55,    null, 'pyro_star',null),
  ('Pyro','ruin_station','Ruin Station',   'station',       400,         1,      '#993322', null,     null,  null, 'pyro6',    null),
  ('Pyro','p6_l2',      'PYAM-FARSTAT-6-2','station',       164965000,   1,      '#885533', null,     235,   null, 'pyro_star',null),
  ('Pyro','p6_l3',      'Endgame',         'station',       164965000,   1,      '#885533', null,     231,   null, 'pyro_star',null),
  ('Pyro','p6_l4',      'Dudley & Daughters','station',     164965000,   1,      '#885533', null,     115,   null, 'pyro_star',null),
  ('Pyro','p6_l5',      'Megumi Refueling', 'station',      164965000,   1,      '#885533', null,     355,   null, 'pyro_star',null),
  ('Pyro','checkmate_belt','Checkmate Belt','asteroid_belt', 40000000,   400,    '#555544', null,     null,  null, 'pyro_star',null),
  ('Nyx','nyx_star',      'Nyx',             'star',          0,          57072,  '#e8e8ff', null,      null, null, null,       null),
  ('Nyx','nyx1',          'Nyx I',           'planet',        18929000,   1000,   '#cc4400', 'nyx1',    60,   null, 'nyx_star', null),
  ('Nyx','nyx2',          'Nyx II',          'planet',        31524000,   1000,   '#888866', 'nyx2',    150,  null, 'nyx_star', null),
  ('Nyx','glaciem_ring',  'Glaciem Ring',    'asteroid_belt', 44105000,   300,    '#aabbcc', null,      null, null, 'nyx_star', null),
  ('Nyx','delamar',       'Delamar',         'dwarf_planet',  44105000,   75,     '#696969', 'delamar', 240,  null, 'nyx_star', null),
  ('Nyx','levski',        'Levski',          'city',          100,        1,      '#88aacc', null,      null, null, 'delamar',  null),
  ('Nyx','glaciem_social','Glaciem Social Station 001','station',44105000,1,      '#667799', null,      60,   null, 'nyx_star', null),
  ('Nyx','nyx3',          'Nyx III',         'planet',        161760000,  1000,   '#aac8e0', 'nyx3',    270,  null, 'nyx_star', null),
  ('Nyx','keeger_belt',   'Keeger Belt',     'asteroid_belt', 180000000,  300,    '#778899', null,      null, null, 'nyx_star', null),
  ('Nyx','pss_alpha',     'People''s Service Station Alpha',  'station', 180000000,1,'#667799',null,    30,   null, 'nyx_star', null),
  ('Nyx','pss_delta',     'People''s Service Station Delta',  'station', 180000000,1,'#667799',null,   120,   null, 'nyx_star', null),
  ('Nyx','pss_theta',     'People''s Service Station Theta',  'station', 180000000,1,'#667799',null,   210,   null, 'nyx_star', null),
  ('Nyx','pss_lambda',    'People''s Service Station Lambda', 'station', 180000000,1,'#667799',null,   300,   null, 'nyx_star', null),
  ('Nyx','keeger_social', 'Keeger Social Station 001',        'station', 180000000,1,'#667799',null,   340,   null, 'nyx_star', null)
) as v(system_name, key, name, type, orbital_radius_km, body_radius_km, color, texture, angle_deg, lat_deg, parent_key, station_glb)
on s.name = v.system_name
where not exists (select 1 from public.bodies b2 where b2.key = v.key);

-- ── RLS for jump_points (public read) ────────────────────────────────────────
alter table public.jump_points enable row level security;
create policy "public read jump_points"
  on public.jump_points for select using (true);
