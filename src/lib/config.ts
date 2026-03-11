// Site configuration
/** Production canonical domain. Use for sitemap, robots, canonical URLs, and OG URLs. */
export const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://ilmargine.bet";

/** Site motto / tagline. Used in footer, The Edge page, and homepage. */
export const SITE_MOTTO = "Mind the margin.";

/** Launch year for display and schema. */
export const LAUNCH_YEAR = 2026;

/** Shown in footer. */
export const LAUNCH_LABEL = "Launching March 2026";

// Stripe configuration (for future VIP access)
export const STRIPE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || "";
export const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY || "";

/** When true: /bookmakers is indexable and included in sitemap. When false (default): noindex and excluded from sitemap. */
export const BOOKMAKERS_INDEXABLE = process.env.BOOKMAKERS_INDEXABLE === "true";

/** When true (default): /fair-odds is indexable and included in sitemap. Set FAIR_ODDS_INDEXABLE=false to hide from search. */
export const FAIR_ODDS_INDEXABLE = process.env.FAIR_ODDS_INDEXABLE !== "false";

/** Google Analytics 4 measurement ID (e.g. G-XXXXXXXX). Set NEXT_PUBLIC_GA_MEASUREMENT_ID in Vercel / .env. */
export const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID ?? "";
