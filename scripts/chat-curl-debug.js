#!/usr/bin/env node
/**
 * Debug chat API: run request(s) and print full raw response (including error body).
 * Usage:
 *   node scripts/chat-curl-debug.js "who won Wimbledon the most?"
 *   node scripts/chat-curl-debug.js --payload scripts/_chat-test-payload.json
 *   node scripts/chat-curl-debug.js --payload scripts/_chat-test-payload.json --repeat 20 --stop-on-error
 *
 * Ensure dev server is running: npm run dev
 */

const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const out = {
    prompt: "",
    payloadPath: "",
    repeat: 1,
    stopOnError: false,
    url: process.env.CHAT_API_URL || "http://localhost:3000/api/chat",
  };

  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--payload" && argv[i + 1]) out.payloadPath = argv[++i];
    else if (a === "--repeat" && argv[i + 1]) out.repeat = Math.max(1, Number(argv[++i]) || 1);
    else if (a === "--stop-on-error") out.stopOnError = true;
    else if (a === "--url" && argv[i + 1]) out.url = String(argv[++i]);
    else if (!a.startsWith("--") && !out.prompt) out.prompt = a;
  }

  if (!out.prompt && !out.payloadPath) {
    out.prompt = "who won Wimbledon the most?";
  }
  return out;
}

function loadBody(opts) {
  if (opts.payloadPath) {
    const abs = path.resolve(opts.payloadPath);
    const raw = fs.readFileSync(abs, "utf8");
    const parsed = JSON.parse(raw);
    return { body: JSON.stringify(parsed), payloadLabel: abs };
  }

  return {
    body: JSON.stringify({
      messages: [{ role: "user", parts: [{ type: "text", text: opts.prompt }] }],
    }),
    payloadLabel: `prompt="${opts.prompt}"`,
  };
}

function printErrorKeys(text) {
  try {
    const json = JSON.parse(text);
    const keys = Object.keys(json);
    console.log("\nParsed error keys:", keys);
    if (json.failed_generation) console.log("failed_generation:", json.failed_generation);
    if (json.error?.failed_generation) console.log("error.failed_generation:", json.error.failed_generation);
  } catch {
    // non-JSON error body
  }
}

async function run() {
  const opts = parseArgs(process.argv);
  const { body, payloadLabel } = loadBody(opts);

  console.log("POST", opts.url);
  console.log("Payload:", payloadLabel);
  console.log("Repeat:", opts.repeat);
  console.log("Stop on error:", opts.stopOnError ? "yes" : "no");
  console.log("---");

  let hadError = false;
  for (let i = 1; i <= opts.repeat; i++) {
    if (opts.repeat > 1) console.log(`\n=== Run ${i}/${opts.repeat} ===`);

    const res = await fetch(opts.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });

    const text = await res.text();
    console.log("Status:", res.status, res.statusText);
    console.log("Headers:", Object.fromEntries(res.headers.entries()));
    console.log("---");
    console.log("Raw body:");
    console.log(text);

    if (!res.ok) {
      hadError = true;
      printErrorKeys(text);
      if (opts.stopOnError) return 1;
    }
  }

  return hadError ? 1 : 0;
}

run().catch((e) => {
  console.error("Fetch error:", e);
  process.exitCode = 1;
}).then((code) => {
  if (typeof code === "number") process.exitCode = code;
});
