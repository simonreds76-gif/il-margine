# Penalty News

Public routes: /penalty-news and /penalty-news/[slug]. Articles link to the club hierarchy. The directory, Tools & guides navigation and footer link to the news hub. Club hierarchy content and review decisions are not changed by news publication.

## Post-match batches and daily reconciliation

Penalty News Daily follows completion of Goalscorer Hot Live Poll (the existing :10/:40 checks, 10:10–22:40 UTC) and Goalscorer Settlement's existing daily 08:45 UTC workflow, regardless of their result. It never reads the hierarchy review queue. Install the workflow on the GitHub default branch main; it checks out codex/fair-odds-daily-pitch-20260908 for the approved collector, website and publication configuration. A manual dispatch supports a dry run and either capture mode. GitHub can delay scheduled jobs. During the active window, finished matches are normally picked up by the next half-hourly check, then batch build/verification adds publication time. Matches outside that window wait for the morning reconciliation; this is not an instant live incident feed.

config/penalty-news-publication.json controls publication and the eight-day daily reconciliation window. Post-match runs check today/yesterday and at most 16 due fixtures; daily runs check at most 128. data/penalty-news/capture-state.json remembers completed fixtures including games with no penalty. Unresolved fixtures survive the date window and are retried oldest-attempt first. A follow-up after two hours and the daily recheck recover delayed commentary and corrections. Only verified checkpoint entries older than 45 days are pruned. Operational timestamps do not change the public revision or trigger a build.

The collector checks finished matches in the Premier League, Serie A, La Liga, Bundesliga and Ligue 1. Cup games and shootouts are excluded. Requested match ID, league, teams and date are cross-checked before normalization. Match score, player identity, minute and penalty outcome must be verified. Retake ambiguity is held rather than guessed. Partial capture preserves failed fixtures while allowing independently verified fixtures to advance. Unresolved source errors/penalties still fail the workflow after saving retry state and independently publishing any verified articles.

## Automatic commentary

Structured award events are linked to the exact taker, team and attempt, including stoppage time. Narrative extraction cross-checks the commentary window, roster identities and penalty-won totals. A team with several penalties cannot have a single incident assigned from a player's match total. Handballs do not acquire invented foul winners. Unsupported award details are omitted and retried; a valid report does not wait for a hierarchy review. Unchanged facts retain existing verified detail through a commentary outage.

Each report contains the factual lead, supported incident context and available full-appearance statistics. No paid LLM service or manual editorial note is required. Original published dates and URLs are preserved. Corrections are journalled.

## Publication safeguards

scripts/publish-penalty-news.py requires the production branch and a clean tracked checkout. It stages only src/data/penalty-news.json and the news-specific capture checkpoint. It checks current live ancestry, builds a candidate without changing the live alias, validates the exact news revision and article routes, then checks for branch/alias changes before promoting. An unchanged published revision skips the build, including checkpoint-only updates. The existing production branch has Git auto-deployment disabled: checkpoint commits do not create builds. A failed promotion is retried on the next run by comparing the saved article revision with the actual live page. The existing FOOTBALL_ATLAS_VERCEL_TOKEN supplies deployment access. No credentials are stored in data or evidence.

The workflow retains raw evidence, exclusions, corrections and the publication receipt for 30 days and writes a compact GitHub job summary. It adds no Telegram alerts and does not change model settings, stakes, review tickets or hierarchy orders.

## Verification and launch

Run the collector tests, full TypeScript check and scoped ESLint. Verify a fresh bounded capture, a cloud dry run and an actual publication. The production page and individual reports must have the expected revision, canonical, indexable metadata and sitemap entries. Verify the default-branch workflow is active and the morning parent workflow remains scheduled. Do not describe an installed trigger as a witnessed future scheduled run.

Commands:

    python -m unittest discover -s scripts/tests -p test_penalty_news.py
    python scripts/build-penalty-news.py --days 3 --allow-partial --evidence-dir PATH
    python scripts/publish-penalty-news.py --dry-run --mode post-match --state PATH

The pages are static. Source collection is never visitor-triggered. One batch produces at most one deployment, not one per penalty. Cards paginate in groups of 12.

