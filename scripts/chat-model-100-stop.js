#!/usr/bin/env node
/**
 * Run 100 requests per model, stop on first error.
 * Usage: node scripts/chat-model-100-stop.js [model]
 *   model: full model id, or "all" for all 4 (default: all)
 *
 * Example: node scripts/chat-model-100-stop.js meta-llama/llama-4-maverick-17b-128e-instruct
 */
const fs = require("fs");
const path = require("path");

const URL = process.env.CHAT_API_URL || "http://localhost:3000/api/chat";
const PAYLOAD_PATH = path.resolve(__dirname, "_chat-test-payload.json");
const MODELS = [
  "meta-llama/llama-4-maverick-17b-128e-instruct",
  "openai/gpt-oss-120b",
  "qwen/qwen3-32b",
  "llama-3.3-70b-versatile",
];

async function runOne(model) {
  const payload = JSON.parse(fs.readFileSync(PAYLOAD_PATH, "utf8"));
  payload.model = model;
  const res = await fetch(URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return { ok: res.ok, status: res.status, text: await res.text() };
}

async function testModel(model, n, stopOnError) {
  for (let i = 1; i <= n; i++) {
    const r = await runOne(model);
    if (!r.ok) {
      console.log(`\nFAIL at run ${i}: status ${r.status}`);
      console.log(r.text.slice(0, 500));
      return { model, ok: i - 1, fail: 1, total: i, failedAt: i };
    }
    if (i % 10 === 0) process.stdout.write(` ${i}`);
  }
  return { model, ok: n, fail: 0, total: n, failedAt: null };
}

async function main() {
  const arg = process.argv[2];
  const models = arg && arg !== "all" ? [arg] : MODELS;
  const n = parseInt(process.env.REPEAT || "100", 10);

  console.log(`Testing ${models.length} model(s), ${n} runs each, stop on error\n`);

  for (const model of models) {
    process.stdout.write(`${model}:`);
    const r = await testModel(model, n, true);
    console.log(`\n  Result: ${r.ok}/${r.total} OK${r.failedAt ? ` (failed at run ${r.failedAt})` : ""}`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
