# AI Search Setup (ChatGPT / Perplexity)

This project now includes code-level setup to improve discovery in AI search:

- `robots.txt` allows `OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`, and `GPTBot`
- `robots.txt` blocks `/admin` and `/api` from indexing
- `robots.txt` includes `host` and sitemap
- `X-Robots-Tag: noindex, nofollow, noarchive` on `/api/*` and `/admin/*`
- `/fair-odds` is indexable by default and included in sitemap (can be disabled with `FAIR_ODDS_INDEXABLE=false`)
- `llms.txt` and `llms-full.txt` endpoints expose crawler-friendly page indexes
- GA route tracking now keeps query params (including `utm_*`)
- Custom GA event `ai_referral_landing` is sent when AI referral is detected

## Runtime flags

- `BOOKMAKERS_INDEXABLE=true|false`
- `FAIR_ODDS_INDEXABLE=true|false` (default: `true`)

## Manual steps still required (outside code)

1. Ensure CDN/WAF does not block `OAI-SearchBot` and `PerplexityBot`.
2. Allow OpenAI crawler IP ranges from:
   - `https://openai.com/searchbot.json`
3. Keep your canonical production domain in `NEXT_PUBLIC_SITE_URL`.
4. Use campaign tags on links shared in AI products, e.g.:
   - `?utm_source=chatgpt.com&utm_medium=ai_search&utm_campaign=organic`
5. Submit your sitemap in Google Search Console and Bing Webmaster Tools.

## GA events

When detected, this event is sent once per session:

- `ai_referral_landing` with params:
  - `source` (`chatgpt`, `perplexity`, `copilot`, `gemini`)
  - `via` (`utm` or `referrer`)
  - `landing_path`
  - `utm_source`, `utm_medium`, `utm_campaign` (if present)
