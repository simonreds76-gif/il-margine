import { createGroq } from "@ai-sdk/groq";
import { streamText, stepCountIs, convertToModelMessages } from "ai";
import { z } from "zod";
import * as tools from "@/lib/chat-tools";
import { retrieveContext } from "@/lib/chat-rag";

export const maxDuration = 30;

const CHAT_MODEL = process.env.GROQ_MODEL || "moonshotai/kimi-k2-instruct";

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

function buildSystemPrompt(ragContext?: string): string {
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
- When asked about game handicaps, use the expected total games and game margin data to assess whether the line is coverable.
- "How do favourites/dogs do at X?" or "fav ROI at Indian Wells?" → use tournament_fav_dog_stats. Level-stake ROI from backtest.
- "Record of seeds at this tournament?" or "how do qualifiers do at X?" → use tournament_seed_stats. Seed/entry win rates from Sackmann.
- "Big servers" = use player_record_vs_big_server (W-L vs opponents with SPW >= 68% on that surface). When explaining, say "service point win %" or "SPW", NOT "hold serve" — 68% SPW is a high bar (elite servers only).
- player_record_vs_lefties: The leftie reference list may not include all players (e.g. Shelton). If by_surface shows only one surface, do NOT claim "all his matches were on X". Say "in our data" or "in the matches we have" — the data may be incomplete.
- Use phrases like "the numbers favour X here", "this looks like a comfortable win", "tight one — could go either way", "I'd lean towards X but it's marginal".

TOURNAMENT NAME MAPPING (critical — the database uses English names):
- "Roland Garros" / "Internazionali d'Italia" etc. → use the English name when calling tools: "French Open", "Rome", "Italian Open"
- Grand Slams: Australian Open, French Open, Wimbledon, US Open
- Masters: Indian Wells, Miami, Monte Carlo, Madrid, Rome, Canada, Cincinnati, Shanghai, Paris
- Always use the most common English short name. The tool has alias mapping but help it out.

RULES:
- CRITICAL: Always output a brief sentence of text BEFORE making any tool calls. Never start your response with a tool call directly. Example: "Let me look that up." then call the tool.
- Always use search_player first to find player IDs before using other player tools.
- Present percentages with one decimal (65.2%), keep it clean.
- If a tool returns empty results, say you don't have data for that — never make up numbers.
- You can chain multiple tool calls to answer complex questions (e.g. search both players, then get H2H).
- Data covers ATP main tour and Challenger level. No WTA/ITF.
- Do NOT mention "model", "fair odds model", "our model", "algorithm" or anything revealing internal methodology. Present everything as your expert analysis.
- Do NOT reference retired players (Federer, Nadal, Murray, etc.) as if they are current. If citing past achievements, be explicit: "beat Federer here in 2019 when he was still active".
- Use British currency: "quid" not "bucks", "£" not "$". E.g. "a few quid" not "a few bucks".
- Surface values: Hard, Clay, Grass, I.hard (indoor hard).
- Round IDs in the database: 1=R1, 2=R2, 3=R3, 7=R16, 9=QF, 10=SF, 12=Final. 4-6 are qualifying rounds.
- Keep responses SHORT. Max 200 words for match lists, max 100 words for single-match questions. Punchy is better than thorough.${ragContext ? `\n\n${ragContext}\n\nRAG: Prefer the retrieved context above when it answers the question. You may still call tools for additional detail, but use the context first.` : ""}`;
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
  const ragContext = lastUserText ? await retrieveContext(lastUserText) : undefined;

  const result = streamText({
    model: groq(CHAT_MODEL),
    system: buildSystemPrompt(ragContext),
    messages: modelMessages,
    maxRetries: 1,
    stopWhen: stepCountIs(8),
    tools: {
      search_player: {
        description: "Search for a player by name (partial match). Returns player IDs, names, ranks. Always use this first to find the correct player_id before calling other tools.",
        inputSchema: z.object({
          name: z.string().describe("Player name or surname to search for"),
        }),
        execute: async ({ name }: { name: string }) => tools.searchPlayer(name),
      },

      player_info: {
        description: "Get detailed player info: rank, age, hand (left/right), country, Elo ratings by surface, surface ranking points.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string (get from search_player first)"),
        }),
        execute: async ({ player_id }: { player_id: string }) => tools.playerInfo(await resolvePlayerId(player_id)),
      },

      player_surface_stats: {
        description: "Get player serve points won % (SPW) and return points won % (RPW) by surface. These are per-POINT stats, not per-game. SPW ~50-53% is elite. Shows 12-month and 36-month windows.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
          surface: z.string().describe("Surface filter: Hard, Clay, Grass, I.hard, or 'all' for all surfaces"),
        }),
        execute: async ({ player_id, surface }: { player_id: string; surface: string }) =>
          tools.playerSurfaceStats(await resolvePlayerId(player_id), surface === "all" ? undefined : surface),
      },

      player_advanced_stats: {
        description: "Get advanced serve/return stats: first serve %, ace rate, double fault rate, break point save/convert rate, by surface.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
          surface: z.string().describe("Surface filter: Hard, Clay, Grass, I.hard, or 'all' for all surfaces"),
        }),
        execute: async ({ player_id, surface }: { player_id: string; surface: string }) =>
          tools.playerAdvancedStats(await resolvePlayerId(player_id), surface === "all" ? undefined : surface),
      },

      head_to_head: {
        description: "Get head-to-head record between two players. Shows overall W-L, surface breakdown, and recent match history with scores.",
        inputSchema: z.object({
          player_a_id: z.string().describe("First player's OnCourt ID as string"),
          player_b_id: z.string().describe("Second player's OnCourt ID as string"),
          surface: z.string().describe("Filter by surface: Hard, Clay, Grass, I.hard, or 'all' for all surfaces"),
        }),
        execute: async ({ player_a_id, player_b_id, surface }: { player_a_id: string; player_b_id: string; surface: string }) =>
          tools.headToHead(await resolvePlayerId(player_a_id), await resolvePlayerId(player_b_id), surface === "all" ? undefined : surface),
      },

      player_record_at_tournament: {
        description: "Get a player's W-L record at a specific tournament (all editions). Shows win %, recent matches with opponents and scores.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
          tournament_name: z.string().describe("Tournament name or partial name (e.g. 'Monte Carlo', 'Roland Garros', 'Indian Wells')"),
        }),
        execute: async ({ player_id, tournament_name }: { player_id: string; tournament_name: string }) =>
          tools.playerRecordAtTournament(await resolvePlayerId(player_id), tournament_name),
      },

      player_recent_form: {
        description: "Get player's recent form: last 10 matches with results, win rate last 21 days, fatigue indicators, last match date.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: async ({ player_id }: { player_id: string }) => tools.playerRecentForm(await resolvePlayerId(player_id)),
      },

      player_record_vs_lefties: {
        description: "Get a player's W-L record against left-handed players. Always returns overall record AND breakdown by surface (Hard, Clay, Grass).",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: async ({ player_id }: { player_id: string }) =>
          tools.playerRecordVsLefties(await resolvePlayerId(player_id)),
      },

      player_record_vs_big_server: {
        description: "Get a player's W-L record against BIG SERVERS (opponents with service point win % SPW >= 68% on that surface). Use this when asked about 'vs big servers', 'against big servers', etc. When explaining to users, say '68%+ of service points won' not 'hold serve 68%'.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: async ({ player_id }: { player_id: string }) =>
          tools.playerRecordVsBigServer(await resolvePlayerId(player_id)),
      },

      player_record_at_altitude: {
        description: "Get a player's record at high-altitude venues (200m+ above sea level). Shows W-L and altitude-specific win %.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: async ({ player_id }: { player_id: string }) => tools.playerRecordAtAltitude(await resolvePlayerId(player_id)),
      },

      player_record_vs_rank_range: {
        description: "Get a player's record against players ranked within a certain range (e.g. top 10, top 20, top 50). Uses current ATP rankings. Do NOT use for 'big servers' — use player_record_vs_big_server instead.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
          max_rank: z.string().describe("Maximum rank to filter opponents (e.g. '10' for top 10, '50' for top 50)"),
        }),
        execute: async ({ player_id, max_rank }: { player_id: string; max_rank: string }) =>
          tools.playerRecordVsRankRange(await resolvePlayerId(player_id), Number(max_rank) || 10),
      },

      player_record_by_round: {
        description: "Get a player's W-L record broken down by round (Final, SF, QF, R16, etc.). Shows how they perform at different stages.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID as string"),
        }),
        execute: async ({ player_id }: { player_id: string }) => tools.playerRecordByRound(await resolvePlayerId(player_id)),
      },

      player_record_by_surface: {
        description: "Get a player's W-L record broken down by surface (Hard, Clay, Grass). Use this when asked about a player's record on a specific surface or their overall surface breakdown. Returns wins, losses, win percentage per surface.",
        inputSchema: z.object({
          player_id: z.string().describe("OnCourt player ID or player name"),
          surface: z.string().describe("Surface filter: Hard, Clay, Grass, or 'all' for breakdown of all surfaces"),
        }),
        execute: async ({ player_id, surface }: { player_id: string; surface: string }) =>
          tools.playerRecordBySurface(await resolvePlayerId(player_id), surface === "all" ? undefined : surface),
      },

      tournament_info: {
        description: "Get tournament information: surface, country, altitude, average total games, serve profile, past editions.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name or partial name"),
        }),
        execute: async ({ tournament_name }: { tournament_name: string }) => tools.tournamentInfo(tournament_name),
      },

      court_pace: {
        description: "Get the court pace / speed of a tournament. Returns serve point win % (SPW) compared to surface average, and a pace rating (fast/slow/average). Use this when asked about court speed, CPI, fast/slow courts, or comparing venues. Higher SPW = faster court.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name or partial name"),
        }),
        execute: async ({ tournament_name }: { tournament_name: string }) => tools.courtPace(tournament_name),
      },

      tournament_past_winners: {
        description: "Get the list of past winners of a tournament with runner-ups and final scores.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name or partial name"),
        }),
        execute: async ({ tournament_name }: { tournament_name: string }) => tools.tournamentPastWinners(tournament_name),
      },

      tournament_entrants: {
        description: "Get the list of players in a tournament's draw (from Pinnacle outright/winner odds). Use for 'is X playing?', 'who's in the Indian Wells draw?', 'is Draper playing this year?'. Pass player_name to check if they're in the draw, or 'all' for full list.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name (e.g. Indian Wells, Miami)"),
          player_name: z.string().describe("Player name to check (e.g. Draper), or 'all' for full entrants list"),
        }),
        execute: async ({ tournament_name, player_name }: { tournament_name: string; player_name: string }) =>
          tools.tournamentEntrants(tournament_name, player_name === "all" ? undefined : player_name),
      },

      match_prediction: {
        description: "Get analysis for today's MAIN DRAW matches (ATP main tour only, no Challenger, no qualifying). Returns win probabilities, expected total games, handicap estimates. Use for 'who wins X vs Y today?', 'will X cover the handicap?'. Do NOT use for 'who wins Indian Wells?' (tournament winner) — use player_record_at_tournament, player_recent_form, etc instead.",
        inputSchema: z.object({
          player_name: z.string().describe("Player name to find their specific match, or 'all' to get all today's matches"),
        }),
        execute: async ({ player_name }: { player_name: string }) =>
          tools.matchPrediction(player_name === "all" ? undefined : player_name),
      },

      tournament_fav_dog_stats: {
        description: "Get historical favourite vs underdog ROI at a tournament (from backtest). Use for 'how do favourites do at Indian Wells?', 'how do dogs do at this tournament?', 'fav/dog ROI at X'. Returns level-stake ROI % for backing favourites and underdogs over recent years.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name (e.g. Indian Wells, French Open, Miami)"),
        }),
        execute: async ({ tournament_name }: { tournament_name: string }) =>
          tools.tournamentFavDogStats(tournament_name),
      },

      tournament_seed_stats: {
        description: "Get seed and entry stats at a tournament (from Sackmann). Use for 'record of seeds at this tournament', 'how do qualifiers do at X', 'seed 1-2 at Indian Wells'. Returns win rates by segment (seed_unseeded, entry_MD, entry_Q, etc.), max round reached, R1 win rate.",
        inputSchema: z.object({
          tournament_name: z.string().describe("Tournament name (e.g. Indian Wells, French Open, Wimbledon)"),
        }),
        execute: async ({ tournament_name }: { tournament_name: string }) =>
          tools.tournamentSeedStats(tournament_name),
      },
    },
  });

  return result.toUIMessageStreamResponse();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("[chat] Error:", err);
    if (process.env.NODE_ENV === "development") {
      return new Response(`Error (dev): ${message}`, { status: 500 });
    }
    return new Response("Sorry, I'm a bit busy right now. Please try again in a moment.", { status: 503 });
  }
}
