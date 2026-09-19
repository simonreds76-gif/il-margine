# Return Atlas release

`/return-atlas` and `/return-atlas/credits` are statically generated. The shared GlobalNav includes the product on desktop and mobile. No provider API, database, scheduled polling, or runtime image optimisation is needed for this feature.

The browser loads a compact immutable index and calculates filters locally. Event names and scores are loaded from one immutable file per player when their record is opened. Fetches time out after 20 seconds and offer retry. An unmounted component aborts outstanding requests.

## Updating the archive

The audited input is currently the sibling workspace's `outputs/atp-returns-design-20260919/preview` directory (`real-data.mjs`, `portraits.mjs`, logo and credits). This is an offline release input, not a provider connection.

After auditing refreshed source files, run:

```powershell
node scripts/build-return-atlas.mjs ../outputs/atp-returns-design-20260919/preview YYYY-MM-DD
node --test scripts/tests/return-atlas.test.mjs
npm run build
```

Pass the actual archive-check date, never a fabricated current date. `checkedAt` is distinct from `through`, the latest accepted match. The exporter generates content-addressed assets and `src/data/return-atlas-release.json`. Publish both in the same deployment. Do not overwrite old immutable asset paths with changed data. This exporter does not itself refresh/download source data or establish an automatic update schedule.

On 19 September 2026, the latest accepted ATP main-tour singles result was 13 September. The price source contained later Challenger/ITF/team events through 19 September and OnCourt results extended through 18 September; neither supplied an eligible completed main-tour match after the 13th. Display both dates explicitly.

## Calculation and presentation rules

- ATP main draws only, completed matches, paired Pinnacle prices. Retirements, walkovers, qualifying, team events and unresolved matches are excluded.
- Favourite/underdog refers to the named player's price relative to their opponent, not a fixed 2.00 threshold. Equal prices enter only All matches.
- Bet against uses the opponent's actual odds. Role remains relative to the named player.
- Each player panel offers independent side and role controls. Role cards show all/favourite/underdog ROI and sample counts together; changing either control updates the chart and ledger without closing the panel.
- Keep last pre-match prices distinguishable from supplemental archived prices/captures. Never silently relabel all archives as closing prices.
- Detailed source and image attribution lives on `/return-atlas/credits`; the match ledger uses plain price-timing labels.
- The role selector now follows a Claude-reviewed GPT component design: crossed rackets for all matches, a racket with a centred ball for favourite, and a racket with an outside ball for underdog. These are decorative tennis mnemonics, not definitions of odds or playing style. Native SVG and visible labels replace all earlier raster role icons, adding no icon image requests. The 138px mobile cards show role, ROI and sample count together, with a mint outline and check for selection. Consultation, exact GPT prompt and generated mockup are in the sibling workspace's `outputs/atp-returns-design-20260919/claude-guided-role-design.md` and `.png`.

## Validation

The two historical leader cards reuse the player portrait component, including its image-error fallback. Photos are 64×74px on desktop and 56×64px on mobile; names, ROI and sample counts remain native text. Opening a highlight selects that player's corresponding price role.

Production build and CPU/ISR policy checks passed on 19 September. Fourteen calculation/archive tests passed, including independent accounting for all 542 players on both sides. Responsive browser checks covered 360/390px layouts, search, filters, pagination, role/side switching, full ledger expansion and shared navigation. These are responsive Chromium checks, not physical iPhone/Safari certification.
