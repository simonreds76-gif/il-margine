# AI Search Setup (ChatGPT / Perplexity / Claude / Grok)

This project now includes code-level setup to improve discovery in AI search:

- `robots.txt` has a wildcard allow rule (`User-agent: *`) plus explicit rules for OpenAI, Perplexity, and Claude bots
- `robots.txt` blocks `/admin` and `/api` from indexing
- `robots.txt` includes `host` and sitemap
- `X-Robots-Tag: noindex, nofollow, noarchive` on `/api/*` and `/admin/*`
- `/fair-odds` is indexable by default and included in sitemap (can be disabled with `FAIR_ODDS_INDEXABLE=false`)
- `llms.txt` and `llms-full.txt` endpoints expose crawler-friendly page indexes
- GA route tracking now keeps query params (including `utm_*`)
- Custom GA event `ai_referral_landing` is sent when AI referral is detected

## Runtime flags

- `FAIR_ODDS_INDEXABLE=true|false` (default: `true`)

## Manual steps still required (outside code)

1. **Deploy** the `golden-with-speed-insights` branch to production (Vercel → promote preview or set production branch).
2. **Vercel Firewall / WAF** – Allow AI crawlers (configure in Vercel Dashboard → Project → Settings → Firewall):
   - Add a **Custom Rule** with action **Bypass** for requests where:
     - `User-Agent` contains `OAI-SearchBot` OR
     - `User-Agent` contains `ChatGPT-User` OR
     - `User-Agent` contains `GPTBot` OR
     - `User-Agent` contains `PerplexityBot` OR
     - `User-Agent` contains `ClaudeBot` OR
     - `User-Agent` contains `Claude-SearchBot` OR
     - `User-Agent` contains `Claude-User`
   - Grok/xAI note: no stable public crawler user-agent is documented by xAI. Keep default bot traffic allowed unless you have a verified reason to block it.
   - Or: add **System Bypass** for OpenAI crawler IP ranges (see `searchbot.json` below).
3. **OpenAI crawler IP list** – Fetch from `https://openai.com/searchbot.json` and add to your WAF allowlist if using IP-based rules. Current prefixes (as of 2026-01):
   - 104.210.140.128/28, 135.234.64.0/24, 172.182.193.224/28, 172.182.193.80/28, 172.182.194.144/28, 172.182.194.32/28, 172.182.195.48/28, 172.182.209.208/28, 172.182.211.192/28, 172.182.213.192/28, 172.182.224.0/28, 172.203.190.128/28, 20.14.99.96/28, 20.168.18.32/28, 20.169.6.224/28, 20.169.7.48/28, 20.169.77.0/25, 20.171.123.64/28, 20.171.53.224/28, 20.25.151.224/28, 20.42.10.176/28, 4.227.36.0/25, 40.67.175.0/25, 40.90.214.16/28, 51.8.102.0/24, 74.7.175.128/25, 74.7.228.0/25, 74.7.228.128/25, 74.7.229.0/25, 74.7.229.128/25, 74.7.230.0/25, 74.7.241.128/25, 74.7.242.128/25, 74.7.243.0/25, 74.7.244.0/25
4. Keep your canonical production domain in `NEXT_PUBLIC_SITE_URL`.
5. Use campaign tags on links shared in AI products, e.g.:
   - `?utm_source=chatgpt.com&utm_medium=ai_search&utm_campaign=organic`
6. Submit your sitemap in Google Search Console and Bing Webmaster Tools.

## GA events

When detected, this event is sent once per session:

- `ai_referral_landing` with params:
  - `source` (`chatgpt`, `perplexity`, `claude`, `copilot`, `gemini`, `grok`)
  - `via` (`utm` or `referrer`)
  - `landing_path`
  - `utm_source`, `utm_medium`, `utm_campaign` (if present)
