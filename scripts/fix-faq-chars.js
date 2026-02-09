const fs = require("fs");
const path = require("path");
const file = path.join(__dirname, "..", "docs", "faq-content.md");
let s = fs.readFileSync(file, "utf8");
// Fix mojibake: UTF-8 bytes read as Windows-1252 (â†' = E2 86 92 = →)
const replacements = [
  [/\u00e2\u2020\u2019/g, "\u2192"],   // â†' -> →
  [/\u00e2\u0153\u201c/g, "\u2713"],   // âœ" -> ✓
  [/\u00e2\u009d\u0152/g, "\u2717"],   // âœŒ -> ✗
  [/\u00e2\u0089\u00a0/g, "\u2260"],   // UTF-8 for ≠
  [/\u00e2\u2030\u00a0/g, "\u2260"],   // â‰ + nbsp -> ≠
  [/\u00e2\u0153\u2014/g, "\u2717"],   // âœ— -> ✗
];
replacements.forEach(([regex, char]) => { s = s.replace(regex, char); });
fs.writeFileSync(file, s);
console.log("Done");
