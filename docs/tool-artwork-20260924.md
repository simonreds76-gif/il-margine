# Tools and guides artwork — 24 September 2026

The Tools hub now uses recognisable destination artwork, including the existing Mind the Margin tube roundel. Research cards form a two-by-two desktop grid and a single column on phones. The resource library, article headers, related links, football calculator and calculator tabs use the same emblem system.

Titles, descriptions, links, canonicals, indexing directives and calculations are preserved. Artwork is decorative beside real text, with fixed dimensions and native lazy loading. No new dependencies, remote image calls, scheduled jobs or server computations were added. WebP assets are served directly, without runtime image transformation. SVG gradient IDs use React `useId` to avoid collisions.

## Assets

Built-in GPT image generation produced the three new illustrations. Originals remain in the Codex generated-images directory; website copies are resized to 320px WebP using Sharp, preserving transparency:

- `public/images/tools/penalty-v1.webp` — 29,676 bytes.
- `public/images/tools/tennis-v1.webp` — 27,954 bytes.
- `public/images/tools/football-v1.webp` — 16,648 bytes.

Existing roundel: `public/brand/mind-the-margin-roundel-v1.webp`.
The pricing, 1X2, lab, Kelly, returns, record, guide, closing-line and toolkit emblems are native SVG in `src/components/ToolEmblem.tsx`.

## Generation prompts

### Penalty

Create one premium compact website emblem for PENALTY TAKER INTELLIGENCE, an independent football research tool. NO TEXT, NO LETTERS. Square transparent background. A recognisable adult footballer in dynamic side profile taking a penalty, planted left leg and right leg striking a white football towards a small goal outline behind to the right; anatomically correct simplified athletic figure, confident clean silhouette. Bespoke polished sports editorial illustration, slightly dimensional enamel/metal finish with restrained depth, mint emerald #5fcda9 and pale mint #a4f3d6 figure, pearl white football with dark navy panels, fine emerald goal frame. All content central within 80% of square. Bold clean geometry readable at 96px, no intricate detail, no fog, no excessive glow, no platform, no badges, no words, no full scenic background. Intended for sophisticated near-black #0f1117 betting analytics website, not casino or gaming aesthetic. Single isolated symbol. Save output for use in website.

### Tennis

Single premium website emblem for Return Atlas Tennis, a historical tennis betting analysis tool. Square transparent background. Recognisable elegant tennis racket angled diagonally upward and one tennis ball at its right, compact composition. Bespoke polished enamel sports editorial illustration, restrained dimensional depth. Emerald mint racket #5fcda9 with pale mint highlights #a4f3d6, crisp pearl white strings, realistic warm chartreuse yellow tennis ball with curved white seams, navy shadows. Bold silhouette visible at 96px. All content central inside 80% of canvas, plenty of clear padding. No text, no letters, no logo wordmark, no pedestal, no glow, no scenery, no background. Suitable for a refined near-black #0f1117 financial sports research website. One isolated symbol, accurate tennis racket and ball proportions.

### Football

Create one premium compact website emblem for Return Atlas Football, historical football betting analysis. Square transparent background. A crisp pearl-white football with dark navy pentagonal panels, nestled in front of a small emerald football pitch tile in gentle three-quarter perspective, clear mint centre circle and halfway line. Bespoke polished enamel sports editorial illustration with restrained dimensional depth, emerald #5fcda9 and pale mint #a4f3d6, pearl-white, navy shadows. Bold geometry recognizable at 96px. All content central within 80% of canvas. No text, no letters, no team crests, no money, no glow, no scenery, no background. Professional near-black #0f1117 sports research website. One isolated compact emblem.
