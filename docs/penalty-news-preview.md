# Penalty News preview

Scope: new /penalty-news hub and individual reports. Existing hierarchy pages,
models, editorial decisions, schedules and Telegram messages are unchanged.

## Factual automation

Run `python scripts/build-penalty-news.py --days 3` after the daily completed
match capture. It discovers all five supported leagues, fetches final scores
and penalty shot evidence, and generates original short reports without an
LLM call or reading a manual review queue. It retains stable event IDs and URLs,
distinguishes saves, misses and woodwork, rejects shootouts and incomplete
results, deduplicates observations, and preserves original publication dates.
Ambiguous nearby attempts are held for retake verification, not invented.
With --allow-partial, independently verified fixtures advance while failed or
ambiguous fixtures retain their last validated reports. A wholly failed capture
cannot overwrite the public JSON. Evidence, exclusions and corrections are saved.

The collector also captures the public English match commentary. Structured
penalty-won and penalty-conceded events are paired to the exact taker and attempt,
with team checks, stoppage-time handling and a boundary at the previous penalty.
Handballs never acquire a guessed foul winner. Match statistics and the score
immediately after a converted penalty add context independently of review tickets.

The 20 reports were replayed without editorial-evidence.json: 14 award details
come from structured commentary and six from automatic narrative cross-checks.
The latter require the exact attempt window, matching participants, explicit
award language and, for a foul winner, one penalty and one credited winner for
the team. A player's total cannot assign them to one of several penalties.
Handball passages must identify exactly one opponent; negated decisions are
rejected. These are evidence rules, not a claim that arbitrary prose is solved.
Unfamiliar narratives still publish confirmed outcome and match context, with
missing award details recorded in incidentCoverage and retried over eight days.
An outage cannot erase verified enrichment when the underlying facts are identical.
No generative model, manual ticket decision or additional paid service is needed.

Original reporting follows a factual lead, incident explanation and wider match
context. It does not copy third-party analysis or infer hierarchy changes from a
miss. Player statistics cover the entire appearance, including any penalty attempt.

## Preview status and launch

The collector has been executed locally against a bounded weekend and offline
replayed from its saved source packets. The manual preview workflow is provided
for repeat captures; it uploads evidence only and does not publish data.
No production daily job has been enabled by this preview.

The new penalty-news-daily.yml is ready for launch but NOT installed on the
scheduler branch. It follows completion of Goalscorer Settlement's existing
daily 08:45 UTC cycle, regardless of that workflow's conclusion. It never reads
the hierarchy review queue. It checks out the production branch and collects an
eight-day window, retaining 30-day source/correction evidence artifacts. There
is no extra cron, per-penalty deployment or per-visitor data work.

Launch checklist:
1. Approve and merge the website preview, add canonical/schema/sitemap metadata
   and remove preview-only noindex, then verify the public routes.
2. Enable config/penalty-news-publication.json on the production branch.
3. Install only penalty-news-daily.yml on golden-with-speed-insights.
4. Dispatch a dry run, then verify one real publication and the next daily run.

publish-penalty-news.py stages only src/data/penalty-news.json, refuses unrelated
changes and uses the established Atlas candidate/verify/promote approach. It
checks live ancestry, exact news revision, article routes, remote branch movement
and alias movement before promoting. An unchanged published revision avoids a
build. The production publisher has NOT been exercised from this preview; it
must pass the launch dry run and controlled first publication before being
described as operational. GitHub schedules can run late, so this is daily news
after completed matches, not a live minute-by-minute feed.

Preview pages remain noindex and absent from the sitemap. Preview navigation now
links to Penalty News under News & guides within Tools & guides, in the footer's
Picks, news & guides group, and in a card on the penalty takers directory.
At launch add canonical metadata, Article schema, sitemap entries and a
discoverable link after approval. Club pages themselves need no rewrite.

## Verification

`python -m unittest discover -s scripts/tests -p test_penalty_news.py`

`python scripts/build-penalty-news.py --offline --end-date YYYY-MM-DD --days 3 --evidence-dir PATH`

The public JSON imports are static. There are no per-visitor source requests or
frequent ISR writes. Visible cards are paginated in batches of 12.
