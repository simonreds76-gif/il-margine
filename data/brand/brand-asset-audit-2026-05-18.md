# Brand Asset Audit - 2026-05-18

## Scope

Recolour the active Il Margine brand assets to the new mint-green direction while preserving the existing logo structure.

Primary brand green: `#57d196`
Secondary glow: `#34d399`
Dark background: `#05080b`

## Active References Checked

- `src/components/GlobalNav.tsx` uses `/logo.png`
- `src/components/Footer.tsx`, `src/components/PageHomeLink.tsx`, and `src/components/ChatWidget.tsx` use `/favicon.png`
- `src/components/StructuredData.tsx` uses `/logo.png`
- Most route metadata uses `/og.png`
- Root metadata previously used `/banner.png`; it now uses `/og.png` for correct 1200x630 social-card dimensions
- `/bookmakers` and World Cup penalty pages still use `/banner.png`, which has been recoloured in-place

## Files Replaced

- `public/logo.png` -> recoloured 256x73 header logo
- `public/favicon.png` -> recoloured 32x32 square icon, with legacy white corner artefacts removed
- `public/favicon-128.png` -> recoloured 128x128 square icon, with legacy white corner artefacts removed
- `public/favicon-256.png` -> recoloured 256x256 square icon, with legacy white corner artefacts removed
- `public/banner.png` -> recoloured 1522x579 banner
- `public/og.png` -> recoloured and resized 1200x630 social card

The uploaded zip was used as colour direction only. The shipped assets preserve the existing Il Margine logo structure rather than adopting the alternate redesigned mark from the zip.

## Metadata Updated

- `src/app/layout.tsx` now declares 32, 128, and 256 favicon sizes
- Apple touch icon now points to `favicon-256.png`
- Root OpenGraph/Twitter image now points to `og.png` with 1200x630 dimensions

## Intentionally Not Changed

- `public/banner-mind-the-margin.png`: no active code reference found in `src/`; left unchanged to avoid altering unused archival artwork without a direct replacement.
- Market/team/bookmaker/league logos: independent third-party marks, not Il Margine brand assets.
- Tailwind `emerald-*` UI classes: left intact because they encode generic positive/status semantics across the app. Only the global `--accent` and selection colour were updated to `#57d196`.

## Risk

Low. The replacement files keep the same filenames and expected dimensions for the active site assets. No route logic, betting logic, data pipeline, or public signal code changed.
