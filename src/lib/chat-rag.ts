/**
 * RAG-style retrieval for the tennis chatbot.
 * Extracts entities from the user query, calls relevant tools in parallel,
 * and returns formatted context for the LLM to answer from.
 */
import * as tools from "@/lib/chat-tools";

/** Same as chat-tools: full ATP list by tournament name and city. */
import tournamentAliases from "./tournament-aliases.json";
const TOURNAMENT_ALIASES: Record<string, string[]> = tournamentAliases as Record<string, string[]>;

function extractTournamentNames(query: string): string[] {
  const lower = query.toLowerCase();
  const out: string[] = [];
  for (const [alias, dbNames] of Object.entries(TOURNAMENT_ALIASES)) {
    if (lower.includes(alias)) out.push(...dbNames);
  }
  return [...new Set(out)];
}

/** Extract candidate player name tokens (e.g. "Sinner", "Alcaraz", "Rune vs Cobolli" -> ["Sinner"], ["Alcaraz"], ["Rune","Cobolli"]) */
function extractPlayerCandidates(query: string): string[][] {
  const lower = query.toLowerCase();
  const candidates: string[][] = [];

  // "X vs Y" or "X v Y" or "X versus Y"
  const vsMatch = query.match(/([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]*?)\s+(?:vs?\.?|versus)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]*?)(?:\s|$|\.|,|\?)/i);
  if (vsMatch) {
    candidates.push([vsMatch[1].trim(), vsMatch[2].trim()]);
  }

  // "X's record" or "X record" or "record of X"
  const recordMatch = query.match(/(?:record\s+of\s+|)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]+?)(?:'s|\s+record|$)/i);
  if (recordMatch) candidates.push([recordMatch[1].trim()]);

  // "X and Y"
  const andMatch = query.match(/([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]+?)\s+and\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]+?)(?:\s|$|\.|,|\?)/i);
  if (andMatch) candidates.push([andMatch[1].trim(), andMatch[2].trim()]);

  // Single capitalized words that look like surnames (2-4 chars or longer)
  const words = query.split(/\s+/).filter((w) => /^[A-Z][a-zà-ÿ]+$/.test(w) && w.length >= 3);
  if (words.length && !candidates.length) {
    for (const w of words.slice(0, 3)) candidates.push([w]);
  }

  return candidates;
}

function hasKeyword(query: string, ...keywords: string[]): boolean {
  const lower = query.toLowerCase();
  return keywords.some((k) => lower.includes(k));
}

function formatJson(obj: unknown): string {
  try {
    return JSON.stringify(obj, null, 0).slice(0, 2000);
  } catch {
    return String(obj);
  }
}

