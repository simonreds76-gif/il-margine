#!/usr/bin/env node
/* eslint-disable no-console */
const http = require("http");

function parseArgs(argv) {
  const out = {
    host: "localhost",
    port: 3000,
    path: "/api/chat",
    timeoutMs: 60000,
    only: "",
    verbose: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--host" && argv[i + 1]) out.host = argv[++i];
    else if (a === "--port" && argv[i + 1]) out.port = Number(argv[++i]) || out.port;
    else if (a === "--path" && argv[i + 1]) out.path = argv[++i];
    else if (a === "--timeout" && argv[i + 1]) out.timeoutMs = Number(argv[++i]) || out.timeoutMs;
    else if (a === "--only" && argv[i + 1]) out.only = String(argv[++i]).toLowerCase();
    else if (a === "--verbose") out.verbose = true;
  }
  return out;
}

function sendChat({ host, port, path, timeoutMs, messages }) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ messages });
    const req = http.request(
      {
        hostname: host,
        port,
        path,
        method: "POST",
        headers: { "Content-Type": "application/json" },
      },
      (res) => {
        let raw = "";
        res.on("data", (chunk) => {
          raw += chunk;
        });
        res.on("end", () => {
          if (res.statusCode !== 200) {
            resolve({
              ok: false,
              status: res.statusCode,
              text: raw.slice(0, 1000),
              error: `HTTP ${res.statusCode}`,
            });
            return;
          }
          const lines = raw.split("\n");
          let text = "";
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const payload = line.slice(6);
            if (payload === "[DONE]") break;
            try {
              const obj = JSON.parse(payload);
              if (obj.type === "text-delta" && typeof obj.delta === "string") {
                text += obj.delta;
              }
            } catch {
              // ignore partial/other frames
            }
          }
          resolve({ ok: true, status: 200, text: text.trim(), raw });
        });
      }
    );
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error(`timeout after ${timeoutMs}ms`));
    });
    req.on("error", (err) => {
      resolve({ ok: false, status: 0, text: "", error: err.message });
    });
    req.write(body);
    req.end();
  });
}

function hasMatch(text, pattern) {
  if (pattern instanceof RegExp) return pattern.test(text);
  return String(text).includes(String(pattern));
}

function validate(text, expectAll = [], rejectAny = [], expectAny = []) {
  const misses = [];
  const hitsReject = [];
  const anyMiss = [];
  for (const p of expectAll) {
    if (!hasMatch(text, p)) misses.push(String(p));
  }
  for (const p of rejectAny) {
    if (hasMatch(text, p)) hitsReject.push(String(p));
  }
  if (expectAny.length) {
    const ok = expectAny.some((p) => hasMatch(text, p));
    if (!ok) {
      for (const p of expectAny) anyMiss.push(String(p));
    }
  }
  return {
    pass: misses.length === 0 && hitsReject.length === 0 && anyMiss.length === 0,
    misses,
    hitsReject,
    anyMiss,
  };
}

function mkUser(text) {
  return { role: "user", parts: [{ type: "text", text }] };
}

function mkAssistant(text) {
  return { role: "assistant", parts: [{ type: "text", text }] };
}

