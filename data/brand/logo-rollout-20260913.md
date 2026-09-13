# Il Margine logo rollout — 13 September 2026

Source: `newlogoilmargine-20260913.png`, supplied by the owner. 1942 × 809 pixels, sRGB, 8-bit PNG, 2,161,931 bytes. Although the PNG has an alpha channel, all pixels are opaque; the dark textured background is part of the artwork. Pixel dimensions, not its 72 DPI metadata, determine screen quality.

The source has enough resolution for the present website. An original vector export (SVG/PDF with actual paths, not a PNG embedded inside it) would be useful for larger displays and print. Upscaling this PNG would not recover additional detail. No AI redraw, invented tracing or background removal is part of this rollout.

## Exports and placements

- Full artwork with tagline: footer, default 1200 × 630 social card, publisher logo.
- Compact mask and wordmark: navigation, individual-tip Open Graph images and future Telegram player-prop image renders. Uses crops of the supplied pixels; it omits the small tagline for legibility.
- Emblem: browser tabs, Apple touch icon, home buttons, chat launcher. PNG sizes 16/32/48/128/180/192/256/512 and multi-resolution ICO.
- Existing `/logo.png`, `/favicon*.png`, `/og.png` and the previous default social-image URL also serve the new exports, preserving old incoming URLs. Current markup uses dated URLs to avoid stale browser/CDN caches.
- The original PNG is stored in the repository but excluded from Vercel uploads. Next/Image uses precompressed static exports with `unoptimized`; no additional transformation CPU is needed for these placements. Versioned assets have a one-year immutable browser/CDN cache policy.

Regenerate with `node scripts/build-site-brand-assets.mjs`. Legacy favicon commands now call the same generator and no longer remove white pixels. Generated card artwork is bundled in a small TS module, avoiding network requests from social-image functions.

Penalty-taker route content, URLs, titles, descriptions, canonical links and page-specific structured data remain unchanged. The global visual identity and organization logo are updated site-wide. Previously delivered Telegram messages and cached external previews cannot be retroactively replaced by a website deployment. Historical standalone campaign art is retained as archival content.

Asset sizes are recorded in `logo-rollout-20260913.json`.
