# Return Atlas Football — implementation and release record

## Product

Return Atlas is the shared brand. Football is the edition, alongside Tennis; manager records follow after the club version is reviewed. Route: `/football-atlas`. The route is static and explicitly noindex during development. It is not linked from production navigation or the sitemap.

The football edition uses the existing public-site header/footer, typography and dark/emerald/blue colours. Its wordmark is native text; it does not reuse the tennis-ball R as a football logo. Native SVG pictograms were reviewed with the GPT design agent. Club crests are cached local assets, contain-fitted rather than cropped. Labels remain visible beside icons.

### Combined filters

League → bet selection → named-team role → season / venue / odds range / minimum matches. Calendar year is an alternative to season. All conditions intersect. Examples: away favourites at 1.50–1.80; home underdogs at 3.00–3.50. Club details inherit the selection and allow it to change without returning to the table.

Preset odds bands use `[lower, upper)`. Custom bounds are inclusive. There is no rounding before filtering. Favourite means the named team's win odds are shorter than its opponent's, even above 2.00; equal team-win prices are in All matches only. Role and odds range always describe the named team, including Back draw and Back opponent.

### Settlement

- **Back team:** its recorded 1X2 win price; draws lose.
- **Back draw:** the recorded draw price; either team winning loses.
- **Back opponent:** the opponent's recorded 1X2 win price; draws lose.

One unit staked per included fixture. Win profit = quoted decimal odds − 1; loss = −1. ROI = aggregate profit / aggregate stakes. Team W/D/L is shown independently of bet W/L. Drawdown is peak-to-trough cumulative profit, not a forecast of a bank's risk. The full chronological curve retains every included result; the ledger renders 25 rows at a time.

Team −0.5 has the same settlement as a team-win bet but can have a different price. No invented +0.5, double-chance or exchange-lay price series is exposed. A future two-leg draw/opponent dutching tool could use recorded prices and explicitly show split stakes; that would be a separate calculated strategy, not a quoted double-chance archive.

Team records overlap. Never add leaderboard profits or match counts as a portfolio. A Back draw fixture appears in both clubs' individual histories; global fixture counts are deduplicated. `uniqueDrawPortfolio` is tested for future aggregate uses.

## Reference review: SteamWatch

Read visually on 23 September 2026: https://www.steamwatch.io/team-pnl?side=fade

Useful ideas: prominent bet-direction switch, compact venue filter, sortable P/L and ROI rankings, expandable methodology. Their visible “Bet against” includes a draw or opponent win. Their explanation did not disclose how that combined price is computed, so it is not interchangeable with this build's Back opponent. The visible page had a recent collection window, league/venue/opponent controls and no visible historical season or exact odds-band controls.

This build adds season and calendar-year choices, intersecting role/venue/price filters, custom odds, club crests, current-club highlights, full historical club search, coverage counts, cumulative profit, drawdown, odds-band and season breakdowns, and a priced fixture ledger. It avoids claiming that a positive retrospective ROI proves persistent market mispricing. Manager H2H and a pre-match opponent-strength filter need their own validated data rather than today's league rank applied retrospectively.

## Data and release boundaries

`scripts/build-football-atlas.py --source <audited fixtures.json>` builds a content-hashed static archive and release metadata. No provider or database calls occur in visitor requests. Raw downloads, odds histories and acquisition reports stay outside the website tree under `../outputs/football-atlas-build-20260923/`.

Older fixtures use Football-Data's explicit Pinnacle closing columns PSCH/PSCD/PSCA. None of that feed's Pinnacle values on/after 23 July 2025 are admitted because of its published stale-feed warning. Recent fixtures use the strict Goaloo bookmaker-177 procedure from the prior audit: last strictly pre-kickoff quote, within 30 minutes, matching independent kickoff/team/date/result, consistent quote timestamps, no conflicting triplet at the selected timestamp. The small documented official kickoff corrections remain explicit. No Bet365 substitution.

