/**
 * Convert logo to favicon.ico for app directory.
 * Uses same sizing as generate-favicons.js: fit contain + inset so the wide
 * logo appears at the right size (not squished).
 * Run: node scripts/generate-favicon-ico.js
 */

const path = require("path");
const fs = require("fs");
const sharp = require("sharp");

const publicDir = path.join(__dirname, "..", "public");
const appDir = path.join(__dirname, "..", "src", "app");
const logoSource = path.join(publicDir, "logo.png");
const dest = path.join(appDir, "favicon.ico");

// Match generate-favicons.js: dark bg, inset so logo is bigger and clearer
const BG = { r: 15, g: 17, b: 23 };
const SIZE = 32;
const INSET = 2;

async function main() {
  const { data, info } = await sharp(logoSource)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  const nearWhite = 228;
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    if (r >= nearWhite && g >= nearWhite && b >= nearWhite) data[i + 3] = 0;
  }
  const sourceNoWhite = await sharp(data, {
    raw: { width: info.width, height: info.height, channels: 4 },
  }).png().toBuffer();

  const inner = SIZE - INSET * 2;
  const resized = await sharp(sourceNoWhite)
    .resize(inner, inner, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .sharpen()
    .toBuffer();

  const bg = await sharp({
    create: { width: SIZE, height: SIZE, channels: 4, background: { ...BG, alpha: 1 } },
  }).png().toBuffer();

  const png32 = await sharp(bg)
    .composite([{ input: resized, left: INSET, top: INSET }])
    .png()
    .toBuffer();

  const tmpPng = path.join(publicDir, "_favicon_tmp.png");
  fs.writeFileSync(tmpPng, png32);

  const pngToIco = (await import("png-to-ico")).default;
  const ico = await pngToIco(tmpPng);
  fs.writeFileSync(dest, ico);
  fs.unlinkSync(tmpPng);
  console.log("Written:", dest);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
