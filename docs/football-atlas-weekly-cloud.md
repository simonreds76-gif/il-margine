# Weekly Football Return Atlas

The GitHub workflow runs Tuesday at 08:35 UTC (09:35 British Summer Time). It checks out the current release branch and runs on a GitHub runner; the laptop is not required. The workflow must also exist on `main` for GitHub's schedule to execute.

## Data and validation

- Five OddsPapi tournament requests cover the Premier League, Serie A, La Liga, Bundesliga and Ligue 1. The historical endpoint supplies Pinnacle regulation-time home/draw/away prices for newly completed matches. It is throttled to one request per 5.2 seconds.
- Goaloo season calendars provide final results. A match must also be finished in OddsPapi, at least six hours old, and reconcile by competition, explicitly mapped teams and kickoff. This cross-check confirms completion and identity, not two independent score feeds. Published score corrections require review.
- Select the last active state strictly before the earlier scheduled/credible actual kickoff. Suspended, missing, conflicting, implausible or uncertain-timing prices fail validation. These observations are labelled **last pre-match**, not certified exchange closing prices.
- Reconcile all completed fixtures in both directions; a partial provider response cannot silently drop matches. Inspect up to a 35-day recovery window. Never substitute another bookmaker or rewrite earlier published results/prices.
- Cache downloaded history privately in GitHub Actions. Retain provenance and SHA-256 of the full provider response. These files are not deployed with the website.

## Publication

Only changed, validated data creates a release commit and candidate Vercel deployment. Verify the candidate page is indexable, uses the correct archive and serves exactly the validated JSON before promotion. Check live ancestry, branch head and live alias to avoid overwriting another release. Preserve the current and previous archive files; remove only older content-addressed Atlas archive files. No change means no Vercel build.

A failed validation keeps the previous public archive. A failure after promotion is reported as such for investigation. The existing operations Telegram bot sends a link to the failed GitHub run. The workflow keeps validation reports for 30 days.

Required repository secrets: `ODDSPAPI_API_KEY`, `FOOTBALL_ATLAS_VERCEL_TOKEN` (project-scoped credential), and the existing `OPS_ALERT_TELEGRAM_BOT_TOKEN` / `OPS_ALERT_TELEGRAM_CHAT_ID`. Never store secrets in code, cache or reports. Rotate the Vercel token before expiry.

Manual `workflow_dispatch` defaults to `dry_run=true`: download and validate without committing, building or promoting. Disable the workflow in GitHub Actions to stop scheduled updates. The older Windows capture tasks remain disabled.

## Initial verification, 24 September 2026

Live read-only run reconciled 61 completed fixtures from 14 September: EPL 11, Serie A 13, La Liga 19, Bundesliga 9, Ligue 1 9. Five fixture requests, no new archive rows. Separate real-history research validated 48 completed fixtures across all five leagues. Unit tests exercise strict pre-start prices, suspension, draw orientation, missing fixtures, encoding, immutable merges and idempotence. Activation and a hosted run must be confirmed separately.