Missing/ambiguous prices are retained as unpriced fixtures for coverage but excluded from returns. Coverage before role and odds filters stays visible. This is not a claim of complete career or league coverage. The ledger distinguishes Closing from Last pre-match; the latter is not represented as an exact executable closing quote.

**Public-release gate:** Football-Data's current data page restricts free data use to private individuals and distinguishes commercial use. Resolve permission/licensing or a permitted replacement archive before publishing this product. This work is a local private research preview, not a production data release. The existing automatic tennis publishing approval does not establish football data rights or enable a football refresh job.

No daily football task, provider polling job or deployment schedule is enabled by this build. A production update path needs a validated permitted recent source, immutable archive generation, meaningful-change detection, retention of the last valid release and failure alerts. Do not schedule a Vercel build for each match.

## Verification

- `node --experimental-strip-types --test scripts/tests/football-atlas.test.mjs`
- TypeScript and ESLint on the new components/page.
- Desktop 1440px, mobile 390px and 320px browser interaction checks: combined filters, detail inheritance, direction changes, ledger pagination, search, state preservation, no page/dialog horizontal overflow, no JavaScript errors.
- Final release counts, coverage reasons and build output are recorded in `../outputs/football-atlas-build-20260923/`.

The existing dirty `scripts/sync-hosted-monitor-data.ps1` is unrelated and was not changed by this task.

## Responsive design review — 23 September 2026

Claude reviewed the actual desktop/mobile/ledger screenshots and the four frontend files at the user's request. Its main findings were inner table overflow, explanation too far below the controls, ambiguous shirt/bar pictograms, and an absent visible chart key. The review is saved at `../outputs/football-atlas-redesign-20260923/claude-review.md`.

The revised preview uses five desktop ranking columns with expandable record/coverage details. Below 800px, the same semantic table becomes labelled club cards; the match ledger becomes fixture cards. Season/odds breakdowns fit the available width. No values are clipped or removed to mask overflow. Sort controls remain available on mobile above the cards.

A short original explainer and illustrative 10u-staked/2u-profit/20%-ROI ticket precede the filters. Expandable instructions, metric legends in both ranking and club views, and a visible curve/break-even key distinguish settlement, price coverage, club W/D/L and bet W/L. A consistent ticket-icon family replaces shirts; amber marks the selected bet, while profit/loss retains green/coral. Role-icon odds are illustrative pairs, not classification thresholds.

Verification now checks **inner panels and controls**, not merely document/dialog width, at 320, 390, 768, 820, 1024 and 1440px. Checks include open legends/breakdowns, long club names, odds menus, combined filters, draw/opponent returns, pagination and preserved outer filters. Results and screenshots are under `../outputs/football-atlas-redesign-20260923/`.

## Combined seasons and football wordmark

Season controls in both ranking and club views include latest 2/3/5 seasons and inclusive custom From/To ranges. Recent periods use the same latest archive season for every club, including the current partial season; a relegated club does not substitute older seasons. Exact bounds are displayed. Selecting a season period clears calendar-year filtering and vice versa. ROI is recomputed from combined profit and stakes, never an average of per-season ROI. Coverage uses the same period before role and odds filters.

The football header now uses a separate generated `wordmark-football-v1.png`, matching the existing white/emerald Return Atlas wordmark with a football in the R and a Football edition label. The original tennis asset remains intact. No live navigation changes or deployment were made.


## Public launch decision — 24 September 2026

The owner explicitly requested public deployment and indexing, confirmed no supplier permission had been obtained, and chose to proceed after the restriction was explained. This records the decision; it does not establish or imply a licence. No false supplier attribution is published. The provenance and original permission concern above remain accurate internal records.

Launch changes replace development wording, enable index/follow with a self-canonical, add static football social cards and WebApplication metadata, add the football sitemap entry, and give Return Atlas one shared desktop dropdown/mobile section for Football and Tennis. Homepage, FAQ and player-props links now describe both editions. No claim of daily football refresh is made; the archive check date and latest priced match remain explicit. Manager research is separate and is not included in this release.
