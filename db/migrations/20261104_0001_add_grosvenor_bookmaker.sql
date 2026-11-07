-- Idempotent addition to the Admin sportsbook selector; no tip/feed changes.
INSERT INTO public.bookmakers (name, short_name, affiliate_link, active)
SELECT 'Grosvenor Sport', 'Grosvenor', NULL, true
WHERE NOT EXISTS (
  SELECT 1
  FROM public.bookmakers
  WHERE REGEXP_REPLACE(LOWER(name), '[^a-z0-9]', '', 'g') IN
    ('grosvenor', 'grosvenorsport', 'grosvenorsports', 'grosvenorsportsbook',
     'grosvenorcasino', 'grosvenorcasinos', 'grosvenorcasinosportsbook')
     OR REGEXP_REPLACE(LOWER(short_name), '[^a-z0-9]', '', 'g') IN
    ('grosvenor', 'grosvenorsport', 'grosvenorsports', 'grosvenorsportsbook',
     'grosvenorcasino', 'grosvenorcasinos', 'grosvenorcasinosportsbook')
);
