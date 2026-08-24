-- Add Bally Bet to the active bookmaker list used by the admin dropdown.
INSERT INTO public.bookmakers (name, short_name, affiliate_link, active)
SELECT 'Bally Bet', 'Bally Bet', NULL, true
WHERE NOT EXISTS (
  SELECT 1
  FROM public.bookmakers
  WHERE LOWER(REPLACE(name, ' ', '')) IN ('ballybet', 'ballysbet')
     OR LOWER(REPLACE(short_name, ' ', '')) IN ('ballybet', 'ballysbet')
);

UPDATE public.bookmakers
SET name = 'Bally Bet', short_name = 'Bally Bet', active = true
WHERE LOWER(REPLACE(name, ' ', '')) IN ('ballybet', 'ballysbet')
   OR LOWER(REPLACE(short_name, ' ', '')) IN ('ballybet', 'ballysbet');
