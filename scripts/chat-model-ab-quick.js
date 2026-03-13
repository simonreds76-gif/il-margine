#!/usr/bin/env node
/**
 * Quick A/B test: 20 runs per model.
 * node scripts/chat-model-ab-quick.js
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

async function testModel(model, n) {
  let ok = 0, fail = 0;
  let sample = null;
  for (let i = 0; i < n; i++) {
    const r = await runOne(model);
    if (r.ok) { ok++; if (!sample) sample = r.text; }
    else fail++;
  }
  return { model, ok, fail, total: n, sample };
}

function extractText(s) {
  if (!s) return "";
  const parts = [];
  for (const line of s.split("\n").filter((l) => l.startsWith("data: "))) {
    const j = line.slice(6);
    if (j === "[DONE]") break;
    try {
      const o = JSON.parse(j);
      if (o.type === "text-delta" && o.delta) parts.push(o.delta);
    } catch {}
  }
  return parts.join("");
}

async function main() {
  console.log("Quick A/B test (20 runs/model)\n");
  const results = [];
  for (const m of MODELS) {
    process.stdout.write(`${m}... `);
    const r = await testModel(m, 20);
    results.push(r);
    console.log(`${r.ok}/${r.total} OK`);
    if (r.sample) {
      const t = extractText(r.sample).slice(0, 200);
      if (t) console.log(`  Sample: ${t}...`);
    }
  }
  console.log("\n=== Summary ===");
  results.sort((a, b) => a.fail - b.fail);
  for (const r of results) {
    console.log(`${r.model}: ${r.ok}/${r.total} (${((r.ok/r.total)*100).toFixed(0)}%)`);
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
