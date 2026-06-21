-- Spawn data for bodies missing from mineral_spawns.
-- Only ship_asteroid mining type (relevant for the simulator).
-- Cellin/Wala/Euterpe share their parent planet HPP (no dedicated HPP in DCB).
-- Pyro V moons use their new canonical names (Ignis/Vatra/Adir/Fairo/Fuego/Vuur).
-- Pyro IV (moon of Pyro V) uses hpp_pyro4.
INSERT INTO mineral_spawns (system, body, body_type, parent_body, mineral, mining_type, spawn_prob_pct, group_prob, data_version, source_file) VALUES
-- Cellin (moon of Crusader) — hpp_stanton2a
('Stanton', 'Cellin', 'moon', 'Crusader', 'Quartz',      'ship_asteroid', 25.7, 6.0, '4.x', 'hpp_stanton2a'),
('Stanton', 'Cellin', 'moon', 'Crusader', 'Agricium',    'ship_asteroid', 28.5, 6.0, '4.x', 'hpp_stanton2a'),
('Stanton', 'Cellin', 'moon', 'Crusader', 'Taranite',    'ship_asteroid', 18.0, 6.0, '4.x', 'hpp_stanton2a'),
('Stanton', 'Cellin', 'moon', 'Crusader', 'Quantainium', 'ship_asteroid',  2.0, 6.0, '4.x', 'hpp_stanton2a'),
('Stanton', 'Cellin', 'moon', 'Crusader', 'Silicon',     'ship_asteroid', 25.8, 6.0, '4.x', 'hpp_stanton2a'),
-- Wala (moon of ArcCorp) — hpp_stanton3a
('Stanton', 'Wala', 'moon', 'ArcCorp', 'Iron',        'ship_asteroid', 34.8, 6.0, '4.x', 'hpp_stanton3a'),
('Stanton', 'Wala', 'moon', 'ArcCorp', 'Copper',      'ship_asteroid', 34.8, 6.0, '4.x', 'hpp_stanton3a'),
('Stanton', 'Wala', 'moon', 'ArcCorp', 'Laranite',    'ship_asteroid', 28.5, 6.0, '4.x', 'hpp_stanton3a'),
('Stanton', 'Wala', 'moon', 'ArcCorp', 'Quantainium', 'ship_asteroid',  2.0, 6.0, '4.x', 'hpp_stanton3a'),
-- Euterpe (moon of microTech) — hpp_stanton4a
('Stanton', 'Euterpe', 'moon', 'microTech', 'Iron',         'ship_asteroid', 32.7, 6.0, '4.x', 'hpp_stanton4a'),
('Stanton', 'Euterpe', 'moon', 'microTech', 'Ice',          'ship_asteroid', 32.6, 6.0, '4.x', 'hpp_stanton4a'),
('Stanton', 'Euterpe', 'moon', 'microTech', 'Hephaestanite','ship_asteroid', 32.6, 6.0, '4.x', 'hpp_stanton4a'),
('Stanton', 'Euterpe', 'moon', 'microTech', 'Quantainium',  'ship_asteroid',  2.0, 6.0, '4.x', 'hpp_stanton4a'),
-- Ignis (Pyro V-a) — hpp_pyro5a
('Pyro', 'Ignis', 'moon', 'Pyro V', 'Tin',     'ship_asteroid', 36.0, 7.5, '4.x', 'hpp_pyro5a'),
('Pyro', 'Ignis', 'moon', 'Pyro V', 'Silicon', 'ship_asteroid', 36.0, 7.5, '4.x', 'hpp_pyro5a'),
('Pyro', 'Ignis', 'moon', 'Pyro V', 'Riccite', 'ship_asteroid', 10.0, 7.5, '4.x', 'hpp_pyro5a'),
('Pyro', 'Ignis', 'moon', 'Pyro V', 'Gold',    'ship_asteroid', 18.0, 7.5, '4.x', 'hpp_pyro5a'),
-- Vatra (Pyro V-b) — hpp_pyro5b
('Pyro', 'Vatra', 'moon', 'Pyro V', 'Iron',    'ship_asteroid', 36.0, 7.5, '4.x', 'hpp_pyro5b'),
('Pyro', 'Vatra', 'moon', 'Pyro V', 'Silicon', 'ship_asteroid', 36.0, 7.5, '4.x', 'hpp_pyro5b'),
('Pyro', 'Vatra', 'moon', 'Pyro V', 'Riccite', 'ship_asteroid', 10.0, 7.5, '4.x', 'hpp_pyro5b'),
('Pyro', 'Vatra', 'moon', 'Pyro V', 'Gold',    'ship_asteroid', 18.0, 7.5, '4.x', 'hpp_pyro5b'),
-- Adir (Pyro V-c) — hpp_pyro5c
('Pyro', 'Adir', 'moon', 'Pyro V', 'Iron',     'ship_asteroid', 43.5, 7.5, '4.x', 'hpp_pyro5c'),
('Pyro', 'Adir', 'moon', 'Pyro V', 'Tungsten', 'ship_asteroid', 28.5, 7.5, '4.x', 'hpp_pyro5c'),
('Pyro', 'Adir', 'moon', 'Pyro V', 'Riccite',  'ship_asteroid', 10.0, 7.5, '4.x', 'hpp_pyro5c'),
('Pyro', 'Adir', 'moon', 'Pyro V', 'Borase',   'ship_asteroid', 18.0, 7.5, '4.x', 'hpp_pyro5c'),
-- Fairo (Pyro V-d) — hpp_pyro5d
('Pyro', 'Fairo', 'moon', 'Pyro V', 'Bexalite', 'ship_asteroid',  9.0, 7.5, '4.x', 'hpp_pyro5d'),
('Pyro', 'Fairo', 'moon', 'Pyro V', 'Tungsten', 'ship_asteroid', 28.5, 7.5, '4.x', 'hpp_pyro5d'),
('Pyro', 'Fairo', 'moon', 'Pyro V', 'Silicon',  'ship_asteroid', 26.8, 7.5, '4.x', 'hpp_pyro5d'),
('Pyro', 'Fairo', 'moon', 'Pyro V', 'Gold',     'ship_asteroid',  9.0, 7.5, '4.x', 'hpp_pyro5d'),
('Pyro', 'Fairo', 'moon', 'Pyro V', 'Iron',     'ship_asteroid', 26.7, 7.5, '4.x', 'hpp_pyro5d'),
-- Fuego (Pyro V-e) — hpp_pyro5e
('Pyro', 'Fuego', 'moon', 'Pyro V', 'Borase',       'ship_asteroid',  9.0, 7.5, '4.x', 'hpp_pyro5e'),
('Pyro', 'Fuego', 'moon', 'Pyro V', 'Bexalite',     'ship_asteroid',  9.0, 7.5, '4.x', 'hpp_pyro5e'),
('Pyro', 'Fuego', 'moon', 'Pyro V', 'Aslarite',     'ship_asteroid', 28.5, 7.5, '4.x', 'hpp_pyro5e'),
('Pyro', 'Fuego', 'moon', 'Pyro V', 'Hephaestanite','ship_asteroid', 26.7, 7.5, '4.x', 'hpp_pyro5e'),
('Pyro', 'Fuego', 'moon', 'Pyro V', 'Iron',         'ship_asteroid', 26.8, 7.5, '4.x', 'hpp_pyro5e'),
-- Vuur (Pyro V-f) — hpp_pyro5f
('Pyro', 'Vuur', 'moon', 'Pyro V', 'Agricium',     'ship_asteroid', 14.2, 7.5, '4.x', 'hpp_pyro5f'),
('Pyro', 'Vuur', 'moon', 'Pyro V', 'Bexalite',     'ship_asteroid', 18.0, 7.5, '4.x', 'hpp_pyro5f'),
('Pyro', 'Vuur', 'moon', 'Pyro V', 'Aslarite',     'ship_asteroid', 14.2, 7.5, '4.x', 'hpp_pyro5f'),
('Pyro', 'Vuur', 'moon', 'Pyro V', 'Hephaestanite','ship_asteroid', 26.8, 7.5, '4.x', 'hpp_pyro5f'),
('Pyro', 'Vuur', 'moon', 'Pyro V', 'Iron',         'ship_asteroid', 26.8, 7.5, '4.x', 'hpp_pyro5f'),
-- Pyro IV (moon of Pyro V) — hpp_pyro4
('Pyro', 'Pyro IV', 'moon', 'Pyro V', 'Laranite',    'ship_asteroid', 28.5, 7.5, '4.x', 'hpp_pyro4'),
('Pyro', 'Pyro IV', 'moon', 'Pyro V', 'Borase',      'ship_asteroid', 18.0, 7.5, '4.x', 'hpp_pyro4'),
('Pyro', 'Pyro IV', 'moon', 'Pyro V', 'Copper',      'ship_asteroid', 25.7, 7.5, '4.x', 'hpp_pyro4'),
('Pyro', 'Pyro IV', 'moon', 'Pyro V', 'Stileron',    'ship_asteroid',  2.0, 7.5, '4.x', 'hpp_pyro4'),
('Pyro', 'Pyro IV', 'moon', 'Pyro V', 'Iron',        'ship_asteroid', 25.7, 7.5, '4.x', 'hpp_pyro4');
