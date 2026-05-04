export const PREMIUM_CHECKOUT_URL = process.env.NEXT_PUBLIC_PREMIUM_CHECKOUT_URL || "";
export const PREMIUM_CONTACT_EMAIL = "partners@ilmargine.bet";

export function premiumJoinHref() {
  if (PREMIUM_CHECKOUT_URL) return PREMIUM_CHECKOUT_URL;
  return `mailto:${PREMIUM_CONTACT_EMAIL}?subject=Il%20Margine%20Premium%20founding%20access`;
}

export function isExternalPremiumHref(href: string) {
  return href.startsWith("http://") || href.startsWith("https://") || href.startsWith("mailto:");
}
