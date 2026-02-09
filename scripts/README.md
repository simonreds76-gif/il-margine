# Scripts

## Favicons (no white corners)

To regenerate favicons with a **dark background** so the browser tab icon has no white edges:

1. Install dev dependency (once):  
   `npm install`
2. Run:  
   `npm run generate-favicons`

This reads `public/favicon-256.png` (or `public/logo.png`) and writes:

- `public/favicon-dark.png` (32×32)
- `public/favicon-128-dark.png` (128×128)
- `public/favicon-256-dark.png` (256×256)

The app uses these dark-background icons so the tab has no white corners. Each image is your logo centered on background `#0f1117`. Hard-refresh or reopen the tab to see the icon.

## Vercel: do not build from `main`

So only `golden-with-speed-insights` (or other branches) trigger builds:

1. In **Vercel** → Project **Settings** → **Git** → **Ignored Build Step**, set:
   ```bash
   node scripts/vercel-ignore-main.cjs
   ```
2. If the command exits `0`, Vercel builds; if `1`, it skips. The script skips when the branch is `main`.

## Other scripts

- **create-logos** – placeholder bookmaker logos
- **download-logos** – download real bookmaker logos
