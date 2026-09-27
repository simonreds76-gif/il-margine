# Return Atlas: Managers

Working historical research preview, not a published route or scheduled feed.
No manager dataset is committed or deployed. Static preview uses the Football
Atlas settlement engine and flat 1u stakes, including the draw as its own outcome.

Build from the saved fixture-manager CSV with `scripts/build-manager-atlas.py
--source PATH --output PRIVATE_DIRECTORY`, then run `node
scripts/package-manager-preview.mjs PRIVATE_DIRECTORY`. Serve that directory on
loopback with Python http.server. Do not put it in public/.

26 September 2026: 24,698 matched priced fixtures, 674 normalized manager names,
2012-08-10 through 2026-05-24. League/date/club/score joins only, explicit club aliases;
no current-manager backfilling or fuzzy match acceptance. The audit lists all
exclusions. Three accent-only name aliases are reviewed; Míchel/Michel is excluded
pending stable identity resolution. Other name variants still need an identity
audit before launch; the count is not certified unique people.

Remaining launch requirements: verify fixture manager accuracy at tenure boundaries,
resolve aliases to stable manager IDs, establish a current-season append source,
review source reuse terms and complete integration under Football Atlas. The local
research UI is usable while these checks proceed. Do not claim current coverage or
automatic manager refresh. No effect on model weights, staking or production data.

UI includes H2H and opponent-club filters, all five leagues, full/single/latest3/
latest5 seasons, venue, role, price bands, three betting sides, rankings, cumulative
profit, drawdown and a progressively expanded match ledger. Units, team W/D/L and
betting W/L remain distinct.
# 27 September follow-up

The preview now uses persistent IDs from `scripts/config/manager-atlas-identities.json`. New source labels stop the build for registry review. Display-name aliases no longer change identity. Original source game IDs and labels are kept in the private build audit, not the browser payload.

Three disputed coach assignments are quarantined through `manager-atlas-exclusions.json`. Independent StatsBomb comparisons are evidence for review, not an automatic replacement source. The larger audit matched 1,916 fixtures and found 3,697 agreeing manager-side labels (including explicitly reviewed full-name variants), 132 missing/non-single comparisons and three disagreements. Excluding those three fixtures leaves 24,695 priced matches and 673 identities after the Solskjær spelling merge.

UI additions: same-fixture team/draw/opponent returns, proportional de-vig market expectations for wins and points, per-club records, observed club sequences, selected price-basis coverage and archive exclusion counts. Observed sequences are not employment tenures. Market residuals are descriptive, not predictions or causal manager ratings.

The bounded GitHub source test ran successfully but returned an entitlement blocker: the existing API-Football subscription is Free and rejects season 2026 (it suggests 2022–2024). Two requests used; no upgrade, recurring workflow or deployment enabled. Historical-only preview remains available; a current fixture-coach feed is still outstanding.
