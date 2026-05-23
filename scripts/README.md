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

## Vercel: skip live-data-only builds

Vercel runs `node scripts/vercel-should-build.cjs` from `vercel.json` to avoid
rebuilding the app for hosted monitor artifact commits. The script builds by
default and skips only when every changed path is a known live-data artifact.

Vercel convention: exit `0` skips the build, exit `1` proceeds with the build.
Add `[force build]` to a commit message to build even when only data artifacts changed.

## Vercel: production promotion helper

Use `scripts/vercel-promote-production.ps1` when a verified preview deployment
needs to become the live `ilmargine.bet` deployment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/vercel-promote-production.ps1 `
  -DeploymentUrl il-margine-example-simones-projects-fb02b6e0.vercel.app
```

The helper tries `vercel promote` first. If Vercel rejects promotion because the
local CLI account is not GitHub-connected for Git deployment promotion, it falls
back to `vercel alias set <deployment> ilmargine.bet`, which is the domain move
that actually serves production traffic.

Use the globally installed Vercel CLI (`vercel`), not parallel `npx vercel`
calls. Parallel `npx` runs can corrupt npm's shared `_npx` extraction cache.

## Tennis stats test (Sackmann data)

Local test to verify the serve/return pipeline using Jeff Sackmann's tennis_atp data from GitHub:

```bash
node scripts/test-sackmann-stats.js
```

Uses 2023 and 2024 ATP match CSVs, computes serve%/return%/total by player and surface, plus vs-leftie stats. Sample matchup (Sinner vs Zverev) included. Data: CC BY-NC-SA 4.0 — for testing only.

## Other scripts

- **create-logos** – placeholder bookmaker logos
- **download-logos** – download real bookmaker logos
