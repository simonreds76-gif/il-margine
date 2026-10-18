-- Applied and verified 18 October 2026 with user approval.
DROP POLICY IF EXISTS "Private Skyline paper snapshot" ON public.goalscorer_live_snapshot;
CREATE POLICY "Private Skyline paper snapshot" ON public.goalscorer_live_snapshot AS RESTRICTIVE FOR SELECT TO PUBLIC USING (snapshot_key <> 'skyline_paper_v1');
