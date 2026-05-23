import { spawnSync } from "node:child_process";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const realProjectRoot = fs.realpathSync(projectRoot);
const require = createRequire(import.meta.url);
const nextBin = require.resolve("next/dist/bin/next");
const [command = "build", ...args] = process.argv.slice(2);

const result = spawnSync(process.execPath, [nextBin, command, ...args], {
  cwd: realProjectRoot,
  env: process.env,
  stdio: "inherit",
});

if (result.error) {
  console.error(result.error);
  process.exit(1);
}

process.exit(result.status ?? 1);
