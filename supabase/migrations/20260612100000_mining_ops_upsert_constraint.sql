-- PostgREST upsert requires a named UNIQUE CONSTRAINT, not just a UNIQUE INDEX.
-- The existing mining_ops_one_per_ship is an index; add the constraint so that
-- upsert(onConflict: "player_id,ship_type") works correctly.

alter table public.mining_operations
  drop constraint if exists mining_ops_one_per_ship_constraint;

alter table public.mining_operations
  add constraint mining_ops_one_per_ship_constraint
  unique using index mining_ops_one_per_ship;
