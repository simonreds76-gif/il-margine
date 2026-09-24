# Tools and homepage release plan

Scope approved 24 September 2026: implement the StatsNBet-inspired recommendations excluding price-history and CLV reporting for published selections. Keep the existing manual CLV calculator.

1. Homepage: independent analysis, statistical models, specialist tools and mathematical edge; preserve the record and monthly results, add compact discovery links.
2. `/tools`: static, indexable directory grouped by pricing, research and risk. Reuse the editorial icon family and shared navigation/footer. No new dependencies, API calls or scheduled tasks.
3. `/resources/odds-value-stakes`: an original worked journey through probability, margin, EV and staking. Connect existing tools and guides in both directions.
4. `/calculator/football`: margin-adjusted 1X2 to double-chance/DNB estimates. Include selection-specific EV with draw refunds, labelled assumptions and invalid-input handling. Keep derived prices separate from Football Atlas's recorded historical prices.
5. Existing fair-odds calculator: allow EV comparison for any outcome, improve reference-price wording and link a practical example. Retain the three existing de-vig methods; do not present a new method as universally superior.
6. Discovery: global desktop/mobile navigation, footer, resource library, Football Atlas context link, canonical metadata, structured data and sitemap.
7. Verify: deterministic financial identities and refunds, existing calculator tests, TypeScript, ESLint, production build, desktop/mobile interaction and page overflow. Deploy one validated release and check the live URLs.

No provider data, published betting results, model weights or background jobs are changed. Research simulations remain distinct from the published record. No CLV performance claims are added.

## Validation

- Nine calculator tests passed, including all DNB/DC settlement identities, refunds, negative EV, home-away symmetry and invalid inputs.
- TypeScript and scoped ESLint passed. Existing ISR policy and all eight CPU-budget checks passed.
- Full production build passed with Webpack (local shared node_modules junction is unsupported by Turbopack). All three added pages were prerendered static. Vercel build will validate Turbopack with its normal dependency installation. Function trace guards passed.
- Browser verified at desktop and 390px: homepage, tools hub, guided article, mobile navigation, calculator deep link, selected-outcome EV, DNB +5% worked example, double chance and clearing an input. No horizontal overflow; no browser errors observed.
