/**
 * Regenerate favicons with a dark background (#0f1117) so there are no white corners
 * in the browser tab. Uses logo from public/favicon-256.png (or public/logo.png).
 *
 * Run: npm run generate-favicons
 * Requires: npm install (sharp is a devDependency)
 */

const path = require("path");
const fs = require("fs");

const publicDir = path.join(__dirname, "..", "public");

// Dark background matching site (no white edges)
const BG = { r: 15, g: 17, b: 23 }; // #0f1117

// Use -dark suffix so we don't overwrite locked favicon.png; layout points at these
// Smaller inset for 32px so the logo (and hat) is bigger and clearer in the browser tab
const SIZES = [
  { size: 32, out: "favicon-dark.png", inset: 2 },
  { size: 128, out: "favicon-128-dark.png", inset: 6 },
  { size: 256, out: "favicon-256-dark.png", inset: 16 },
];

async function main() {
  let sharp;
  try {
    sharp = require("sharp");
  } catch (e) {
    console.error("Missing dependency. Run: npm install sharp --save-dev");
    process.exit(1);
  }

  const source256 = path.join(publicDir, "favicon-256.png");
  const sourceLogo = path.join(publicDir, "logo.png");
  const source = fs.existsSync(source256) ? source256 : sourceLogo;
  if (!fs.existsSync(source)) {
    console.error("No source image found. Add public/favicon-256.png or public/logo.png");
    process.exit(1);
  }

  console.log("Source:", path.basename(source));

  // Make white/near-white pixels transparent so corners show dark background
  const { data, info } = await sharp(source)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  const nearWhite = 228; // treat brighter than this as transparent (removes white/light margins)
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    if (r >= nearWhite && g >= nearWhite && b >= nearWhite) {
      data[i + 3] = 0;
    }
  }
  const sourceNoWhite = await sharp(data, {
    raw: { width: info.width, height: info.height, channels: 4 },
  })
    .png()
    .toBuffer();

  for (const { size, out: outName, inset } of SIZES) {
    const inner = size - inset * 2;
    let pipeline = sharp(sourceNoWhite)
      .resize(inner, inner, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } });
    if (size <= 32) pipeline = pipeline.sharpen(); // crisper hat/details in tab
    const resized = await pipeline.toBuffer();

    const outPath = path.join(publicDir, outName);
    const bg = await sharp({
      create: {
        width: size,
        height: size,
        channels: 4,
        background: { ...BG, alpha: 1 },
      },
    })
      .png()
      .toBuffer();

    const outBuffer = await sharp(bg)
      .composite([{ input: resized, left: inset, top: inset }])
      .png()
      .toBuffer();

    fs.writeFileSync(outPath, outBuffer);
    console.log("Written:", outName);
  }

  console.log("Done. Favicons have dark edges (no white). Hard-refresh the browser tab to see them.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
