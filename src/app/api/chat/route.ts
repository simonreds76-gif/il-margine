import { createGroq } from "@ai-sdk/groq";
import { streamText, stepCountIs, convertToModelMessages } from "ai";
import { z } from "zod";
import * as tools from "@/lib/chat-tools";
import { retrieveContext } from "@/lib/chat-rag";

export const maxDuration = 30;

const CHAT_MODEL = process.env.GROQ_MODEL || "moonshotai/kimi-k2-instruct";

function asNum(v: unknown, fallback = 0): number {
  if (v == null || v === "") return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function asStr(v: unknown): string {
  return v == null ? "" : String(v).trim();
}

function uiTextStreamResponse(text: string): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      const push = (obj: unknown) => controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
      push({ type: "start" });
      push({ type: "start-step" });
      push({ type: "text-start", id: "txt-0" });
      push({ type: "text-delta", id: "txt-0", delta: text });
      push({ type: "text-end", id: "txt-0" });
      push({ type: "finish-step" });
      push({ type: "finish", finishReason: "stop" });
      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}

function extractVsNames(query: string): [string, string] | null {
  const m = query.match(/([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s.'-]*?)\s+(?:vs?\.?|versus)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s.'-]*?)(?:\?|$|,|\.|\s)/i);
  if (!m) return null;
  const a = m[1].replace(/^(who\s+wins?\s+|who\s+|pick\s+|predict\s+)/i, "").trim();
  const b = m[2].replace(/^(who\s+wins?\s+|who\s+|pick\s+|predict\s+)/i, "").trim();
  if (!a || !b) return null;
  return [a, b];
}

function extractTournamentMostWinners(query: string): string | null {
  const m = query.match(/won\s+(.+?)\s+the\s+most/i);
  if (!m) return null;
  return m[1].replace(/^the\s+/i, "").trim();
}

function formatSurfaceBreakdown(bySurface: unknown): string {
  const obj = bySurface as Record<string, { wins?: number; losses?: number; win_pct?: number }> | undefined;
  if (!obj || typeof obj !== "object") return "";
  const parts = Object.entries(obj)
    .map(([s, r]) => `${s} ${asNum(r?.win_pct).toFixed(1)}% (${asNum(r?.wins)}-${asNum(r?.losses)})`)
    .slice(0, 5);
  return parts.join(", ");
}

type ChatMsg = { role?: string; content?: string; parts?: Array<{ type?: string; text?: string }> };

function messageText(m: unknown): string {
  const msg = m as ChatMsg;
  if (typeof msg?.content === "string") return msg.content;
  if (Array.isArray(msg?.parts)) {
    return msg.parts
      .filter((p) => p?.type === "text" && typeof p.text === "string")
      .map((p) => p.text as string)
      .join("");
  }
  return "";
}

function recentConversationTexts(messages: unknown[] | undefined, maxCount = 8): string[] {
  if (!Array.isArray(messages) || !messages.length) return [];
  const out: string[] = [];
  for (let i = messages.length - 1; i >= 0 && out.length < maxCount; i--) {
    const t = messageText(messages[i]).trim();
    if (!t) continue;
    out.push(t);
  }
  return out;
}

function inferRoundFromQuery(query: string): string | null {
  const q = query.toLowerCase();
  if (q.includes("quarter") || q.includes("quarters") || q.includes("quarter-final") || q.includes("quarterfinal") || /\bqf\b/.test(q)) return "QF";
  if (q.includes("semi") || q.includes("semis") || q.includes("semi-final") || q.includes("semifinal") || /\bsf\b/.test(q)) return "SF";
  if (q.includes("final")) return "Final";
  if (q.includes("r16") || q.includes("round of 16") || q.includes("last 16")) return "R16";
  if (q.includes("r3") || q.includes("third round")) return "R3";
  if (q.includes("r2") || q.includes("second round")) return "R2";
  if (q.includes("r1") || q.includes("first round")) return "R1";
  return null;
}

function inferYear(text: string, currentYear: number): number | null {
  const m = text.match(/\b(20\d{2})\b/);
  if (m) return Number(m[1]);
  const q = text.toLowerCase();
  if (q.includes("last year")) return currentYear - 1;
  if (q.includes("this year")) return currentYear;
  return null;
}

