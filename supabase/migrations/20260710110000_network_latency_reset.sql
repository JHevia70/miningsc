-- One-time reset: clear test/mixed-country ping_results accumulated while
-- iterating on the country list, so history starts homogeneous with the
-- final 16-country set (ES, DE, NL, FR, PT, IT, PL, RU, AT, DK, FI, NO, GB, CH, SK, UA).
truncate table public.ping_results restart identity;
