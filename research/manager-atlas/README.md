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
