import { spawn, spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(scriptDir, "..");
const passthroughArgs = process.argv.slice(2);
const configuredSyncTimeoutMs = Number.parseInt(process.env.ILMARGINE_HOSTED_SYNC_TIMEOUT_MS ?? "45000", 10);
const syncTimeoutMs = Number.isFinite(configuredSyncTimeoutMs) && configuredSyncTimeoutMs > 0 ? configuredSyncTimeoutMs : 45000;

function runHostedSync() {
  if (process.env.ILMARGINE_SKIP_HOSTED_SYNC === "1") {
    console.log("[dev] Hosted monitor sync skipped by ILMARGINE_SKIP_HOSTED_SYNC=1.");
    return;
  }

  if (process.platform !== "win32") {
    console.log("[dev] Hosted monitor sync skipped outside Windows. Starting Next dev.");
    return;
  }

  console.log("[dev] Syncing hosted monitor settlement artifacts before starting Next...");
  const result = spawnSync(
    "powershell.exe",
    [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      resolve(scriptDir, "sync-hosted-monitor-data.ps1"),
      "-Settlement",
    ],
    {
      cwd: repoRoot,
      stdio: "inherit",
      env: process.env,
      timeout: syncTimeoutMs,
    },
  );

  if (result.error) {
    console.warn(`[dev] Hosted monitor sync did not complete (${result.error.message}). Starting Next dev anyway.`);
    return;
  }

  if (result.status !== 0) {
    console.warn(
      `[dev] Hosted monitor sync failed with exit code ${result.status ?? "unknown"}. Starting Next dev anyway.`,
    );
  }
}

function startNextDev() {
  if (process.env.ILMARGINE_DEV_SYNC_ONLY === "1") {
    console.log("[dev] Sync-only mode complete. Next dev not started.");
    return;
  }

  const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
  const child = spawn(npmCommand, ["run", "dev:next", "--", ...passthroughArgs], {
    cwd: repoRoot,
    stdio: "inherit",
    env: process.env,
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

runHostedSync();
startNextDev();
