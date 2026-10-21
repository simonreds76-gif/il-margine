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
Source failures or unresolved events fail the batch and preserve the last good
public JSON. Evidence, exclusions and corrections are stored separately.

The collector also captures the public English match commentary. Structured
penalty-won and penalty-conceded events are paired to the exact taker and attempt,
with team checks, stoppage-time handling and a boundary at the previous penalty.
Handballs never acquire a guessed foul winner. Match statistics and the score
immediately after a converted penalty add context independently of review tickets.

The initial 20 reports all have verified award details: 14 are extracted from
structured commentary; six use reviewed facts pinned to exact commentary messages
in data/penalty-news/editorial-evidence.json. These six examples are not evidence
that arbitrary narrative commentary can already be interpreted automatically.
Future unfamiliar narratives still receive the verified outcome and match context,
with missing award details recorded in incidentCoverage. Reviewed additions expire
if their supporting commentary changes. No generative model or paid service runs.

Original reporting follows a factual lead, incident explanation and wider match
context. It does not copy third-party analysis or infer hierarchy changes from a
miss. Player statistics cover the entire appearance, including any penalty attempt.

## Preview status and launch

The collector has been executed locally against a bounded weekend and offline
replayed from its saved source packets. The manual preview workflow is provided
for repeat captures; it uploads evidence only and does not publish data.
No production daily job has been enabled by this preview.

After approval, integrate the collector into the existing daily penalty capture,
independently of hierarchy review and alert delivery. That job runs on
golden-with-speed-insights, while the public website uses
codex/fair-odds-daily-pitch-20260908: promote only the validated news JSON using
the established production publisher. Do not push a research branch wholesale.
Reuse the existing schedule; batch one site refresh rather than a deployment
per penalty or per visitor. Preserve raw packets and the correction journal in
the job's evidence artifact. Verify a real scheduled capture and publication
before describing the news feed as automatically live.

Preview pages are noindex and absent from the sitemap and existing navigation.
At launch add canonical metadata, Article schema, sitemap entries and a
discoverable link after approval. Club pages themselves need no rewrite.

## Verification

`python -m unittest discover -s scripts/tests -p test_penalty_news.py`

`python scripts/build-penalty-news.py --offline --end-date YYYY-MM-DD --days 3 --evidence-dir PATH`

The public JSON imports are static. There are no per-visitor source requests or
frequent ISR writes. Visible cards are paginated in batches of 12.