function buildCases() {
  return [
    {
      id: "h2h_pair_tiafoe_zverev",
      messages: [mkUser("tiafoe vs zverev h2h")],
      expectAll: [/historical H2H:/i, /1-8/, /Surface split:/i],
      rejectAny: [/Top ATP spots today:/i],
    },
    {
      id: "h2h_today_all_matches",
      messages: [mkUser("what about the h2h for all today's matches?")],
      expectAll: [/Today's ATP main-draw H2H:/i],
      rejectAny: [/Top ATP spots today:/i],
    },
    {
      id: "tournament_underdogs_iw",
      messages: [mkUser("How do underdogs do at Indian Wells?")],
      expectAll: [/BNP Paribas Open/i, /underdogs ROI/i, /favourites ROI/i],
      rejectAny: [/Top ATP underdog spots today/i],
    },
    {
      id: "tournament_underdogs_iw_last_year_direct",
      messages: [mkUser("How do underdogs do at Indian Wells last year?")],
      expectAll: [/BNP Paribas Open/i, /\(2025\)/, /underdogs ROI/i, /favourites ROI/i],
      rejectAny: [/2022-2025/, /Top ATP underdog spots today/i],
    },
    {
      id: "tournament_underdogs_iw_followup_last_year",
      messages: [
        mkUser("How do underdogs do at Indian Wells?"),
        mkAssistant("BNP Paribas Open (2022-2025): underdogs ROI -11.6% (110/354), favourites ROI +3.6% (244/354) on 354 matches."),
        mkUser("last year?"),
      ],
      expectAll: [/BNP Paribas Open/i, /\(2025\)/, /underdogs ROI/i, /favourites ROI/i],
      rejectAny: [/2022-2025/],
    },
    {
      id: "underdog_today",
      messages: [mkUser("best underdog bet today?")],
      expectAll: [/Top ATP underdog spots today/i],
      rejectAny: [/Best ATP moneyline value spots today/i],
    },
    {
      id: "value_today",
      messages: [mkUser("best value bet of the day?")],
      expectAll: [/Best ATP moneyline value spots today/i, /Pin/i, /fair/i],
      rejectAny: [/handicap/i],
    },
    {
      id: "tips_split_value_then_favs",
      messages: [mkUser("best tips for today?")],
      expectAll: [/Best value \(Pinnacle vs fair, ML\):/i, /Best favourites:/i],
      rejectAny: [],
    },
    {
      id: "who_won_rg_last_year",
      messages: [mkUser("who won roland garros last year?")],
      expectAll: [/2025/i, /French Open|Roland\W*Garros/i],
      rejectAny: [/I don't have access/i],
    },
    {
      id: "rg_qf_followup_context",
      messages: [
        mkUser("who won roland garros last year?"),
        mkAssistant("Carlos Alcaraz won the 2025 French Open."),
        mkUser("who did he beat in the quarters?"),
      ],
      expectAll: [/Tommy Paul/i, /QF|quarter/i, /2025/i],
      rejectAny: [/I couldn't find/i, /I don't have access/i],
    },
    {
      id: "h2h_pair_rune_cobolli",
      messages: [mkUser("Rune vs Cobolli H2H")],
      expectAll: [/historical H2H:/i, /Surface split:/i, /Rune/i, /Cobolli/i],
      rejectAny: [/Top ATP spots today:/i],
    },
    {
      id: "big_servers_fritz_surface_split",
      messages: [mkUser("How does Fritz do against big servers?")],
      expectAll: [/Fritz vs big servers/i, /By surface:/i, /Clay/i, /Hard/i],
      rejectAny: [/Top ATP spots today:/i, /I don't have/i],
    },
    {
      id: "pick_against_fonseca_specific",
      messages: [mkUser("what's your pick today against Fonseca?")],
      expectAll: [],
      expectAny: [/Fonseca/i, /not listed in today's ATP main-draw fixtures/i],
      rejectAny: [/Top ATP spots today:/i, /Best ATP moneyline value spots today:/i],
    },
    {
      id: "tip_michelsen_humbert_specific",
      messages: [mkUser("Michelsen vs Humbert today? What's your tip?")],
      expectAll: [/Michelsen/i, /Humbert/i],
      expectAny: [/not listed in today's ATP main-draw fixtures/i, /I'd lean/i],
      rejectAny: [/Top ATP spots today:/i, /Best ATP moneyline value spots today:/i],
    },
    {
      id: "rg_winner_and_qf_single_turn",
      messages: [mkUser("who won roland garros last year and who did he beat in the quarters?")],
      expectAll: [/French Open|Roland\W*Garros/i, /quarter|QF/i],
      expectAny: [/Tommy\s*Paul/i, /beat|smashed|defeated|dismantled/i],
      rejectAny: [/I couldn't find/i, /I don't have access/i],
    },
    {
      id: "underdogs_iw_followup_context_only",
      messages: [
        mkUser("How do underdogs do at Indian Wells?"),
        mkAssistant("BNP Paribas Open (2022-2025): underdogs ROI -11.6% (110/354), favourites ROI +3.6% (244/354) on 354 matches."),
        mkUser("last year?"),
      ],
      expectAll: [/BNP Paribas Open/i, /underdogs ROI/i, /favourites ROI/i],
      expectAny: [/\(2025\)/, /2025/],
      rejectAny: [/Top ATP underdog spots today/i, /Could you clarify/i],
    },
    {
      id: "tournament_best_record_followup_there",
      messages: [
        mkUser("how do favourites do at delray beach?"),
        mkAssistant("Delray Beach Open (2022-2025): underdogs ROI -9.8% (39/103), favourites ROI -2.1% (64/103) on 103 matches."),
        mkUser("who has the best record there?"),
      ],
      expectAll: [/Delray/i],
      expectAny: [/Best record there by titles/i, /best performer by titles/i],
      rejectAny: [/Could you clarify/i, /Top ATP spots today/i],
    },
    {
      id: "best_performer_queens_past4y",
      messages: [mkUser("who's the best performer at the Queen's in the past 4 years?")],
      expectAll: [/Queen/i],
      expectAny: [/best performer by titles/i, /I don't have (?:winners|past-winner) data for Queen/i],
      rejectAny: [/Could you clarify/i, /Top ATP spots today/i, /Rate limit/i],
    },
  ];
}

async function run() {
  const cfg = parseArgs(process.argv);
  const cases = buildCases().filter((c) => !cfg.only || c.id.toLowerCase().includes(cfg.only));
  if (!cases.length) {
    console.log("No matching test cases.");
    process.exit(2);
  }

  console.log(`Chat regression: ${cases.length} cases -> http://${cfg.host}:${cfg.port}${cfg.path}`);
  let passed = 0;
  let failed = 0;
  const started = Date.now();

  for (const tc of cases) {
    const res = await sendChat({
      host: cfg.host,
      port: cfg.port,
      path: cfg.path,
      timeoutMs: cfg.timeoutMs,
      messages: tc.messages,
    });
    if (!res.ok) {
      failed += 1;
      console.log(`\n[FAIL] ${tc.id} :: ${res.error || "request failed"}`);
      if (res.text) console.log(`  body: ${res.text}`);
      continue;
    }

    const check = validate(res.text, tc.expectAll, tc.rejectAny, tc.expectAny || []);
    if (check.pass) {
      passed += 1;
      console.log(`\n[PASS] ${tc.id}`);
      if (cfg.verbose) console.log(`  answer: ${res.text}`);
    } else {
      failed += 1;
      console.log(`\n[FAIL] ${tc.id}`);
      if (check.misses.length) console.log(`  missing: ${check.misses.join(" | ")}`);
      if (check.anyMiss.length) console.log(`  missing any-of: ${check.anyMiss.join(" | ")}`);
      if (check.hitsReject.length) console.log(`  forbidden matched: ${check.hitsReject.join(" | ")}`);
      console.log(`  answer: ${res.text}`);
    }
  }

  const sec = ((Date.now() - started) / 1000).toFixed(1);
  console.log(`\nSummary: pass=${passed} fail=${failed} total=${cases.length} in ${sec}s`);
  process.exit(failed ? 1 : 0);
}

run().catch((err) => {
  console.error("Fatal:", err?.message || String(err));
  process.exit(1);
});
