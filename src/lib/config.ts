// Site configuration
/** Production canonical domain. Use for sitemap, robots, canonical URLs, and OG URLs. */
export const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://ilmargine.bet";

export const TELEGRAM_CHANNEL_URL = process.env.NEXT_PUBLIC_TELEGRAM_CHANNEL_URL || "https://t.me/yourchannelname";

// Stripe configuration (for future VIP access)
export const STRIPE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || "";
export const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY || "";

/** Google Analytics. Set NEXT_PUBLIC_GA_MEASUREMENT_ID in Vercel to enable. */
export const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "";