export async function retrieveContext(query: string): Promise<string> {
  const chunks: string[] = [];
  const q = query.trim();
  if (!q || q.length < 3) return "";

  const tournaments = extractTournamentNames(q);
  const playerCandidates = extractPlayerCandidates(q);

  // Resolve player IDs
  const playerIds: number[] = [];
  const playerNames: string[] = [];
  const seen = new Set<number>();
  for (const group of playerCandidates) {
    for (const name of group) {
      const results = await tools.searchPlayer(name);
      if (results.length > 0 && results[0].id) {
        const id = Number(results[0].id);
        if (!seen.has(id)) {
          seen.add(id);
          playerIds.push(id);
          playerNames.push(String(results[0].name ?? name));
        }
      }
    }
  }

  const promises: Promise<{ label: string; data: unknown }>[] = [];

  // H2H if two players and vs/head-to-head
  if (playerIds.length >= 2 && hasKeyword(q, "vs", "versus", "head to head", "h2h")) {
    promises.push(
      tools.headToHead(playerIds[0], playerIds[1]).then((d) => ({ label: "head_to_head", data: d }))
    );
  }

  // Player record by surface (for "best record", "where does X do best" etc.)
  if (playerIds.length > 0 && hasKeyword(q, "record", "best", "where does", "surface", "clay", "hard", "grass")) {
    for (const pid of playerIds.slice(0, 2)) {
      promises.push(tools.playerRecordBySurface(pid).then((d) => ({ label: "player_record_by_surface", data: d })));
    }
  }

  // Player record at tournament
  if (playerIds.length > 0 && tournaments.length > 0 && hasKeyword(q, "tournament", "at ", "record", "how did", "best result")) {
    for (const pid of playerIds.slice(0, 2)) {
      for (const t of tournaments.slice(0, 2)) {
        promises.push(
          tools.playerRecordAtTournament(pid, t).then((d) => ({ label: `player_record_at_${t}`, data: d }))
        );
      }
    }
  }

  // Vs lefties
  if (playerIds.length > 0 && hasKeyword(q, "leftie", "left-handed", "lefty", "vs left")) {
    for (const pid of playerIds.slice(0, 2)) {
      promises.push(tools.playerRecordVsLefties(pid).then((d) => ({ label: "vs_lefties", data: d })));
    }
  }

  // Vs big servers
  if (playerIds.length > 0 && hasKeyword(q, "big server", "big servers")) {
    for (const pid of playerIds.slice(0, 2)) {
      promises.push(tools.playerRecordVsBigServer(pid).then((d) => ({ label: "vs_big_servers", data: d })));
    }
  }

  // Recent form
  if (playerIds.length > 0 && hasKeyword(q, "form", "recent", "last", "lately")) {
    for (const pid of playerIds.slice(0, 2)) {
      promises.push(tools.playerRecentForm(pid).then((d) => ({ label: "recent_form", data: d })));
    }
  }

  // Tournament info / past winners / court pace / fav-dog ROI / seed stats
  if (tournaments.length > 0) {
    if (hasKeyword(q, "won", "champion", "winner", "past", "history")) {
      for (const t of tournaments.slice(0, 2)) {
        promises.push(tools.tournamentPastWinners(t).then((d) => ({ label: `past_winners_${t.replace(/\s/g, "_")}`, data: d })));
      }
    }
    if (hasKeyword(q, "surface", "court", "speed", "pace")) {
      for (const t of tournaments.slice(0, 2)) {
        promises.push(tools.courtPace(t).then((d) => ({ label: `court_pace_${t.replace(/\s/g, "_")}`, data: d })));
      }
    }
    if (hasKeyword(q, "favourite", "favorite", "fav", "dog", "underdog", "roi", "how do")) {
      for (const t of tournaments.slice(0, 2)) {
        promises.push(tools.tournamentFavDogStats(t).then((d) => ({ label: "tournament_fav_dog", data: d })));
      }
    }
    if (hasKeyword(q, "seed", "seeds", "qualifier", "qualifiers", "entry", "unseeded")) {
      for (const t of tournaments.slice(0, 2)) {
        promises.push(tools.tournamentSeedStats(t).then((d) => ({ label: "tournament_seed_stats", data: d })));
      }
    }
    if (hasKeyword(q, "about", "info", "tell me", "what is") || !playerIds.length) {
      for (const t of tournaments.slice(0, 1)) {
        promises.push(tools.tournamentInfo(t).then((d) => ({ label: "tournament_info", data: d })));
      }
    }
  }

  // Player info (rank, Elo) if we have players
  if (playerIds.length > 0 && playerIds.length <= 2) {
    for (const pid of playerIds) {
      promises.push(tools.playerInfo(pid).then((d) => ({ label: "player_info", data: d })));
    }
  }

  // Cap parallel calls
  const results = await Promise.allSettled(promises.slice(0, 8));

  for (const r of results) {
    if (r.status === "fulfilled" && r.value.data != null) {
      const { label, data } = r.value;
      const str = formatJson(data);
      if (str && str !== "{}" && str !== "null") {
        chunks.push(`[${label}]\n${str}`);
      }
    }
  }

  if (chunks.length === 0) return "";

  return `RETRIEVED CONTEXT (use this data to answer; if it doesn't contain the answer, say so):\n\n${chunks.join("\n\n")}`;
}
