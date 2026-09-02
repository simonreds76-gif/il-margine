import { promises as fs } from "node:fs";
import path from "node:path";

const roots = ["src/app/model-monitor", "src/components/model-monitor"];
const badText = /(?:\u00c3|\u00c2|\u00e2\u20ac|\ufffd|SIGNAL \?)/u;
const failures = [];

async function scan(directory) {
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      await scan(fullPath);
      continue;
    }
    if (!/\.(?:ts|tsx)$/.test(entry.name)) continue;
    const text = await fs.readFile(fullPath, "utf8");
    if (badText.test(text)) failures.push(fullPath);
  }
}

for (const root of roots) await scan(root);

if (failures.length) {
  console.error(`Monitor text encoding check failed:\n${failures.join("\n")}`);
  process.exit(1);
}

console.log("Monitor text encoding check passed.");
