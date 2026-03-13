# Chat Model A/B Test Results

## Current Config (post-fallback)

- **Primary model**: `meta-llama/llama-4-maverick-17b-128e-instruct` (default)
- **Backup model**: `llama-3.3-70b-versatile` (used on parse errors)
- **Fallback**: On parse/tool error, retry once with backup before surfacing error to user

## Test Setup

- **Payload**: `scripts/_chat-test-payload.json` — "has tabilo ever reached the quarters in any grand slam?"
- **API**: Supports `model` override in request body (no server restart needed)
- **Scripts**:
  - `scripts/chat-model-ab-test.js` — full A/B test, 50 runs/model, reports OK/fail + sample
  - `scripts/chat-model-ab-quick.js` — 20 runs/model
  - `scripts/chat-model-100-stop.js` — N runs/model, stop on first error (default 100)

## Results (partial)

| Model | Runs | OK | Fail | Notes |
|-------|------|-----|------|-------|
| meta-llama/llama-4-maverick-17b-128e-instruct | 30 | 30 | 0 | 100% |
| meta-llama/llama-4-maverick-17b-128e-instruct | 50 | 50 | 0 | 100% (50-repeat test) |
| openai/gpt-oss-120b | 30 | 30 | 0 | 100% |
| openai/gpt-oss-120b | 20 | 20 | 0 | 100% (quick test) |
| qwen/qwen3-32b | — | — | — | Slower; test in progress |
| llama-3.3-70b-versatile | — | — | — | Pending |

## How to Run Full 100-Repeat Test

Ensure dev server is running (`npm run dev`), then:

```powershell
# All 4 models, 100 runs each, stop on first error
node scripts/chat-model-100-stop.js

# Single model, 100 runs
node scripts/chat-model-100-stop.js meta-llama/llama-4-maverick-17b-128e-instruct

# 50 runs per model
$env:REPEAT=50; node scripts/chat-model-100-stop.js
```

## Findings So Far

1. **llama-4-maverick** and **gpt-oss-120b** both achieved 100% success in 20–50 runs.
2. Parsing failures are intermittent; a larger sample (100+) may be needed to see differences.
3. **qwen3-32b** and **llama-3.3-70b** appear slower; tests may take longer.
4. Model override via request body works; no server restart needed between models.
