# Football Atlas automatic updates

## Current status: local tasks disabled

On 24 September 2026 the owner rejected the requirement to keep the PC running.
Both `IlMargine-Football-Atlas-Capture` and `IlMargine-Football-Atlas-Weekly`
were disabled. The archive and implementation below are retained, but this is
**not an active update schedule**. A weekly hosted archive pull is being reviewed.
The live site keeps its last validated archive meanwhile. Do not re-enable the
local schedule without a new instruction from the owner.

## Retained implementation

Enabled locally on 24 September 2026. Source code is versioned; runtime data and
configuration live outside the website under `outputs/football-atlas-automation`
in the Codex workspace. No new Vercel functions or cron jobs are introduced.

- Hidden Windows task `IlMargine-Football-Atlas-Capture` checks every ten minutes.
  A season calendar is refreshed every twelve hours. Pinnacle is queried only
  for leagues with fixtures in the next ninety minutes, except a forced audit.
  Two league-wide requests replace match-by-match odds collection.
- `IlMargine-Football-Atlas-Weekly` runs Tuesday at 09:15 local Windows time, after
  Monday fixtures. It publishes only changed data. Both tasks catch up after
  missed starts, but a sleeping/offline PC cannot collect missed closing prices.
- Pinnacle's guest API supplies one complete open full-time home/draw/away market
  per root fixture. In-play, half-time, alternate and incomplete prices are
  rejected. Original American prices are converted without early rounding.
- Use the latest captured price strictly before the independently checked kickoff
  and no more than thirty minutes before it. This remains **last pre-match**, not
  a promise of an exact bookmaker closing tick. Rescheduling invalidates earlier
  kickoff captures. No other bookmaker is substituted.
- Goaloo season calendars supply league fixtures and final scores. Their UTC+8
  timestamps are converted to UTC. Only completed matches are eligible; the same
  score must be seen in two fresh calendar observations at least an hour apart.
  All club names use an explicit reviewed mapping; new clubs require review.
- Existing public fixtures, odds and results are retained. Missing prices,
  unsettled fixtures, changed published scores, unknown clubs, duplicate IDs or
  additions over 100 matches stop automatic publication and raise an alert.
- The start timestamp defines the new forward collection window. This does not
  fabricate prices or silently backfill the older archive. Future collection
  makes no Football-Data requests and does not change historical provenance.
- Private SQLite quotes, source identifiers, health reports and logs are never
  copied to the public site. Only the immutable compressed-shape JSON archive
  and release manifest are staged from an isolated Git checkout. The current,
  previous and live archive are retained; older versions remain in Git.
- Production is promoted only after build success, archive equality checks,
  indexability checks and checks that neither the branch nor live deployment
  advanced in the meantime. Build failure leaves the old alias live. The live
  archive is checked again after promotion. Interrupted deployments can resume;
  failed builds require review instead of endless new deployments.
- Failures notify the existing private operations Telegram channel. Identical
  failures are deduplicated for 24 hours. Credentials are read from an existing
  environment file and never written into source, task arguments or logs.

Run `python scripts/football_atlas_update.py capture --config <config>` for the
normal capture; add `--force` for a bounded all-league audit. Run `publish
--dry-run` to validate without committing/deploying. Task installation is
`scripts/install-football-atlas-tasks.ps1 -ConfigPath <config>`.

This uses the already working Pinnacle guest endpoint, not a contracted API SLA.
Calendar/price coverage is explicitly checked so an HTTP 200 cannot masquerade
as complete match coverage. Availability and quotas can change.
