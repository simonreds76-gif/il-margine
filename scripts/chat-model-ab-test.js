#!/usr/bin/env node
/**
 * A/B test Groq models for chat API: failure rate + sample response.
 * Usage:
 *   node scripts/chat-model-ab-test.js [--repeat N] [--url URL]
 *
 * Tests: llama-4-maverick, gpt-oss-120b, qwen3-32b, llama-3.3-70b
 * Passes model in request body (API supports model override).
 * Ensure dev server is running: npm run dev
 */

const fs = require("fs");
const path = require("path");

const REPEAT = parseInt(process.env.REPEAT || "50", 10);
const URL = process.env.CHAT_API_URL || "http://localhost:3000/api/chat";
const PAYLOAD_PATH = path.resolve(__dirname, "_chat-test-payload.json");

const MODELS = [
  "meta-llama/llama-4-maverick-17b-128e-instruct",
  "openai/gpt-oss-120b",
  "qwen/qwen3-32b",
  "llama-3.3-70b-versatile",
];

function loadPayload() {
  const raw = fs.readFileSync(PAYLOAD_PATH, "utf8");
  return JSON.parse(raw);
}

async function runOne(model, runIndex) {
  const payload = loadPayload();
  payload.model = model;
  const res = await fetch(URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await res.text();
  return { ok: res.ok, status: res.status, text, runIndex };
}

async function testModel(model, repeat) {
  const results = [];
  let firstSuccessText = null;
  for (let i = 1; i <= repeat; i++) {
    const r = await runOne(model, i);
    results.push(r);
    if (r.ok && !firstSuccessText) {
      firstSuccessText = r.text;
    }
  }
  const okCount = results.filter((r) => r.ok).length;
  const failCount = results.length - okCount;
  const firstFail = results.find((r) => !r.ok);
  return {
    model,
    okCount,
    failCount,
    total: results.length,
    firstFailRun: firstFail?.runIndex ?? null,
    firstSuccessText: firstSuccessText ? firstSuccessText.slice(0, 800) : null,
  };
}

function extractTextFromStream(s) {
  if (!s || typeof s !== "string") return "";
  const lines = s.split("\n").filter((l) => l.startsWith("data: "));
  const parts = [];
  for (const line of lines) {
    const json = line.slice(6);
    if (json === "[DONE]") break;
    try {
      const obj = JSON.parse(json);
      if (obj.type === "text-delta" && obj.delta) parts.push(obj.delta);
    } catch {}
  }
  return parts.join("");
}

async function main() {
  const repeat = parseInt(process.argv.find((a) => a.startsWith("--repeat="))?.split("=")[1] || process.env.REPEAT || "50", 10);
  const url = process.argv.find((a) => a.startsWith("--url="))?.split("=")[1] || URL;

  console.log("Chat model A/B test");
  console.log("URL:", url);
  console.log("Repeat per model:", repeat);
  console.log("Payload:", PAYLOAD_PATH);
  console.log("---\n");

  const summaries = [];

  for (const model of MODELS) {
    console.log(`Testing: ${model}`);
    const summary = await testModel(model, repeat);
    summaries.push(summary);
    console.log(`  OK: ${summary.okCount}/${summary.total} | Failures: ${summary.failCount} | First fail at run: ${summary.firstFailRun ?? "none"}`);
    if (summary.firstSuccessText) {
      const extracted = extractTextFromStream(summary.firstSuccessText);
      const preview = extracted.slice(0, 300).replace(/\r?\n/g, " ");
      console.log(`  Sample: ${preview}${extracted.length > 300 ? "..." : ""}`);
    }
    console.log("");
  }

  console.log("=== SUMMARY ===");
  const byFails = [...summaries].sort((a, b) => a.failCount - b.failCount);
  for (const s of byFails) {
    const pct = ((s.okCount / s.total) * 100).toFixed(1);
    console.log(`${s.model}: ${s.okCount}/${s.total} (${pct}%)`);
  }
}

main().catch((e) => {
  console.error("Error:", e);
  process.exitCode = 1;
});
