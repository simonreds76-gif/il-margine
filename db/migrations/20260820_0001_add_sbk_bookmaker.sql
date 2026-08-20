-- Add SBK (betsbk.com) to the active bookmaker list used by the admin dropdown.
INSERT INTO public.bookmakers (name, short_name, affiliate_link, active)
SELECT 'SBK', 'SBK', NULL, true
WHERE NOT EXISTS (
  SELECT 1
  FROM public.bookmakers
  WHERE LOWER(name) = 'sbk'
     OR LOWER(short_name) IN ('sbk', 'betsbk')
);

UPDATE public.bookmakers
SET name = 'SBK', short_name = 'SBK', active = true
WHERE LOWER(name) = 'sbk'
   OR LOWER(short_name) IN ('sbk', 'betsbk');
