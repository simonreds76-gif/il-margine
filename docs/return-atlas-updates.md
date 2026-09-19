# Return Atlas daily publication

The owner authorised automatic publication after validation on 19 September 2026.

The existing hidden `IlMargine-Daily-AM` task starts at 10:05 local Windows time.
After its successful OnCourt refresh and betting-alert work, it runs the Atlas
publisher. There is no extra scheduled task, visitor polling, Supabase query or
paid odds API request. This desktop must be running with its usual user session;
it is not an always-on cloud scheduler.

Machine config: `D:/IlMargine/return-atlas-automation/config.json`.
Status/error/last successful version: `D:/IlMargine/return-atlas-automation/status.json`.
The AM pipeline also records a failed run if Atlas fails. Config holds only paths.
Git and Vercel use the user's existing authenticated CLI sessions.

1. Require OnCourt player/tournament/result CSVs newer than 30 hours and copy a
   stable snapshot. The morning pipeline completes before this step.
2. Download the current year's paired Pinnacle CSV once per day. Previous years
   remain cached. Annual rollover downloads the new year's archive; unavailable
   or malformed data fails closed. Existing workbook/capture supplements retain
   their distinct price-basis labels.
3. Reconcile ATP main-draw completed singles against OnCourt identities, round,
   tournament, scores, winner and surface. Exclude unpriced/unresolved records.
   OnCourt contains odds, but its local odds table has no closing timestamp and
   bookmaker mapping is not established here; these are not substituted.
4. Build a separate candidate and check all player histories and both betting
   directions. Reject disappearing or altered historical prices/results, changed
   score/event details, future records and backfills larger than 400 matches.
   Such corrections need review; they never silently rewrite published returns.
5. If accepted matches are unchanged, log the check and do not deploy. The page's
   'Data checked' date is the archive-release check, not a daily heartbeat. The
   latest included match date only advances when an eligible priced match exists.
6. Commit only the versioned archive and release manifest from an isolated sparse
   checkout; never force-push. Build a Vercel production candidate without moving
   the public alias, verify its page/index, check the branch has not advanced,
   then promote. A failed build or pre-promotion check leaves the old site live.
   A post-promotion verification failure is reported and needs investigation.

Keep three deployed archive versions, always preserving the candidate, previous
release and current live version. Older static directories are removed only from
the isolated checkout, after path validation, and remain recoverable in Git.
This bounds deployment file growth as daily updates accumulate.

Runtime: Python with openpyxl, Node, Git, Vercel CLI. All child processes use
CREATE_NO_WINDOW; the existing Windows task remains launched by hidden WScript.
The refresh has an OS-owned single-run lock. Run manually with:

```powershell
C:/Python314/python.exe D:/IlMargine/return-atlas-automation/checkout/scripts/refresh-return-atlas.py --config D:/IlMargine/return-atlas-automation/config.json --dry-run
```

Omit `--dry-run` to publish a validated change. A dirty isolated checkout is
preserved for inspection, not reset. Failed pushes are retried on a subsequent
run when the checkout is otherwise clean. Existing source attribution and photo
licence credits remain part of the release.
