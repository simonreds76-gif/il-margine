// Site configuration
/** Production canonical domain. Use for sitemap, robots, canonical URLs, and OG URLs. */
export const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://ilmargine.bet";

/** Site motto / tagline. Used in footer, The Edge page, and homepage. */
export const SITE_MOTTO = "Mind the margin.";

export const TELEGRAM_CHANNEL_URL = process.env.NEXT_PUBLIC_TELEGRAM_CHANNEL_URL || "https://t.me/IlMargineProps";

/** Launch year for display and schema. */
export const LAUNCH_YEAR = 2026;

/** Shown in footer: e.g. "Launching March 2026" while in testing, or "Launched 2026" when live. */
export const LAUNCH_LABEL = "Launching March 2026";

/** Short line for visitors who land during beta (homepage). */
export const BETA_NOTICE = "We're in beta. Full launch March 2026.";

// Stripe configuration (for future VIP access)
export const STRIPE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || "";
export const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY || "";

/** When true: /bookmakers is indexable and included in sitemap. When false (default): noindex and excluded from sitemap. */
export const BOOKMAKERS_INDEXABLE = process.env.BOOKMAKERS_INDEXABLE === "true";

/** Google Analytics 4 measurement ID (e.g. G-XXXXXXXX). Set NEXT_PUBLIC_GA_MEASUREMENT_ID in Vercel / .env. */
export const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID ?? "";
