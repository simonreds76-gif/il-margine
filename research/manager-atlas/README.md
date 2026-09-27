# Current status — 27 September 2026

The notes below are a chronological development log. This status supersedes earlier blockers:

- Luis García is split into Luis García Plaza and Luis García Fernández, with explicit club/date rules. No ambiguous short-name alias is accepted globally.
- The preview contains 24,937 validated priced fixtures through 20 September 2026, matching the latest date in the existing Football Atlas release. All 242 eligible current-season fixtures in that release have now been joined to coaches. Eight other new fixtures lack usable eligible paired prices and are not silently included.
- `scripts/refresh-manager-atlas.py` is the tested, bounded, cached append step. Run it after the existing Football Atlas update; replay with `--offline` makes no requests. No API-Football subscription upgrade is required. New or conflicting identities remain pending; fatal source failures retain the last archive.
- Exact fixture reviews distinguish real interim head coaches from assistants covering touchline bans. The Forest–Leeds league match is independently verified because its provider page resolves to a different cup fixture. Evidence is in `scripts/config/manager-fixture-reviews.json`.
- The collector is working locally. Weekly cloud execution/publication is NOT installed, and this page is NOT live. The existing monthly Codex identity review is separate. Do not mistake `currentSeasonConnected` for a scheduled publisher.
- Private raw evidence and preview data must not be committed: the GitHub repository is public.

Refresh existing private archive:

```powershell
python scripts/refresh-manager-atlas.py --archive PRIVATE_DIRECTORY/data.json --state PRIVATE_CACHE
node scripts/package-manager-preview.mjs PRIVATE_DIRECTORY
```

Do not rebuild the historical seed over an appended archive. Keep the private seed, cache, identity reviews and validated result together when installing the cloud workflow. New unknown coaches need review rather than an automatic guess. Weekly publication should follow the existing Football Atlas job and preserve the last validated archive on failure, with no per-visitor provider calls.

---

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

## Astra visual revision and portrait coverage

The preview now has an original scalable Atlas mark and a consistent SVG icon system, designed with a GPT-6 Astra design agent. Typography uses system fonts; no font CDN or image-provider calls happen from the browser. The header's latest-match date is derived from `data.through`, never the page-build date. The coverage disclosure explicitly says that automatic manager refresh is not connected.

`collect-manager-portraits.py --cache PRIVATE_DIRECTORY` performs a bounded, cached Wikimedia import. It accepts exact manager names/aliases, requires a football coaching biography, resolves the biography's free lead image, and retains Commons author/licence/source metadata. Ambiguous identities and unsupported licences remain unresolved. Files are hosted locally and lazy-loaded; the unavailable state is a neutral manager pictogram, not initials or a fabricated likeness. The JSON manifest preserves evidence; the page has expandable photo credits. Image licences must remain with these files when integrating publicly.

On phones the ranking becomes a compact card layout with manager, ROI, bets, team W/D/L, profit and drawdown visible without horizontal scrolling. Detailed match and club tables remain scrollable within their own containers. Both H2H and overall rankings retain one-match samples; the minimum selector has been removed. Small samples remain labelled.

Update dependency: the existing Football Atlas workflow provides prices/results via OddsPapi, but manager history also requires verified fixture-level coach attribution. Date-only API-Football fixture lists can work although season=2026 queries fail; current five-league coach access remains unverified. No new cron, provider subscription, Vercel workload or public deployment was added by this visual revision.

## Additional provider portraits

Public coach-profile thumbnails supplement Commons where no photo was found. `portraits-provider.json` retains the exact source profile, provider ID, club-history corroboration and file checksum. These images are not described as CC-licensed. The packager merges provider records first and Commons records second, so an available credited Commons image takes priority. The page serves all images locally; there are no per-visitor provider requests.

Collectors use existing identity candidates only as leads, then require the public profile to be a coach with a matching archived club history. Ambiguous profiles, access challenges, missing photos and failed decodes are recorded rather than silently replaced with another person. Profile HTML/metadata remains in private evidence caches. Each manager ID maps to a single manifest entry, making an individual thumbnail straightforward to remove or replace.

The Luis García archive label has been flagged for identity review: its club history appears to span Luis García Plaza and Luis García Fernández. Do not attach one person's portrait until the underlying match identities are split and verified.

## Latest review schedule and visual update

Monthly review is now scheduled in Codex, first Monday at 09:00 Europe/London (automation monthly-manager-atlas-verification). It is not an installed cloud fixture publisher. The active-role register is due for review on 5 October; original checkedAt evidence dates remain unchanged. New match history still needs a verified current fixture-coach source and validated append workflow.

The selected record and same-fixture strategy cards show ROI first, profit units second. Visible examples explain stake units, profit percentages and odds-based expected wins/points. Chart includes running profit, falls from a peak, and per-bet pointer/keyboard inspection. Astra's original coach/cigar/finance SVG replaces the earlier mark.

Portrait manifests now cover 651 of 673 identities and all 72 verified active managers. The remaining 22 must not be described as complete; mixed Luis García identity and unavailable historical portraits remain open. Generic provider placeholders were rejected. Keep provider provenance separate from Commons licensing.
