-- Run this in Supabase SQL Editor to add Bwin and deactivate Unibet

-- 1. Add Bwin (Entain group, similar to Coral/Ladbrokes)
INSERT INTO public.bookmakers (name, short_name, active, affiliate_link)
SELECT 'Bwin', 'BW', true, NULL
WHERE NOT EXISTS (SELECT 1 FROM public.bookmakers WHERE LOWER(name) = 'bwin' OR short_name = 'BW');

-- 2. Deactivate Unibet (no longer a recommended partner)
UPDATE public.bookmakers SET active = false WHERE LOWER(short_name) = 'un' OR LOWER(name) LIKE '%unibet%';
