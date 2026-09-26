# Tennis Matchup Lab

Public route: `/tennis-matchup`. Approved for publication on 26 September 2026.

The public page serves a dated, validated snapshot. It is not connected to the
Return Atlas automatic publisher yet. Do not imply that a daily update occurred
without rebuilding, validating and deploying a new release.

## Release a data update

1. Run `scripts/build-tennis-matchup.py` against the current validated Atlas and
   local results/statistics exports, writing to a private temporary directory.
2. Run `python scripts/package-tennis-matchup.py --snapshot PATH/data.json`.
   It publishes an allowlisted set of match fields and versioned player shards.
   It does not publish the raw input tables, internal audit or local file paths.
3. Run the builder, packager and public fixture tests; review the release date,
   record counts and changed matches before committing the static data release.
4. Deploy a candidate, verify search, filters, H2H orientation and the snapshot
   version, then promote it. Retain the last good release if validation fails.

The homepage does not download the archive. The comparison first loads a small
player index, then downloads only the selected players' records. Data URLs are
versioned so a cached player file cannot mix with another release. Changing an
input cancels display of an older in-flight comparison.

## Visual assets and code

`identity.mjs` contains the original GPT-6 Astra vector icon family. The original
court image is retained under `assets/`; `build-tennis-matchup-assets.mjs` creates
a compressed WebP, static share image and page-scoped CSS. Source styles remain
scoped to the new route when packaged and do not alter other site tables.

The public interactive module is under `src/app/tennis-matchup/runtime` and is
isolated to its own DOM root. Core arithmetic is unchanged except the unused
research resampling calculation is omitted from the public rendering path.

The site FAQs explain actual wins, expected wins, excess wins, the percentage-
point gap, statistical coverage and the distinction from betting returns.
No model weights or fair-odds prediction pipeline are modified by this page.
