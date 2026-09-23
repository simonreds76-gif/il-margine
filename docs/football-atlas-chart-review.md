# Return Atlas chart and branding review — 24 September 2026

Local preview changes only. Football remains noindex and absent from public navigation/sitemap.

## Verified scope

The audited fixture archive contains 25,491 completed domestic league fixtures: La Liga 5,389; Premier League 5,370; Serie A 5,370; Ligue 1 5,042; Bundesliga 4,320. It does not mix in domestic cups or European competitions. Prices are available for 25,237 fixtures. Coverage is now explicit in the hero, guide, chart, methodology, homepage feature and FAQ.

## Design review and changes

Claude reviewed actual desktop/mobile chart screenshots and relevant frontend source. Review saved outside the app in `outputs/football-atlas-chart-20260923/claude-review.md`.

Implemented readable HTML axes, round zero-inclusive ticks, neutral unsmoothed match-by-match line, mint/coral area above/below break-even, optional synchronized underwater drawdown strip, pointer capture, keyboard slider and a match readout. No prices, records, staking assumptions or filters changed. The horizontal axis is bet order, not elapsed time. All figures are profit units, not bankroll returns.

Reused existing editorial emblems for methodology/legend and existing sport emblems for homepage headings. Tennis heading and its main CTA link to the live tennis route. Football retains honest preview status without a public link.

## Tennis logo

Generated with the built-in image-generation tool using the original tennis logo as edit target and the football logo as layout reference. Saved as `public/return-atlas/assets/wordmark-tennis-v2.png`. The homepage, tennis hero and daily export manifest use it; the exporter takes the product asset rather than the old research-directory logo. Existing pre-rendered social share cards are unchanged.

Final generation prompt:

> Edit target Image 1: existing Return Atlas TENNIS logo. Image 2 is style/layout reference for matching sport suffix. Preserve exact identity of Image 1: white Return, emerald mint Atlas, tennis-ball seam inside R, typography and clean flat vector-like finish. Add the word TENNIS in uppercase widely spaced mint letters UNDER Atlas, right aligned, in exactly the same visual position/style/proportion as FOOTBALL in reference Image 2. Single completed logo only, no alternative icons, no mockup. Transparent background with real alpha. Keep wide 3:1 canvas with generous consistent padding matching Image 2 (2172x724 reference), entire logo and subtitle inside canvas. No powered by text, no glow, no shadows, no other text. Text verbatim Return Atlas and TENNIS.

## Validation

- 12 core tests including running-peak drawdown, recovery, all-win/all-loss paths and flat/tiny-domain axis checks.
- Nice's displayed curve/maximum drawdown independently recomputed from the audited fixture archive.
- Browser checks for pointer/keyboard inspection, drawdown visibility, negative returns, resetting the cursor on filter changes, page/inner-panel widths at 320, 390, 768 and 1440px, homepage navigation and matching tennis assets.
- Daily exporter tested against a temporary one-match fixture; retained the new logo bytes and manifest URL without an old source logo.
- Scoped ESLint and production build pass. No chart package, provider calls or additional Vercel function introduced.

Evidence and screenshots: `outputs/football-atlas-chart-20260923/` in the parent workspace.
