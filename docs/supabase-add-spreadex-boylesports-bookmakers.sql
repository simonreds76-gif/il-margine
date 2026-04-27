-- Add Spreadex and BoyleSports to the active bookmakers table for tip reporting.
-- They intentionally have no affiliate links for now, so they are selectable
-- in admin/reporting without being treated as affiliate partners.

INSERT INTO public.bookmakers (name, short_name, affiliate_link, active)
SELECT 'Spreadex', 'Spreadex', NULL, true
WHERE NOT EXISTS (
  SELECT 1
  FROM public.bookmakers
  WHERE LOWER(name) = 'spreadex'
     OR LOWER(short_name) IN ('spreadex', 'spx')
);

UPDATE public.bookmakers
SET name = 'Spreadex',
    short_name = 'Spreadex',
    affiliate_link = NULL,
    active = true
WHERE LOWER(name) = 'spreadex'
   OR LOWER(short_name) IN ('spreadex', 'spx');

INSERT INTO public.bookmakers (name, short_name, affiliate_link, active)
SELECT 'BoyleSports', 'BoyleSports', NULL, true
WHERE NOT EXISTS (
  SELECT 1
  FROM public.bookmakers
  WHERE LOWER(name) IN ('boylesports', 'boyle sports')
     OR LOWER(short_name) IN ('boylesports', 'boyle sports', 'boy', 'bs')
);

UPDATE public.bookmakers
SET name = 'BoyleSports',
    short_name = 'BoyleSports',
    affiliate_link = NULL,
    active = true
WHERE LOWER(name) IN ('boylesports', 'boyle sports')
   OR LOWER(short_name) IN ('boylesports', 'boyle sports', 'boy', 'bs');
