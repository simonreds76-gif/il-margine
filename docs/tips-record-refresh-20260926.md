# Tips and public record refresh — 26 September 2026

## User-facing changes
- Shared tennis/player-props introductions with existing approved illustrated artwork and matching Return Atlas links.
- Competition cards retain full-colour marks, improve selection/focus/mobile spacing and use quantitative sample labels. Challenger uses the existing tour mark.
- Homepage uses Published betting picks and concise record copy, with metric icons and a direct record-method explanation. Earlier aggregate records remain transparently distinguished from individual logs; numerical totals are unchanged.
- Monthly bars use a common zero axis, with negative months below it. A short units/ROI example and responsive legend explain the table.
- Removed synthetic historical waves from the profit curve. One opening aggregate balance is followed only by the recorded bet sequence. Drawdown remains calculated from individual logged bets.
- Tools menu separates calculations from learning; Guides & insights naming is consistent in the homepage and footer.
- Calculator and resource query selection use small Suspense boundaries with stable fallbacks and Next search parameters. The surrounding explanations, totals, metadata and links retain static/ISR rendering. Calculator default remains Returns; explicit tool links are unchanged.

## Review and checks
Claude Sonnet reviewed the shared intro, monthly/chart styling, icons, sample labels and resource code. This was source-only; report is saved in outputs/tips-record-refresh-20260926. Addressed the filter subscription concern with Next useSearchParams, tightened the record icon, aligned chart precision and shortened Atlas accessible names. The synthetic archive curve was discovered separately and removed.

TypeScript and scoped ESLint passed. Six calculator/monthly/profit-regression tests and eight CPU-budget tests passed; ISR policy audit passed. Browser checks at 1280px and 390px verified no horizontal overflow or broken tips images, competition filtering, monthly expansion, calculator direct links/switching, resource filter persistence, and keyboard navigation of the profit chart. No console errors observed on the inspected local pages.

No new dependencies, image assets, API calls, recurring tasks, model weights or provider integrations. Hosting build/trace checks and promotion verification are recorded separately after deployment.
