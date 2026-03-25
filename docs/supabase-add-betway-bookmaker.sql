-- Add Betway to the bookmakers table so it appears in the admin dropdown
-- and can be attached to tips with the internal affiliate redirect route.

INSERT INTO bookmakers (name, short_name, affiliate_link, active)
SELECT 'Betway', 'Betway', '/api/go/betway', true
WHERE NOT EXISTS (
  SELECT 1 FROM bookmakers WHERE short_name = 'Betway' OR name = 'Betway'
);
