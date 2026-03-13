# SEO audit for Google indexing

Last check: before first indexing request. All items below have been verified in the codebase.

---

## 1. Technical basics

| Item | Status | Notes |
|------|--------|------|
| **Canonical domain** | OK | `BASE_URL` from `NEXT_PUBLIC_SITE_URL` or `https://ilmargine.bet` |
| **HTTPS** | OK | Assumed in production (Vercel) |
| **robots.txt** | OK | `allow: /`, `disallow: /admin`, `sitemap: {BASE_URL}/sitemap.xml` |
| **Sitemap** | OK | `/sitemap.xml` lists all indexable URLs with priorities and changeFrequency |
| **Viewport** | OK | Set in root layout: device-width, initialScale=1, themeColor |
| **lang** | OK | `<html lang="en">` in root layout |

---

## 2. Metadata by page

| Page | Title | Description | Canonical | OG / Twitter | robots |
|------|-------|-------------|-----------|--------------|--------|
| **Home** | OK (layout) | OK (layout) | OK (layout) | OK (layout) | default |
| **Tennis tips** | OK (layout) | OK (layout) | OK | OK | default (index, follow) |
| **Player props** | OK (layout) | OK (layout) | OK | OK | default |
| **Anytime goalscorer** | OK (layout) | OK (layout) | OK | OK | default |
| **Bet builders** | OK (layout) | OK (layout) | OK | OK | default |
| **Bookmakers** | OK (layout) | OK (layout) | OK | OK | **noindex, follow** |
| **Calculator** | OK (layout) | OK (layout) | OK | OK | default |
| **Disclaimer** | OK (layout) | OK (layout) | OK | inherited | index, follow |
| **Privacy policy** | OK (page + layout) | OK (page) | OK | inherited | index, follow |
| **Cookies policy** | OK (page) | OK (page) | OK | inherited | index, follow |
| **Contact** | OK (page) | OK (page) | OK | inherited | index, follow |
| **Admin** | OK | — | — | — | noindex, nofollow |

- **Bookmakers** is kept **noindex** by choice while the featured list may change (add/remove bookmakers). Once the lineup is stable, allow indexing by setting `robots: { index: true, follow: true }` in `bookmakers/layout.tsx`.
- Policy/contact pages inherit OG/Twitter from root layout (image + site description); sufficient for indexing.

---

## 3. Sitemap coverage

All indexable routes are in the sitemap:

- `/` (priority 1, daily)
- `/tennis-tips`, `/player-props` (0.9, daily)
- `/anytime-goalscorer`, `/bet-builders` (0.8, weekly)
- `/bookmakers`, `/calculator` (0.7, monthly)
- `/disclaimer`, `/privacy-policy`, `/cookies-policy` (0.3, yearly)
- `/contact` (0.5, yearly)

**Not in sitemap (by design):**

- `/admin` — blocked in robots.txt and noindex
- `/atp-tennis` — redirects to `/tennis-tips` (no need to list)

---

## 4. Structured data

- **WebSite** (schema.org): name, url, description.
- **Organization**: name, url, logo, foundingDate.

Both are in `StructuredData.tsx` and output as JSON-LD. No BreadcrumbList yet; optional for later.

---

## 5. Content and structure

- **Single H1 per page** for main content (admin has two states; it’s noindex).
- **Images**: Logo and footer favicon have appropriate `alt`; decorative “back” favicons use `alt=""`.
- **Main content** is in `<main id="main-content">` for accessibility and clarity.

---

## 6. Before you request indexing

1. **Environment**  
   In Vercel (or your host), set `NEXT_PUBLIC_SITE_URL=https://ilmargine.bet` so all canonicals and OG URLs use the live domain.

2. **Live checks (after deploy)**
   - Open `https://ilmargine.bet/robots.txt` — should show allow /, disallow /admin, sitemap.
   - Open `https://ilmargine.bet/sitemap.xml` — should list all URLs above.
   - Use [Google Rich Results Test](https://search.google.com/test/rich-results) on the homepage to confirm structured data.
   - Use [URL Inspection](https://search.google.com/search-console) when you’re ready to request indexing.

---

## 7. Summary

- **Crawling:** robots.txt and sitemap are correct; only `/admin` is blocked.
- **Indexing:** All public pages are indexable except Bookmakers (noindex by choice until the featured list is final).
- **Metadata:** Titles, descriptions, and canonicals are set; main tips and key pages have OG/Twitter.
- **Structured data:** WebSite + Organization in place; ready for indexing once the above env and (optional) bookmakers change are done.