function inferTournament(text: string): string | null {
  const q = text.toLowerCase();
  const known = [
    "roland garros",
    "french open",
    "wimbledon",
    "us open",
    "australian open",
    "indian wells",
    "miami",
    "monte carlo",
    "madrid",
    "rome",
    "canada",
    "cincinnati",
    "shanghai",
    "paris",
  ];
  for (const t of known) {
    if (q.includes(t)) return t;
  }
  const won = text.match(/\bwho\s+won\s+(.+?)\s+(?:last|this)\s+year\b/i);
  if (won?.[1]) return won[1].trim();
  const atIn = text.match(/\b(?:at|in)\s+([A-Za-z][A-Za-z\s.'-]{2,50}?)(?:\s+(?:last|this)\s+year|\s+20\d{2}|\?|$)/i);
  if (atIn?.[1]) {
    const cand = atIn[1].trim();
    const c = cand.toLowerCase();
    if (!/\b(final|finals|semi|semis|quarter|quarters|qf|sf|r16|round)\b/.test(c)) {
      return cand;
    }
  }
  return null;
}

function inferPlayerFromBeatQuery(query: string, contextTexts: string[]): string | null {
  const direct = query.match(/\bwho did\s+(.+?)\s+beat\b/i);
  if (direct?.[1]) {
    const cand = direct[1].trim().replace(/^(he|she|they|him|her)\b/i, "").trim();
    if (cand && !/^(he|she|they|him|her)$/i.test(cand)) return cand;
  }
  for (const t of contextTexts) {
    const m =
      t.match(/\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(?:has\s+)?won\b/) ||
      t.match(/\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(?:beat|defeated|crushed)\b/);
    if (m?.[1]) return m[1].trim();
  }
  return null;
}

function extractAgainstPlayerName(query: string): string | null {
  const m = query.match(/\bagainst\s+([A-Za-z][A-Za-z\s.'-]{1,50})\??$/i);
  if (!m?.[1]) return null;
  const name = m[1].trim().replace(/\s+/g, " ");
  return name || null;
}

async function deterministicAnswer(userText: string, uiMessages?: unknown[]): Promise<string | null> {
  const q = userText.trim();
  const lower = q.toLowerCase();

  if (!q) return null;

  if ((lower.includes("do you use") || lower.includes("use your")) && (lower.includes("model") || lower.includes("algorithm"))) {
    return "I use ATP match stats and market data from the database to give a straight, data-backed read.";
  }

  const asksBeatInRound =
    /\bwho did\b/i.test(q) &&
    /\bbeat\b/i.test(q) &&
    /\b(quarter|quarters|qf|semi|semis|sf|final|finals|r16|round of 16|last 16|r3|r2|r1|first round|second round|third round)\b/i.test(q);
  if (asksBeatInRound) {
    const round = inferRoundFromQuery(q);
    if (round) {
      const nowYear = new Date().getFullYear();
      const contextTexts = recentConversationTexts(uiMessages, 10);
      const seasonYear =
        inferYear(q, nowYear) ??
        contextTexts.map((t) => inferYear(t, nowYear)).find((y): y is number => y != null) ??
        undefined;
      const tournament =
        inferTournament(q) ??
        contextTexts.map((t) => inferTournament(t)).find((t): t is string => !!t) ??
        null;
      const player =
        inferPlayerFromBeatQuery(q, contextTexts) ??
        null;

      if (tournament && player) {
        const result = await tools.tournamentEditionResults(tournament, seasonYear, round, player);
        const found = Boolean((result as Record<string, unknown>).found);
        const matches = (((result as Record<string, unknown>).matches as Array<Record<string, unknown>> | undefined) ?? [])
          .filter((m) => asStr(m.winner) && asStr(m.loser));
        if (found && matches.length) {
          const playerLower = player.toLowerCase();
          const won = matches.find((m) => asStr(m.winner).toLowerCase().includes(playerLower));
          const lost = matches.find((m) => asStr(m.loser).toLowerCase().includes(playerLower));
          const m = won ?? lost ?? matches[0];
          const yearOut = asNum((result as Record<string, unknown>).season_year) || seasonYear || nowYear;
          const tourOut = asStr((result as Record<string, unknown>).tournament) || tournament;
          const roundOut = asStr(m.round) || round;
          const winner = asStr(m.winner);
          const loser = asStr(m.loser);
          const score = asStr(m.score);
          if (won) {
            return score
              ? `${winner} beat ${loser} in the ${roundOut} at ${tourOut} ${yearOut}, ${score}.`
              : `${winner} beat ${loser} in the ${roundOut} at ${tourOut} ${yearOut}.`;
          }
          if (lost) {
            return score
              ? `${loser} lost to ${winner} in the ${roundOut} at ${tourOut} ${yearOut}, ${score}.`
              : `${loser} lost to ${winner} in the ${roundOut} at ${tourOut} ${yearOut}.`;
          }
          return score
            ? `${winner} beat ${loser} in the ${roundOut} at ${tourOut} ${yearOut}, ${score}.`
            : `${winner} beat ${loser} in the ${roundOut} at ${tourOut} ${yearOut}.`;
        }
        return `I couldn't find that ${round} result for ${player} at ${tournament}${seasonYear ? ` ${seasonYear}` : ""}.`;
      }
    }
  }

  const isH2hIntent = /\b(h2h|head to head|head-to-head)\b/i.test(q);
  if (isH2hIntent) {
    const pair = extractVsNames(q);
    if (pair) {
      const [a, b] = pair;
      const pa = await tools.searchPlayer(a);
      const pb = await tools.searchPlayer(b);
      if (pa.length && pb.length && pa[0].id && pb[0].id) {
        const h2h = await tools.headToHead(Number(pa[0].id), Number(pb[0].id), undefined);
        const summary = (h2h as Record<string, unknown>).summary as Array<Record<string, unknown>> | undefined;
        const overall = summary?.find((r) => asStr(r.surface) === "Overall");
        const surfaceRows = summary?.filter((r) => asStr(r.surface) !== "Overall") ?? [];
        const aId = Number(pa[0].id);
        const bId = Number(pb[0].id);
        const lowId = Math.min(aId, bId);
        const aIsLow = aId === lowId;
        const orientWinsA = (row: Record<string, unknown>) => (aIsLow ? asNum(row.wins_a) : asNum(row.wins_b));
        const orientWinsB = (row: Record<string, unknown>) => (aIsLow ? asNum(row.wins_b) : asNum(row.wins_a));
        const oW = overall ? orientWinsA(overall) : surfaceRows.reduce((s, r) => s + orientWinsA(r), 0);
        const oL = overall ? orientWinsB(overall) : surfaceRows.reduce((s, r) => s + orientWinsB(r), 0);
        const surf = surfaceRows
          .map((r) => `${asStr(r.surface)} ${orientWinsA(r)}-${orientWinsB(r)}`)
          .slice(0, 4)
          .join(", ");
        const aName = asStr(pa[0].name) || a;
        const bName = asStr(pb[0].name) || b;
        return `${aName} vs ${bName} historical H2H: ${oW}-${oL}.${surf ? ` Surface split: ${surf}.` : ""} This is historical data, not today's fixture list.`;
      }
    }
  }

  const mostTournament = extractTournamentMostWinners(q);
  if (mostTournament) {
    const winners = await tools.tournamentPastWinners(mostTournament);
    if (!winners.length) return `I don't have past-winner data for ${mostTournament} in this dataset.`;
    const counts = new Map<string, number>();
    for (const row of winners) {
      const w = asStr((row as Record<string, unknown>).winner);
      if (!w) continue;
      counts.set(w, (counts.get(w) ?? 0) + 1);
    }
    const top = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);
    if (!top.length) return `I don't have complete winners data for ${mostTournament} right now.`;
    const lead = top[0];
    const chasers = top.slice(1).map(([name, n]) => `${name} (${n})`).join(", ");
    return chasers
      ? `${lead[0]} has won ${mostTournament} the most in this dataset (${lead[1]} titles). Next: ${chasers}.`
      : `${lead[0]} has won ${mostTournament} the most in this dataset (${lead[1]} titles).`;
  }

  const asksUnderdog = /\b(underdog|underdogs|dog|dogs|outsider|outsiders|longshot|long shot)\b/i.test(q);
  if (asksUnderdog) {
    const rows = await tools.matchPrediction(undefined);
    const matches = rows.filter((r) => asStr((r as Record<string, unknown>).player1) && asStr((r as Record<string, unknown>).player2));
    if (!matches.length) return "No ATP main-draw matches found for today.";

    const dogs = matches
      .map((r) => {
        const rr = r as Record<string, unknown>;
        const p1 = asNum(rr.p1_win_pct);
        const p2 = asNum(rr.p2_win_pct);
        if (p1 === p2) return null;
        const dogIsP1 = p1 < p2;
        const dogName = dogIsP1 ? asStr(rr.player1) : asStr(rr.player2);
        const favName = dogIsP1 ? asStr(rr.player2) : asStr(rr.player1);
        const dogPct = Math.min(p1, p2);
        return {
          dogName,
          favName,
          dogPct,
          matchLabel: `${asStr(rr.player1)} vs ${asStr(rr.player2)}`,
        };
      })
      .filter((x): x is { dogName: string; favName: string; dogPct: number; matchLabel: string } => !!x)
      .sort((a, b) => b.dogPct - a.dogPct);

    if (!dogs.length) return "No underdog spots found in today's ATP main-draw matches.";

    const top = dogs.slice(0, 5).map((d) => `${d.dogName} ${d.dogPct.toFixed(1)}% (vs ${d.favName}; ${d.matchLabel})`);
    return `Top ATP underdog spots today (by upset chance): ${top.join("; ")}.`;
  }

  const againstName = extractAgainstPlayerName(q);
  const asksPick = /\b(pick|picks|tip|tips|lean|fancy|who do you like|who wins)\b/i.test(q);
  const vsPairForPick = extractVsNames(q);
  if (vsPairForPick && asksPick) {
    const [a, b] = vsPairForPick;
    const rowsA = await tools.matchPrediction(a);
    const rowsB = await tools.matchPrediction(b);
    const rows = [...rowsA, ...rowsB].filter((r) => asStr((r as Record<string, unknown>).player1) && asStr((r as Record<string, unknown>).player2));
    const target = rows.find((r) => {
      const rr = r as Record<string, unknown>;
      const p1 = asStr(rr.player1).toLowerCase();
      const p2 = asStr(rr.player2).toLowerCase();
      return (p1.includes(a.toLowerCase()) || p2.includes(a.toLowerCase())) && (p1.includes(b.toLowerCase()) || p2.includes(b.toLowerCase()));
    });
    if (target) {
      const rr = target as Record<string, unknown>;
      const p1 = asNum(rr.p1_win_pct);
      const p2 = asNum(rr.p2_win_pct);
      const fav = p1 >= p2 ? asStr(rr.player1) : asStr(rr.player2);
      const favPct = Math.max(p1, p2).toFixed(1);
      const dog = p1 < p2 ? asStr(rr.player1) : asStr(rr.player2);
      const dogPct = Math.min(p1, p2).toFixed(1);
      return `For ${asStr(rr.player1)} vs ${asStr(rr.player2)} today, I'd lean ${fav} (${favPct}%). ${dog} is live at ${dogPct}% if you want the dog angle.`;
    }
    return `${a} vs ${b} is not listed in today's ATP main-draw fixtures, so I can't give a live tip right now.`;
  }
  if (againstName && asksPick) {
    const rows = await tools.matchPrediction(againstName);
    const matches = rows.filter((r) => asStr((r as Record<string, unknown>).player1) && asStr((r as Record<string, unknown>).player2));
    if (!matches.length) {
      return `I can't find a listed ATP main-draw match today involving ${againstName}.`;
    }

    const nameLower = againstName.toLowerCase();
    const pickMatch =
      matches.find((r) => {
        const rr = r as Record<string, unknown>;
        return asStr(rr.player1).toLowerCase().includes(nameLower) || asStr(rr.player2).toLowerCase().includes(nameLower);
      }) ?? matches[0];

    const rr = pickMatch as Record<string, unknown>;
    const p1 = asNum(rr.p1_win_pct);
    const p2 = asNum(rr.p2_win_pct);
    const fav = p1 >= p2 ? asStr(rr.player1) : asStr(rr.player2);
    const favPct = Math.max(p1, p2).toFixed(1);
    const dog = p1 < p2 ? asStr(rr.player1) : asStr(rr.player2);
    const dogPct = Math.min(p1, p2).toFixed(1);
    return `For ${asStr(rr.player1)} vs ${asStr(rr.player2)} today, I'd lean ${fav} (${favPct}%). ${dog} is live at ${dogPct}% if you want the dog angle.`;
  }

  const asksTips = /\b(tip|tips|pick|picks|best bet|best bets|bet slip|value picks?)\b/i.test(q);
  if (asksTips) {
    const rows = await tools.matchPrediction(undefined);
    const matches = rows.filter((r) => asStr((r as Record<string, unknown>).player1) && asStr((r as Record<string, unknown>).player2));
    if (!matches.length) return "No ATP main-draw matches found for today.";

    const scored = matches
      .map((r) => {
        const rr = r as Record<string, unknown>;
        const p1 = asNum(rr.p1_win_pct);
        const p2 = asNum(rr.p2_win_pct);
        const pickP1 = p1 >= p2;
        const pickPlayer = pickP1 ? asStr(rr.player1) : asStr(rr.player2);
        const oppPlayer = pickP1 ? asStr(rr.player2) : asStr(rr.player1);
        const winPct = Math.max(p1, p2);
        const conf = asStr(rr.confidence).toLowerCase();
        const confBoost = conf === "high" ? 4 : conf === "medium" ? 2 : 0;
        const score = Math.abs(p1 - 50) + confBoost;
        return {
          pickPlayer,
          oppPlayer,
          winPct,
          confidence: conf || "n/a",
          surface: asStr(rr.surface),
          score,
        };
      })
      .filter((x) => x.winPct >= 58)
      .sort((a, b) => b.score - a.score);

    const top = (scored.length ? scored : matches
      .map((r) => {
        const rr = r as Record<string, unknown>;
        const p1 = asNum(rr.p1_win_pct);
        const p2 = asNum(rr.p2_win_pct);
        const pickP1 = p1 >= p2;
        return {
          pickPlayer: pickP1 ? asStr(rr.player1) : asStr(rr.player2),
          oppPlayer: pickP1 ? asStr(rr.player2) : asStr(rr.player1),
          winPct: Math.max(p1, p2),
          confidence: asStr(rr.confidence).toLowerCase() || "n/a",
          surface: asStr(rr.surface),
          score: Math.abs(p1 - 50),
        };
      }).sort((a, b) => b.score - a.score))
      .slice(0, 5);

    const tips = top.map((t, i) => `${i + 1}) ${t.pickPlayer} over ${t.oppPlayer} (${t.winPct.toFixed(1)}%, ${t.confidence}, ${t.surface})`);
    return `Today's ATP tips from the numbers: ${tips.join("; ")}.`;
  }

  if (lower.includes("today") || lower.includes("today's") || lower.includes("todays") || lower.includes("picks")) {
    const rows = await tools.matchPrediction(undefined);
    const matches = rows.filter((r) => asStr((r as Record<string, unknown>).player1) && asStr((r as Record<string, unknown>).player2));
    if (!matches.length) return "No ATP main-draw matches found for today.";
    const ranked = [...matches].sort((a, b) => {
      const pa = asNum((a as Record<string, unknown>).p1_win_pct);
      const pb = asNum((b as Record<string, unknown>).p1_win_pct);
      return Math.abs(pb - 50) - Math.abs(pa - 50);
    });
    const top = ranked.slice(0, 5).map((r) => {
      const rr = r as Record<string, unknown>;
      return `${asStr(rr.favoured)} ${Math.max(asNum(rr.p1_win_pct), asNum(rr.p2_win_pct)).toFixed(1)}% (${asStr(rr.player1)} vs ${asStr(rr.player2)})`;
    });
    return `Top ATP spots today: ${top.join("; ")}.`;
  }

  if (lower.includes("big server")) {
    const m = q.match(/how does\s+(.+?)\s+do against big servers/i);
    const name = m?.[1]?.trim();
    if (name) {
      const players = await tools.searchPlayer(name);
      if (!players.length || !players[0].id) return `I can't find ${name} in the player index.`;
      const pid = Number(players[0].id);
      const stats = await tools.playerRecordVsBigServer(pid);
      const overall = (stats as Record<string, unknown>).overall as Record<string, unknown> | undefined;
      const bySurface = formatSurfaceBreakdown((stats as Record<string, unknown>).by_surface);
      return `${asStr(players[0].name)} vs big servers: ${asNum(overall?.win_pct).toFixed(1)}% (${asNum(overall?.wins)}-${asNum(overall?.losses)}).${bySurface ? ` By surface: ${bySurface}.` : ""}`;
    }
  }

  if (lower.includes("leftie") || lower.includes("left-handed") || lower.includes("lefty") || lower.includes("vs left")) {
    const m = q.match(/how does\s+(.+?)\s+do against/i) || q.match(/(.+?)\s+vs a leftie/i);
    const name = m?.[1]?.trim();
    if (name) {
      const players = await tools.searchPlayer(name);
      if (!players.length || !players[0].id) return `I can't find ${name} in the player index.`;
      const pid = Number(players[0].id);
      const stats = await tools.playerRecordVsLefties(pid);
      const overall = (stats as Record<string, unknown>).overall as Record<string, unknown> | undefined;
      const bySurface = formatSurfaceBreakdown((stats as Record<string, unknown>).by_surface);
      return `${asStr(players[0].name)} vs lefties: ${asNum(overall?.win_pct).toFixed(1)}% (${asNum(overall?.wins)}-${asNum(overall?.losses)}).${bySurface ? ` By surface: ${bySurface}.` : ""}`;
    }
  }

  if (lower.includes("who wins")) {
    const pair = extractVsNames(q);
    if (pair) {
      const [a, b] = pair;
      const rowsA = await tools.matchPrediction(a);
      const rowsB = await tools.matchPrediction(b);
      const rows = [...rowsA, ...rowsB].filter((r) => asStr((r as Record<string, unknown>).player1) && asStr((r as Record<string, unknown>).player2));
      const target = rows.find((r) => {
        const rr = r as Record<string, unknown>;
        const p1 = asStr(rr.player1).toLowerCase();
        const p2 = asStr(rr.player2).toLowerCase();
        return (p1.includes(a.toLowerCase()) || p2.includes(a.toLowerCase())) && (p1.includes(b.toLowerCase()) || p2.includes(b.toLowerCase()));
      });
      if (target) {
        const rr = target as Record<string, unknown>;
        const fav = asStr(rr.favoured);
        const favPct = Math.max(asNum(rr.p1_win_pct), asNum(rr.p2_win_pct)).toFixed(1);
        const total = asNum(rr.expected_total_games).toFixed(1);
        return `Numbers favour ${fav} (${favPct}%) in ${asStr(rr.player1)} vs ${asStr(rr.player2)} on ${asStr(rr.surface)}. Expected total games: ${total}.`;
      }
      return `${a} vs ${b} is not listed in today's ATP main-draw fixtures, so I can't give a live match probability right now.`;
    }
  }

  return null;
}

function getLastUserMessageText(messages: unknown[]): string {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i] as { role?: string; content?: string; parts?: Array<{ type?: string; text?: string }> };
    if (m?.role === "user") {
      if (typeof m.content === "string") return m.content;
      if (Array.isArray(m.parts)) {
        const text = m.parts
          .filter((p) => p?.type === "text" && typeof p.text === "string")
          .map((p) => (p as { text: string }).text)
          .join("");
        if (text) return text;
      }
      break;
    }
  }
  return "";
}

function buildIntentHints(userText: string): string {
  const q = userText.toLowerCase();
  const hints: string[] = [];
  const nowYear = new Date().getFullYear();

  const hasVs = /\b(vs|v|versus)\b/.test(q);
  const asksH2h = hasVs && (q.includes("h2h") || q.includes("head to head") || q.includes("head-to-head"));
  if (asksH2h) {
    hints.push("- Intent hint: This is H2H. Call search_player for both players, then head_to_head.");
  }
  if (q.includes("leftie") || q.includes("left-handed") || q.includes("lefty") || q.includes("vs left")) {
    hints.push("- Intent hint: This is a vs-lefties query. Call search_player, then player_record_vs_lefties.");
  }
  if (q.includes("big server")) {
    hints.push("- Intent hint: This is a vs-big-servers query. Call search_player, then player_record_vs_big_server.");
  }

  const asksTournamentWinner = q.includes("who wins") && !hasVs;
  if (asksTournamentWinner) {
    hints.push(
      "- Intent hint: This asks for tournament winner, not today's fixtures. Use tournament_past_winners + tournament_entrants (+ form/surface tools if needed). Do NOT use match_prediction."
    );
  }
  const asksTournamentEditionResult =
    (q.includes("who did") || q.includes("who beat") || q.includes("beat in")) &&
    (q.includes("quarter") || q.includes("qf") || q.includes("semi") || q.includes("sf") || q.includes("final") || q.includes("r16"));
  if (asksTournamentEditionResult) {
    hints.push(
      "- Intent hint: This asks about specific tournament-edition results. Use tournament_edition_results with tournament_name, season_year, round, and player_name (infer pronouns from prior context)."
    );
  }
  if (q.includes("today") || q.includes("today's") || q.includes("todays") || q.includes("picks")) {
    hints.push("- Intent hint: This is a today's-matches/picks query. Use match_prediction.");
  }
  if (q.includes("tip") || q.includes("tips") || q.includes("best bet") || q.includes("bet slip") || q.includes("value pick")) {
    hints.push("- Intent hint: User wants betting tips. Use match_prediction and return 3-5 concrete ATP picks with win % and confidence.");
  }
  if (q.includes("model") || q.includes("algorithm")) {
    hints.push(
      '- Intent hint: Do not use the words "model" or "algorithm" in your answer. Say: "I use ATP match stats and market data from the database."'
    );
  }
  if (q.includes("last year") || q.includes("this year")) {
    hints.push(`- Intent hint: Use explicit years in the answer. Last year = ${nowYear - 1}, this year = ${nowYear}.`);
  }

  return hints.length ? `\n\nINTENT HINTS:\n${hints.join("\n")}` : "";
}

function buildSystemPrompt(ragContext?: string, intentHints?: string): string {
  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  const year = now.getFullYear();

  return `You are Il Margine's Tennis Analyst — a sharp, opinionated expert who gives punchy, data-backed takes on ATP tennis.

Today's date is ${today}. The current year is ${year}. "Last year" means ${year - 1}.

You have tools to query a database of ATP match data going back decades.

RESPONSE STYLE — THIS IS CRITICAL:
- Be concise and punchy. No waffle. Get to the point fast.
- When listing today's matches, do NOT just list every favoured player. Instead:
  - Group matches by tournament.
  - Only highlight the 3-5 most interesting matches (biggest mismatches, closest calls, or notable storylines).
  - For each highlighted match, give a 1-2 sentence take with the win probability and expected total games.
  - Example: "Tsitsipas (72%) should handle Korda on this surface. Expect around 23 games — tight enough that -3.5 is risky."
  - Then briefly mention the rest: "Other strong favourites today: Paul, Tabilo, Hurkacz — all 65%+ and should advance."
- When asked about a specific match ("who wins Borges vs Nava?"), give a focused take: probability, surface context, form, H2H if relevant, and a handicap view.
- When asked who will WIN A TOURNAMENT (e.g. "who wins Indian Wells?", "Indian Wells champion?"): do NOT rely on today's match list. Use player_record_at_tournament, player_surface_stats, player_recent_form, tournament_past_winners, court_pace. Today's matches are a small slice — focus on tournament history, form, and surface fit.
- When asked "is X playing?" or "is Draper in the draw?" or "who's playing Indian Wells?": use tournament_entrants with the tournament and player name. This uses Pinnacle outright odds and gives the full draw.
- For questions like "who did X beat in the quarters/semis/final at [tournament] [year]" or follow-ups like "who did he beat in the quarters?", use tournament_edition_results (tournament_name + season_year + round + player_name). Do not claim you lack results access when data exists.
- When asked about game handicaps, use the expected total games and game margin data to assess whether the line is coverable.
- "Where does X have the best record?" or "X's best surface?" → use player_record_by_surface for surface breakdown. For best tournament, call player_record_at_tournament for 2–3 likely venues (e.g. Indian Wells, Cincinnati, Paris).
- "How do favourites/dogs do at X?" or "fav ROI at Indian Wells?" → use tournament_fav_dog_stats. Level-stake ROI from backtest.
- "Record of seeds at this tournament?" or "how do qualifiers do at X?" → use tournament_seed_stats. Seed/entry win rates from Sackmann.
- "Big servers" = use player_record_vs_big_server (W-L vs opponents with SPW >= 68% on that surface). When explaining, say "service point win %" or "SPW", NOT "hold serve" — 68% SPW is a high bar (elite servers only).
- player_record_vs_lefties: Data includes ATP + Challenger matches. The leftie reference list may not include all players (e.g. Shelton). If by_surface shows only one surface, do NOT claim "all his matches were on X". Say "in our data" or "in the matches we have" — the data may be incomplete. If the user questions the match count, explain that we include Challenger-level matches and full career history.
- Use phrases like "the numbers favour X here", "this looks like a comfortable win", "tight one — could go either way", "I'd lean towards X but it's marginal".

TOURNAMENT NAME MAPPING (critical, the database uses English names):
- "Roland Garros" / "Internazionali d'Italia" etc. use the English name when calling tools: "French Open", "Rome", "Italian Open"
- Grand Slams: Australian Open, French Open, Wimbledon, US Open
- Masters: Indian Wells, Miami, Monte Carlo, Madrid, Rome, Canada, Cincinnati, Shanghai, Paris
- Always use the most common English short name. The tool has alias mapping but help it out.

TOURNAMENT CALENDAR (memorise these months so you know when draws are known):
- Australian Open: January. Indian Wells, Miami: March. Monte Carlo: April. Madrid, Rome: May. French Open (Roland Garros): May/June. Wimbledon: June/July. Canada, Cincinnati: August. US Open: August/September. Shanghai: October. Paris: October/November.
- If asked whether a player is in a future tournament's draw (e.g. "is Merida in the French Open draw?" in March): the draw is not known until the tournament month. Say so. E.g. "Roland Garros is in May/June, so we won't know the draw until then."

RULES:
- CRITICAL: Resolve relative time references to explicit years in output. If user says "last year", use ${year - 1}. If they say "this year", use ${year}. Write the year explicitly in your answer.
- CRITICAL: Always output a brief sentence of text BEFORE making any tool calls. Never start your response with a tool call directly. Example: "Let me look that up." then call the tool.
- CRITICAL: After calling a tool, you MUST include the result in your response. Never leave the user with only "Let me look that up" and nothing else. Always deliver the answer or say you don't have that data.
- Always use search_player first to find player IDs before using other player tools.
- Present percentages with one decimal (65.2%), keep it clean.
- If a tool returns empty results, say you don't have data for that — never make up numbers.
- You can chain multiple tool calls to answer complex questions (e.g. search both players, then get H2H).
- Data covers ATP main tour and Challenger level. No WTA/ITF.
- Do NOT mention "model", "fair odds model", "our model", "algorithm" or anything revealing internal methodology. Present everything as your expert analysis.
- BANNED WORDS in final output: "model", "models", "algorithm", "algorithms". Never use them, even when the user asks with those words.
- If asked for tips or picks: base them solely on the stats and data from your tools. Do not speculate beyond what the data supports.
- Retired players: Do NOT reference Federer, Nadal, Murray, etc. as if they are current. If citing past achievements, be explicit: "beat Federer here in 2019 when he was still active". Exception: "Who's won X the most?" or "past winners at X" are historical by nature — include all winners (Djokovic, Federer, Nadal, etc.) and optionally note who's retired. If asked for "active players only" who won most or have best record: we have no active/retired filter. Use tournament_past_winners and player_record_at_tournament for likely candidates; note who's retired when relevant.
- Use British currency: "quid" not "bucks", "£" not "$". E.g. "a few quid" not "a few bucks".
- Surface values: Hard, Clay, Grass, I.hard (indoor hard).
- Round IDs in the database: 1=R1, 2=R2, 3=R3, 7=R16, 9=QF, 10=SF, 12=Final. 4-6 are qualifying rounds.
- Keep responses SHORT. Max 200 words for match lists, max 100 words for single-match questions. Punchy is better than thorough.${ragContext ? `\n\n${ragContext}\n\nRAG: Prefer the retrieved context above when it answers the question. You may still call tools for additional detail, but use the context first.` : ""}${intentHints ?? ""}`;
}

async function resolvePlayerId(idOrName: string): Promise<number> {
  const s = String(idOrName).trim();
  const n = Number(s);
  if (!isNaN(n) && n > 0) return n;
  const results = await tools.searchPlayer(s);
  if (results.length > 0 && results[0].id) return Number(results[0].id);
  const surname = s.replace(/^[A-Z]\.\s*/, "").split(/\s+/).pop() ?? s;
  if (surname !== s) {
    const retry = await tools.searchPlayer(surname);
    if (retry.length > 0 && retry[0].id) return Number(retry[0].id);
  }
  return 0;
}

/** Wrap tool execute to catch errors and return structured error instead of crashing. */
function safeExecute<T, A extends unknown[]>(
  fn: (...args: A) => Promise<T>,
  toolName: string
): (...args: A) => Promise<T | { error: string }> {
  return async (...args: A) => {
    try {
      return await fn(...args);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[chat] Tool ${toolName} failed:`, msg);
      return { error: `Tool failed: ${msg}` };
    }
  };
}

export async function POST(req: Request) {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    return new Response("AI service is not configured.", { status: 503 });
  }

  const groq = createGroq({ apiKey });

  try {
  const { messages: uiMessages } = await req.json();
  const modelMessages = await convertToModelMessages(uiMessages);

  const lastUserText = getLastUserMessageText(Array.isArray(uiMessages) ? uiMessages : []);
  if (lastUserText) {
    const fast = await deterministicAnswer(lastUserText, Array.isArray(uiMessages) ? uiMessages : undefined);
    if (fast) {
      return uiTextStreamResponse(fast);
    }
  }
  const ragContext = lastUserText ? await retrieveContext(lastUserText) : undefined;
  const intentHints = lastUserText ? buildIntentHints(lastUserText) : "";

  const result = streamText({
    model: groq(CHAT_MODEL),
    system: buildSystemPrompt(ragContext, intentHints),
    messages: modelMessages,
    maxRetries: 2,
    stopWhen: stepCountIs(8),
    tools: {
      search_player: {
        description: "Search for a player by name (partial match). Returns player IDs, names, ranks. Always use this first to find the correct player_id before calling other tools.",
        inputSchema: z.object({
          name: z.string().describe("Player name or surname to search for"),
        }),
        execute: safeExecute(async ({ name }) => tools.searchPlayer(name), "search_player"),
      },

      player_info: {
        description: "Get detailed player info: rank, age, hand (left/right), country, Elo ratings by surface, surface ranking points.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string (get from search_player first)"),
        }),
        execute: safeExecute(async ({ player_id }) => tools.playerInfo(await resolvePlayerId(player_id)), "player_info"),
      },

      player_surface_stats: {
        description: "Get player serve points won % (SPW) and return points won % (RPW) by surface. These are per-POINT stats, not per-game. SPW ~50-53% is elite. Shows 12-month and 36-month windows.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
          surface: z.string().describe("Surface filter: Hard, Clay, Grass, I.hard, or 'all' for all surfaces"),
        }),
        execute: safeExecute(
          async ({ player_id, surface }) =>
            tools.playerSurfaceStats(await resolvePlayerId(player_id), surface === "all" ? undefined : surface),
          "player_surface_stats"
        ),
      },

      player_advanced_stats: {
        description: "Get advanced serve/return stats: first serve %, ace rate, double fault rate, break point save/convert rate, by surface.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
          surface: z.string().describe("Surface filter: Hard, Clay, Grass, I.hard, or 'all' for all surfaces"),
        }),
        execute: safeExecute(
          async ({ player_id, surface }) =>
            tools.playerAdvancedStats(await resolvePlayerId(player_id), surface === "all" ? undefined : surface),
          "player_advanced_stats"
        ),
      },

      head_to_head: {
        description: "Get head-to-head record between two players. Shows overall W-L, surface breakdown, and recent match history with scores.",
        inputSchema: z.object({
          player_a_id: z.string().describe("First player's OnCourt ID as string"),
          player_b_id: z.string().describe("Second player's OnCourt ID as string"),
          surface: z.string().describe("Filter by surface: Hard, Clay, Grass, I.hard, or 'all' for all surfaces"),
        }),
        execute: safeExecute(
          async ({ player_a_id, player_b_id, surface }) =>
            tools.headToHead(await resolvePlayerId(player_a_id), await resolvePlayerId(player_b_id), surface === "all" ? undefined : surface),
          "head_to_head"
        ),
      },

      player_record_at_tournament: {
        description: "Get a player's W-L record at a specific tournament (all editions). Shows win %, recent matches with opponents and scores.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
          tournament_name: z.string().describe("Tournament name or partial name (e.g. 'Monte Carlo', 'Roland Garros', 'Indian Wells')"),
        }),
        execute: safeExecute(
          async ({ player_id, tournament_name }) =>
            tools.playerRecordAtTournament(await resolvePlayerId(player_id), tournament_name),
          "player_record_at_tournament"
        ),
      },

      player_recent_form: {
        description: "Get player's recent form: last 10 matches with results, win rate last 21 days, fatigue indicators, last match date.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: safeExecute(async ({ player_id }) => tools.playerRecentForm(await resolvePlayerId(player_id)), "player_recent_form"),
      },

      player_record_vs_lefties: {
        description: "Get a player's W-L record against left-handed players. Always returns overall record AND breakdown by surface (Hard, Clay, Grass).",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: safeExecute(
          async ({ player_id }) => tools.playerRecordVsLefties(await resolvePlayerId(player_id)),
          "player_record_vs_lefties"
        ),
      },

      player_record_vs_big_server: {
        description: "Get a player's W-L record against BIG SERVERS (opponents with service point win % SPW >= 68% on that surface). Use this when asked about 'vs big servers', 'against big servers', etc. When explaining to users, say '68%+ of service points won' not 'hold serve 68%'.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: safeExecute(
          async ({ player_id }) => tools.playerRecordVsBigServer(await resolvePlayerId(player_id)),
          "player_record_vs_big_server"
        ),
      },

      player_record_at_altitude: {
        description: "Get a player's record at high-altitude venues (200m+ above sea level). Shows W-L and altitude-specific win %.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: safeExecute(
          async ({ player_id }) => tools.playerRecordAtAltitude(await resolvePlayerId(player_id)),
          "player_record_at_altitude"
        ),
      },

      player_record_vs_rank_range: {
        description: "Get a player's record against players ranked within a certain range (e.g. top 10, top 20, top 50). Uses current ATP rankings. Do NOT use for 'big servers' — use player_record_vs_big_server instead.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
          max_rank: z.string().describe("Maximum rank to filter opponents (e.g. '10' for top 10, '50' for top 50)"),
        }),
        execute: safeExecute(
          async ({ player_id, max_rank }) =>
            tools.playerRecordVsRankRange(await resolvePlayerId(player_id), Number(max_rank) || 10),
          "player_record_vs_rank_range"
        ),
      },

      player_record_by_round: {
        description: "Get a player's W-L record broken down by round (Final, SF, QF, R16, etc.). Shows how they perform at different stages.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: safeExecute(
          async ({ player_id }) => tools.playerRecordByRound(await resolvePlayerId(player_id)),
          "player_record_by_round"
        ),
      },

      player_record_by_surface: {
        description: "Get a player's W-L record broken down by surface (Hard, Clay, Grass). Use this when asked about a player's record on a specific surface or their overall surface breakdown. Returns wins, losses, win percentage per surface.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID or player name"),
          surface: z.string().describe("Surface filter: Hard, Clay, Grass, or 'all' for breakdown of all surfaces"),
        }),
        execute: safeExecute(
          async ({ player_id, surface }) =>
            tools.playerRecordBySurface(await resolvePlayerId(player_id), surface === "all" ? undefined : surface),
          "player_record_by_surface"
        ),
      },

      tournament_info: {
        description: "Get tournament information: surface, country, altitude, average total games, serve profile, past editions.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name or partial name"),
        }),
        execute: safeExecute(async ({ tournament_name }) => tools.tournamentInfo(tournament_name), "tournament_info"),
      },

      court_pace: {
        description: "Get the court pace / speed of a tournament. Returns serve point win % (SPW) compared to surface average, and a pace rating (fast/slow/average). Use this when asked about court speed, CPI, fast/slow courts, or comparing venues. Higher SPW = faster court.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name or partial name"),
        }),
        execute: safeExecute(async ({ tournament_name }) => tools.courtPace(tournament_name), "court_pace"),
      },

      tournament_past_winners: {
        description: "Get the list of past winners of a tournament with runner-ups and final scores.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name or partial name"),
        }),
        execute: safeExecute(
          async ({ tournament_name }) => tools.tournamentPastWinners(tournament_name),
          "tournament_past_winners"
        ),
      },

      tournament_edition_results: {
        description: "Get match-level results for a specific tournament edition (year), with optional round and player filters. Use for questions like 'who did Alcaraz beat in the QF at Roland Garros last year?'.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name (e.g. French Open, Indian Wells, Wimbledon)"),
          season_year: z.string().optional().describe("Edition year (e.g. 2025). Omit to use latest edition."),
          round: z.string().optional().describe("Round filter (QF, SF, Final, R16, R1, etc.)"),
          player_name: z.string().optional().describe("Optional player name filter (e.g. Carlos Alcaraz)"),
        }),
        execute: safeExecute(
          async ({ tournament_name, season_year, round, player_name }) =>
            tools.tournamentEditionResults(
              tournament_name,
              season_year && /^\d{4}$/.test(season_year) ? Number(season_year) : undefined,
              round,
              player_name
            ),
          "tournament_edition_results"
        ),
      },

      tournament_entrants: {
        description: "Get the list of players in a tournament's draw (from Pinnacle outright/winner odds). Use for 'is X playing?', 'who's in the Indian Wells draw?', 'is Draper playing this year?'. Pass player_name to check if they're in the draw, or 'all' for full list.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name (e.g. Indian Wells, Miami)"),
          player_name: z.string().describe("Player name to check (e.g. Draper), or 'all' for full entrants list"),
        }),
        execute: safeExecute(
          async ({ tournament_name, player_name }) =>
            tools.tournamentEntrants(tournament_name, player_name === "all" ? undefined : player_name),
          "tournament_entrants"
        ),
      },

      match_prediction: {
        description: "Get analysis for today's MAIN DRAW matches (ATP main tour only, no Challenger, no qualifying). Returns win probabilities, expected total games, handicap estimates. Use for 'who wins X vs Y today?', 'will X cover the handicap?'. Do NOT use for 'who wins Indian Wells?' (tournament winner) — use player_record_at_tournament, player_recent_form, etc instead.",
        inputSchema: z.object({
          player_name: z.string().describe("Player name to find their specific match, or 'all' to get all today's matches"),
        }),
        execute: safeExecute(
          async ({ player_name }) => tools.matchPrediction(player_name === "all" ? undefined : player_name),
          "match_prediction"
        ),
      },

      tournament_fav_dog_stats: {
        description: "Get historical favourite vs underdog ROI at a tournament (from backtest). Use for 'how do favourites do at Indian Wells?', 'how do dogs do at this tournament?', 'fav/dog ROI at X'. Returns level-stake ROI % for backing favourites and underdogs over recent years.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name (e.g. Indian Wells, French Open, Miami)"),
        }),
        execute: safeExecute(
          async ({ tournament_name }) => tools.tournamentFavDogStats(tournament_name),
          "tournament_fav_dog_stats"
        ),
      },

      tournament_seed_stats: {
        description: "Get seed and entry stats at a tournament (from Sackmann). Use for 'record of seeds at this tournament', 'how do qualifiers do at X', 'seed 1-2 at Indian Wells'. Returns win rates by segment (seed_unseeded, entry_MD, entry_Q, etc.), max round reached, R1 win rate.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name (e.g. Indian Wells, French Open, Wimbledon)"),
        }),
        execute: safeExecute(
          async ({ tournament_name }) => tools.tournamentSeedStats(tournament_name),
          "tournament_seed_stats"
        ),
      },
    },
  });

  return result.toUIMessageStreamResponse();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const lower = message.toLowerCase();
    console.error("[chat] Error:", err);
    if (process.env.NODE_ENV === "development") {
      return new Response(`Error (dev): ${message}`, { status: 500 });
    }
    let userMessage = "Sorry, I'm a bit busy right now. Please try again in a moment.";
    if (lower.includes("over capacity") || lower.includes("overcapacity")) {
      userMessage = "Roger is overloaded right now. Try again in a minute.";
    } else if (lower.includes("rate limit") || lower.includes("quota") || lower.includes("429")) {
      userMessage = "I've hit my daily question limit. Please try again in an hour or so.";
    } else if (lower.includes("timeout") || lower.includes("timed out")) {
      userMessage = "Request timed out. Please try again.";
    } else if (lower.includes("api key") || lower.includes("unauthorized") || lower.includes("401")) {
      userMessage = "Roger is temporarily unavailable. We're looking into it.";
    } else if (message.length < 200 && !message.includes("key") && !message.includes("secret")) {
      userMessage = `Roger hit an error: ${message}`;
    }
    return new Response(userMessage, { status: 503 });
  }
}
