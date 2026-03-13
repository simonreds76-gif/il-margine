/**
 * Crop white borders from a logo image and save as public/logo.png and public/favicon.png.
 * Usage: node scripts/crop-logo-whites.js <path-to-image>
 * Example: node scripts/crop-logo-whites.js "C:\...\il-margine-favicon-mask-clean-....png"
 */

const path = require("path");
const fs = require("fs");

async function main() {
  let sharp;
  try {
    sharp = require("sharp");
  } catch (e) {
    console.error("Missing dependency. Run: npm install sharp --save-dev");
    process.exit(1);
  }

  const sourcePath = process.argv[2];
  if (!sourcePath || !fs.existsSync(sourcePath)) {
    console.error("Usage: node scripts/crop-logo-whites.js <path-to-image>");
    console.error("Provide the full path to the logo image (e.g. from Cursor assets).");
    process.exit(1);
  }

  const publicDir = path.join(__dirname, "..", "public");
  const logoOut = path.join(publicDir, "logo.png");
  const faviconOut = path.join(publicDir, "favicon.png");

  try {
    // Trim pixels within threshold of the corner (removes white border)
    const trimmed = await sharp(sourcePath)
      .trim({ threshold: 30 })
      .png();

    const meta = await trimmed.metadata();
    const w = meta.width || 64;
    const h = meta.height || 64;

    // Logo: use at 64x64 for nav (square icon)
    await trimmed
      .clone()
      .resize(64, 64)
      .png()
      .toFile(logoOut);
    console.log("Written:", logoOut);

    // Favicon: 32x32 for browser tab / small icons
    await trimmed
      .clone()
      .resize(32, 32)
      .png()
      .toFile(faviconOut);
    console.log("Written:", faviconOut);
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
}

main();
