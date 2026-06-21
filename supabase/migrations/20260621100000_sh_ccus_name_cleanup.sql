-- Clean up corrupted / mis-normalised ship names in sh_ccus
-- 8 distinct issues affecting 28 edges total
-- Strategy: if the clean name already exists (collision), delete the corrupt row;
--           otherwise rename it in-place.

-- 1. "Genesis Starliner Upagrade" → "Genesis Starliner"
--    Mole Carbon -> Genesis Starliner already exists at $124.79 (corrupt row is $108, better price)
--    → update the existing row to keep the better price, then delete the corrupt one
UPDATE sh_ccus SET price = 108, scraped_at = NOW()
WHERE from_ship = 'Mole Carbon' AND to_ship = 'Genesis Starliner';
DELETE FROM sh_ccus WHERE to_ship = 'Genesis Starliner Upagrade';

-- 2. CCU title parsed as "Ironclad ...spaces... to Ironclad" — nonsense self-upgrade
DELETE FROM sh_ccus WHERE to_ship LIKE 'Ironclad%to Ironclad';

-- 3. "Ironclad Base, Edition w/ruance" → "Ironclad Base" — no collision
UPDATE sh_ccus SET to_ship = 'Ironclad Base'
WHERE to_ship = 'Ironclad Base, Edition w/ruance';

-- 4. "Nomad Edition, with" → "Nomad"
--    Reliant Kore -> Nomad already exists at $29.53 (corrupt row is $85, worse)
--    → keep existing, delete corrupt
DELETE FROM sh_ccus WHERE to_ship = 'Nomad Edition, with';

-- 5. "Prowler - Update" → "Prowler"
--    Caterpillar -> Prowler already exists at $154.92 (corrupt row is $204.89, worse)
--    → keep existing, delete corrupt
DELETE FROM sh_ccus WHERE to_ship = 'Prowler - Update';

-- 6. "the Anvil Carrack" → "Carrack"
--    Hercules M2 -> Carrack already exists at $75 (corrupt row is $120, worse)
--    → keep existing, delete corrupt
DELETE FROM sh_ccus WHERE to_ship = 'the Anvil Carrack';

-- 7. Double space in "Titan  Renegade" — no collision
UPDATE sh_ccus SET from_ship = 'Titan Renegade'
WHERE from_ship = 'Titan  Renegade';

-- 8. "R" is Greycat R — 22 edges, no duplicates with Greycat R, safe to rename
UPDATE sh_ccus SET from_ship = 'Greycat R'
WHERE from_ship = 'R';
