-- Second reset: the deepest-reachable-hop fix (see network_runner.py
-- _last_reachable_hop) changes how RTT is computed per country, making prior
-- rows (measured with the old 0%-loss-only rule) not comparable to new ones.
truncate table public.ping_results restart identity;
