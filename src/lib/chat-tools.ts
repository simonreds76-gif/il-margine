import { createClient } from "@supabase/supabase-js";
import { readFile } from "fs/promises";
import path from "path";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
const sb = createClient(url, key);

type Row = Record<string, unknown>;

function num(v: unknown, fallback = 0): number {
  if (v == null || v === "") return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function str(v: unknown): string {
  return v == null ? "" : String(v).trim();
}

function surfaceFromCourtName(name: string): string {
  const n = str(name).toUpperCase();
  if (n.includes("CLAY")) return "Clay";
  if (n.includes("GRASS")) return "Grass";
  if (n.includes("I.HARD") || n === "I.HARD" || n.includes("INDOOR")) return "I.hard";
  if (n.includes("CARPET")) return "Carpet";
  return "Hard";
}

async function fetchAllLeftieIds(): Promise<number[]> {
  const pageSize = 1000;
  let from = 0;
  const out: number[] = [];

  while (true) {
    const { data, error } = await sb
      .from("player_hand_reference")
      .select("player_id")
      .eq("hand", "L")
      .range(from, from + pageSize - 1);

    if (error || !data?.length) break;
    for (const row of data) {
      out.push(num(row.player_id));
    }
    if (data.length < pageSize) break;
    from += data.length;
  }
  return [...new Set(out.filter((id) => id > 0))];
}

/** Tournament name + city aliases. Full ATP list by tournament name and city. */
import tournamentAliases from "./tournament-aliases.json";
const TOURNAMENT_ALIASES: Record<string, string[]> = tournamentAliases as Record<string, string[]>;

function resolveSearchTerms(input: string): string[] {
  const lower = input.toLowerCase().trim();
  for (const [alias, dbNames] of Object.entries(TOURNAMENT_ALIASES)) {
    if (lower.includes(alias)) return dbNames;
  }
  const terms = [input];
  if (/\s/.test(input)) terms.push(input.replace(/\s+/g, "-"));
  if (/-/.test(input)) terms.push(input.replace(/-/g, " "));
  return [...new Set(terms)];
}

const JUNK_TOUR_KEYWORDS = ["junior", "qualif", "boys", "girls", "legends", "doubles", "wheelchair"];
function isMainTour(name: string): boolean {
  const lower = name.toLowerCase();
  return !JUNK_TOUR_KEYWORDS.some((kw) => lower.includes(kw));
}

/* ── Player search (fuzzy, typo-tolerant) ─────────────────── */

/** Common spelling variants (Maroszan/Marozsan, etc.). */
function spellingVariants(q: string): string[] {
  const variants = [q];
  const lower = q.toLowerCase();
  if (lower.includes("maroszan")) variants.push(q.replace(/maroszan/gi, "Marozsan"));
  if (lower.includes("marozsan") && !lower.includes("maroszan")) variants.push(q.replace(/marozsan/gi, "Maroszan"));
  if (lower.includes("auger-aliassime")) variants.push(q.replace(/auger-aliassime/gi, "Auger-Aliassime"));
  if (lower.includes("auger aliassime")) variants.push(q.replace(/auger aliassime/gi, "Auger-Aliassime"));
  if (lower.includes("auger aliassime") && !lower.includes("auger-aliassime")) variants.push(q.replace(/auger aliassime/gi, "Auger Aliassime"));
  return [...new Set(variants)];
}

/** Typo-tolerant variants: dedupe consecutive chars, surname only, prefix. */
function typoTolerantVariants(q: string): string[] {
  const out: string[] = [];
  const words = q.split(/\s+/).filter(Boolean);
  const surname = words.length > 1 ? words[words.length - 1]! : words[0] ?? q;
  if (surname.length >= 4) out.push(surname);
  const deduped = surname.replace(/(.)\1+/g, "$1");
  if (deduped !== surname && deduped.length >= 4) out.push(deduped);
  if (surname.length >= 6) out.push(surname.slice(0, 6));
  if (surname.length >= 5) out.push(surname.slice(0, 5));
  return [...new Set(out)];
}

export async function searchPlayer(name: string): Promise<Row[]> {
  const q = name.trim();
  if (!q) return [];
  const termsToTry = [...spellingVariants(q), ...typoTolerantVariants(q).filter((t) => t !== q)];
  for (const term of termsToTry) {
    if (!term || term.length < 3) continue;
    const { data } = await sb
      .from("oncourt_players")
      .select("id, name, birthdate, country, atp_rank")
      .ilike("name", `%${term}%`)
      .not("name", "like", "%/%")
      .order("atp_rank", { ascending: true, nullsFirst: false })
      .limit(10);
    if (data?.length) return data;
  }
  return [];
}

/* ── Player info (rank, age, hand, Elo, country) ──────────── */

export async function playerInfo(playerId: number): Promise<Row | null> {
  const { data: p } = await sb
    .from("oncourt_players")
    .select("id, name, birthdate, country, atp_rank, hard_points, clay_points, grass_points")
    .eq("id", playerId)
    .single();
  if (!p) return null;

  const { data: hand } = await sb
    .from("player_hand_reference")
    .select("hand")
    .eq("player_id", playerId)
    .maybeSingle();

  const { data: elo } = await sb
    .from("player_elo")
    .select("surface, elo")
    .eq("player_id", playerId);

  return {
    ...p,
    hand: hand?.hand ?? "Unknown",
    elo: (elo ?? []).reduce((acc: Record<string, number>, r: Row) => {
      acc[str(r.surface)] = num(r.elo);
      return acc;
    }, {} as Record<string, number>),
  };
}

/* ── Player surface stats (SPW, RPW, match count) ────────── */

export async function playerSurfaceStats(playerId: number, surface?: string): Promise<Row[]> {
  let q = sb
    .from("player_surface_stats")
    .select("player_id, surface, hold_pct, return_pct, match_count, service_pts, return_pts, hold_pct_long, return_pct_long, match_count_long")
    .eq("player_id", playerId);
  if (surface) q = q.eq("surface", surface);
  const { data } = await q.limit(10);
  return (data ?? []).map((r: Row) => ({
    surface: r.surface,
    serve_points_won_pct_12m: Math.round(num(r.hold_pct) * 1000) / 10,
    return_points_won_pct_12m: Math.round(num(r.return_pct) * 1000) / 10,
    matches_12m: r.match_count,
    service_points_played: r.service_pts,
    serve_points_won_pct_36m: Math.round(num(r.hold_pct_long) * 1000) / 10,
    return_points_won_pct_36m: Math.round(num(r.return_pct_long) * 1000) / 10,
    matches_36m: r.match_count_long,
  }));
}

/* ── Player advanced stats (ace rate, DF, BP save/convert) ── */

export async function playerAdvancedStats(playerId: number, surface?: string): Promise<Row[]> {
  let q = sb
    .from("player_advanced_stats")
    .select("*")
    .eq("player_id", playerId);
  if (surface) q = q.eq("surface", surface);
  const { data } = await q.limit(10);
  return data ?? [];
}

/* ── Head to head ─────────────────────────────────────────── */

export async function headToHead(playerAId: number, playerBId: number, surface?: string): Promise<Row> {
  const lowId = Math.min(playerAId, playerBId);
  const highId = Math.max(playerAId, playerBId);

  // Legacy precomputed table can be stale/incomplete when ID mapping coverage is partial.
  // Keep reading it for fallback, but build authoritative H2H summary from oncourt_games.
  let q = sb
    .from("player_h2h")
    .select("*")
    .eq("player_a_id", lowId)
    .eq("player_b_id", highId);
  if (surface) q = q.eq("surface", surface);
  const { data: h2hLegacy } = await q.limit(10);

  const { data: matches } = await sb
    .from("oncourt_games")
    .select("winner_id, loser_id, tour_id, round_id, result, date")
    .or(`and(winner_id.eq.${playerAId},loser_id.eq.${playerBId}),and(winner_id.eq.${playerBId},loser_id.eq.${playerAId})`)
    .order("date", { ascending: false })
    .limit(200);

  const tourIds = [...new Set((matches ?? []).map((m) => num(m.tour_id)).filter((id) => id > 0))];
  const tours: Row[] = [];
  for (let i = 0; i < tourIds.length; i += 200) {
    const chunk = tourIds.slice(i, i + 200);
    const { data } = await sb.from("oncourt_tours").select("id, name, court_id").in("id", chunk);
    if (data?.length) tours.push(...data);
  }
  const tourMap: Record<number, Row> = {};
  for (const t of tours) tourMap[num(t.id)] = t;

  const courtIds = [...new Set(tours.map((t) => num(t.court_id)).filter((id) => id > 0))];
  const courtMap: Record<number, string> = {};
  if (courtIds.length) {
    const { data: courts } = await sb.from("oncourt_courts").select("id, name").in("id", courtIds);
    for (const c of courts ?? []) courtMap[num(c.id)] = str(c.name);
  }

  const summaryBySurface: Record<string, { wins_a: number; wins_b: number; match_count: number; last_match_date: string | null }> = {};
  const pushSummary = (surf: string, winnerId: number, matchDate: string) => {
    if (!summaryBySurface[surf]) {
      summaryBySurface[surf] = { wins_a: 0, wins_b: 0, match_count: 0, last_match_date: null };
    }
    const rec = summaryBySurface[surf];
    if (winnerId === lowId) rec.wins_a += 1;
    else if (winnerId === highId) rec.wins_b += 1;
    rec.match_count += 1;
    if (matchDate && (!rec.last_match_date || matchDate > rec.last_match_date)) rec.last_match_date = matchDate;
  };

  const enriched = [];
  for (const m of matches ?? []) {
    const t = tourMap[num(m.tour_id)];
    const courtName = courtMap[num(t?.court_id)] ?? "";
    const surf = surfaceFromCourtName(courtName);
    const d = str(m.date);
    pushSummary("Overall", num(m.winner_id), d);
    pushSummary(surf, num(m.winner_id), d);
    enriched.push({ ...m, tournament: str(t?.name), surface: surf });
  }

  const computedSummary = Object.entries(summaryBySurface)
    .map(([surf, rec]) => ({
      player_a_id: lowId,
      player_b_id: highId,
      surface: surf,
      wins_a: rec.wins_a,
      wins_b: rec.wins_b,
      match_count: rec.match_count,
      last_match_date: rec.last_match_date,
    }))
    .sort((a, b) => {
      if (a.surface === "Overall") return -1;
      if (b.surface === "Overall") return 1;
      return a.surface.localeCompare(b.surface);
    });

  return {
    summary: computedSummary.length ? computedSummary : (h2hLegacy ?? []),
    recent_matches: enriched,
    player_a_id: playerAId,
    player_b_id: playerBId,
  };
}

/* ── Player record at tournament ──────────────────────────── */

export async function playerRecordAtTournament(playerId: number, tournamentName: string): Promise<Row> {
  const searchTerms = resolveSearchTerms(tournamentName);
  let tours: Row[] = [];
  for (const term of searchTerms) {
    const { data } = await sb
      .from("oncourt_tours")
      .select("id, name, date")
      .ilike("name", `%${term}%`)
      .limit(100);
    if (data?.length) tours = [...tours, ...data];
  }
  tours = tours.filter((t) => isMainTour(str(t.name)));
  if (!tours.length) return { wins: 0, losses: 0, matches: [], tournament: tournamentName };

  const tourIds = tours.map((t: Row) => num(t.id));

  const { data: wins } = await sb
    .from("oncourt_games")
    .select("winner_id, loser_id, tour_id, round_id, result, date")
    .eq("winner_id", playerId)
    .in("tour_id", tourIds)
    .order("date", { ascending: false })
    .limit(200);

  const { data: losses } = await sb
    .from("oncourt_games")
    .select("winner_id, loser_id, tour_id, round_id, result, date")
    .eq("loser_id", playerId)
    .in("tour_id", tourIds)
    .order("date", { ascending: false })
    .limit(200);

  const allMatches = [...(wins ?? []), ...(losses ?? [])]
    .sort((a, b) => String(b.date).localeCompare(String(a.date)));

  const toEnrich = allMatches.slice(0, 30);
  const opponentIds = [...new Set(toEnrich.map((m) => (num(m.winner_id) === playerId ? num(m.loser_id) : num(m.winner_id))))];
  const { data: opponents } = opponentIds.length > 0
    ? await sb.from("oncourt_players").select("id, name").in("id", opponentIds)
    : { data: [] };
  const oppMap = new Map((opponents ?? []).map((o) => [num(o.id), str(o.name)]));

  const enriched = toEnrich.map((m) => {
    const opponentId = num(m.winner_id) === playerId ? num(m.loser_id) : num(m.winner_id);
    const won = num(m.winner_id) === playerId;
    return {
      date: m.date,
      opponent: oppMap.get(opponentId) ?? `Player ${opponentId}`,
      won,
      score: m.result,
      round_id: m.round_id,
    };
  });

  return {
    tournament: tournamentName,
    wins: (wins ?? []).length,
    losses: (losses ?? []).length,
    win_pct: (wins ?? []).length + (losses ?? []).length > 0
      ? Math.round(((wins ?? []).length / ((wins ?? []).length + (losses ?? []).length)) * 1000) / 10
      : 0,
    recent_matches: enriched.slice(0, 20),
  };
}

/* ── Player recent form ───────────────────────────────────── */

export async function playerRecentForm(playerId: number): Promise<Row> {
  const { data: activity } = await sb
    .from("player_recent_activity")
    .select("*")
    .eq("player_id", playerId)
    .maybeSingle();

  const { data: recentWins } = await sb
    .from("oncourt_games")
    .select("winner_id, loser_id, tour_id, result, date")
    .eq("winner_id", playerId)
    .order("date", { ascending: false })
    .limit(10);

  const { data: recentLosses } = await sb
    .from("oncourt_games")
    .select("winner_id, loser_id, tour_id, result, date")
    .eq("loser_id", playerId)
    .order("date", { ascending: false })
    .limit(10);

  const allRecent = [...(recentWins ?? []), ...(recentLosses ?? [])]
    .sort((a, b) => String(b.date).localeCompare(String(a.date)))
    .slice(0, 10);

  const enriched = [];
  for (const m of allRecent) {
    const oppId = num(m.winner_id) === playerId ? num(m.loser_id) : num(m.winner_id);
    const { data: opp } = await sb.from("oncourt_players").select("name").eq("id", oppId).maybeSingle();
    const { data: tour } = await sb.from("oncourt_tours").select("name").eq("id", m.tour_id).maybeSingle();
    enriched.push({
      date: m.date,
      opponent: opp?.name ?? `Player ${oppId}`,
      tournament: tour?.name ?? "",
      won: num(m.winner_id) === playerId,
      score: m.result,
    });
  }

  return {
    activity: activity ?? null,
    last_10_matches: enriched,
  };
}

/* ── Record vs lefties (always returns surface breakdown) ── */

/** Use precomputed player_vs_leftie_stats when available — avoids URL-length limits with 1200+ leftie IDs. */
async function playerRecordVsLeftiesFromStats(playerId: number): Promise<Row | null> {
  const { data: rows } = await sb
    .from("player_vs_leftie_stats")
    .select("surface, win_pct_vs_leftie, match_count_vs_leftie")
    .eq("player_id", playerId);
  if (!rows?.length) return null;

  const bySurface: Record<string, { wins: number; losses: number; win_pct: number }> = {};
  let totalW = 0, totalL = 0;
  for (const r of rows) {
    const surf = str(r.surface) || "Hard";
    const mc = num(r.match_count_vs_leftie);
    const wp = num(r.win_pct_vs_leftie, 0.5);
    const wins = mc > 0 ? Math.round(wp * mc) : 0;
    const losses = mc - wins;
    totalW += wins;
    totalL += losses;
    bySurface[surf] = { wins, losses, win_pct: mc > 0 ? Math.round(wp * 1000) / 10 : 0 };
  }
  const total = totalW + totalL;
  return {
    overall: { wins: totalW, losses: totalL, total, win_pct: total > 0 ? Math.round((totalW / total) * 1000) / 10 : 0 },
    by_surface: bySurface,
    note: "Precomputed from ATP + Challenger matches. Leftie list from OnCourt categories.",
  };
}

const LEFTIE_CHUNK_SIZE = 200;

export async function playerRecordVsLefties(playerId: number): Promise<Row> {
  let precomputed: Row | null = null;
  try {
    precomputed = await playerRecordVsLeftiesFromStats(playerId);
  } catch {
    // Table may not exist; fall back to live query
  }
  if (precomputed) return precomputed;

  const lefties = await fetchAllLeftieIds();
  if (!lefties.length) return { overall: { wins: 0, losses: 0 }, note: "No leftie reference data" };

  const leftieArr = [...new Set(lefties.filter((id) => id > 0))];
  const allWins: Row[] = [];
  const allLosses: Row[] = [];

  for (let i = 0; i < leftieArr.length; i += LEFTIE_CHUNK_SIZE) {
    const chunk = leftieArr.slice(i, i + LEFTIE_CHUNK_SIZE);
    const [winsRes, lossesRes] = await Promise.all([
      sb.from("oncourt_games").select("winner_id, loser_id, tour_id, result, date").eq("winner_id", playerId).in("loser_id", chunk).order("date", { ascending: false }).limit(500),
      sb.from("oncourt_games").select("winner_id, loser_id, tour_id, result, date").eq("loser_id", playerId).in("winner_id", chunk).order("date", { ascending: false }).limit(500),
    ]);
    if (winsRes.data?.length) allWins.push(...winsRes.data);
    if (lossesRes.data?.length) allLosses.push(...lossesRes.data);
  }

  const tourIds = [...new Set([...allWins, ...allLosses].map((m) => num(m.tour_id)))];
  const toursList: Row[] = [];
  for (let i = 0; i < tourIds.length; i += 200) {
    const chunk = tourIds.slice(i, i + 200);
    const { data } = await sb.from("oncourt_tours").select("id, court_id").in("id", chunk);
    if (data?.length) toursList.push(...data);
  }
  const tours = toursList;
  const { data: courts } = await sb.from("oncourt_courts").select("id, name").limit(50);
  const courtToSurface: Record<number, string> = {};
  for (const c of courts ?? []) {
    const n = str(c.name).toUpperCase();
    if (n.includes("CLAY")) courtToSurface[num(c.id)] = "Clay";
    else if (n.includes("GRASS")) courtToSurface[num(c.id)] = "Grass";
    else if (n.includes("I.HARD") || n === "I.HARD" || n.includes("INDOOR")) courtToSurface[num(c.id)] = "I.hard";
    else if (n.includes("CARPET")) courtToSurface[num(c.id)] = "Carpet";
    else courtToSurface[num(c.id)] = "Hard";
  }
  const tourToSurface: Record<number, string> = {};
  for (const t of tours ?? []) tourToSurface[num(t.id)] = courtToSurface[num(t.court_id)] ?? "Hard";

  const bySurface: Record<string, { wins: number; losses: number }> = {};
  for (const m of allWins) {
    const s = tourToSurface[num(m.tour_id)] ?? "Hard";
    if (!bySurface[s]) bySurface[s] = { wins: 0, losses: 0 };
    bySurface[s].wins += 1;
  }
  for (const m of allLosses) {
    const s = tourToSurface[num(m.tour_id)] ?? "Hard";
    if (!bySurface[s]) bySurface[s] = { wins: 0, losses: 0 };
    bySurface[s].losses += 1;
  }

  const surfaceBreakdown: Record<string, { wins: number; losses: number; win_pct: number }> = {};
  for (const [s, r] of Object.entries(bySurface)) {
    const total = r.wins + r.losses;
    surfaceBreakdown[s] = { ...r, win_pct: total > 0 ? Math.round((r.wins / total) * 1000) / 10 : 0 };
  }

  const totalW = allWins.length;
  const totalL = allLosses.length;
  const total = totalW + totalL;

  return {
    overall: {
      wins: totalW,
      losses: totalL,
      total,
      win_pct: total > 0 ? Math.round((totalW / total) * 1000) / 10 : 0,
    },
    by_surface: surfaceBreakdown,
    note: "ATP + Challenger matches vs left-handed opponents (OnCourt categories). Chunked query.",
  };
}

/* ── Record vs big servers (hold_pct >= 68% on surface) ───── */

export async function playerRecordVsBigServer(playerId: number): Promise<Row> {
  const { data: rows } = await sb
    .from("player_vs_big_server_stats")
    .select("surface, win_pct_vs_big_server, match_count_vs_big_server")
    .eq("player_id", playerId);
  if (!rows?.length) return { overall: { wins: 0, losses: 0 }, note: "No vs-big-server data for this player" };

  const bySurface: Record<string, { wins: number; losses: number; win_pct: number; matches: number }> = {};
  let totalW = 0, totalL = 0;
  for (const r of rows) {
    const surf = str(r.surface) || "Hard";
    const mc = num(r.match_count_vs_big_server);
    const wp = num(r.win_pct_vs_big_server, 0.5);
    const wins = mc > 0 ? Math.round(wp * mc) : 0;
    const losses = mc - wins;
    totalW += wins;
    totalL += losses;
    bySurface[surf] = {
      wins,
      losses,
      win_pct: mc > 0 ? Math.round(wp * 1000) / 10 : 0,
      matches: mc,
    };
  }
  const total = totalW + totalL;
  return {
    overall: {
      wins: totalW,
      losses: totalL,
      total,
      win_pct: total > 0 ? Math.round((totalW / total) * 1000) / 10 : 0,
    },
    by_surface: bySurface,
    note: "Big servers = opponents who win 68%+ of their service points (SPW) on that surface. Not per-game hold %.",
  };
}

/* ── Record at altitude ───────────────────────────────────── */

export async function playerRecordAtAltitude(playerId: number): Promise<Row> {
  const { data: altStats } = await sb
    .from("player_altitude_stats")
    .select("*")
    .eq("player_id", playerId);

  const { data: altTours } = await sb
    .from("oncourt_tours")
    .select("id, name, altitude")
    .gte("altitude", 200)
    .limit(500);
  const altTourIds = (altTours ?? []).map((t: Row) => num(t.id));

  let wins = 0, losses = 0;
  if (altTourIds.length) {
    const { count: wc } = await sb
      .from("oncourt_games")
      .select("*", { count: "exact", head: true })
      .eq("winner_id", playerId)
      .in("tour_id", altTourIds);
    const { count: lc } = await sb
      .from("oncourt_games")
      .select("*", { count: "exact", head: true })
      .eq("loser_id", playerId)
      .in("tour_id", altTourIds);
    wins = wc ?? 0;
    losses = lc ?? 0;
  }

  return {
    altitude_stats: altStats ?? [],
    record: { wins, losses, total: wins + losses, win_pct: wins + losses > 0 ? Math.round((wins / (wins + losses)) * 1000) / 10 : 0 },
  };
}

/* ── Record vs top N ──────────────────────────────────────── */

export async function playerRecordVsRankRange(playerId: number, maxRank: number): Promise<Row> {
  const { data: topPlayers } = await sb
    .from("oncourt_players")
    .select("id")
    .lte("atp_rank", maxRank)
    .gt("atp_rank", 0)
    .limit(5000);
  const topIds = (topPlayers ?? []).map((p: Row) => num(p.id));
  if (!topIds.length) return { wins: 0, losses: 0 };

  const { count: wc } = await sb
    .from("oncourt_games")
    .select("*", { count: "exact", head: true })
    .eq("winner_id", playerId)
    .in("loser_id", topIds);
  const { count: lc } = await sb
    .from("oncourt_games")
    .select("*", { count: "exact", head: true })
    .eq("loser_id", playerId)
    .in("winner_id", topIds);

  const w = wc ?? 0;
  const l = lc ?? 0;
  return { wins: w, losses: l, total: w + l, win_pct: w + l > 0 ? Math.round((w / (w + l)) * 1000) / 10 : 0, max_rank: maxRank };
}

/* ── Tournament entrants (from Pinnacle outright odds) ──────── */

export async function tournamentEntrants(tournamentName: string, playerName?: string): Promise<Row> {
  const searchTerms = resolveSearchTerms(tournamentName);
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

  for (const term of searchTerms) {
    const { data: latest } = await sb
      .from("tournament_outright_snapshot")
      .select("capture_date")
      .ilike("tournament_name", `%${term}%`)
      .in("capture_date", [today, yesterday])
      .order("capture_date", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (!latest?.capture_date) continue;

    const { data, error } = await sb
      .from("tournament_outright_snapshot")
      .select("capture_date, tournament_name, player_name, odds, rank_in_market")
      .ilike("tournament_name", `%${term}%`)
      .eq("capture_date", latest.capture_date)
      .order("rank_in_market", { ascending: true })
      .limit(200);
    if (error) return { found: false, note: "Outright snapshot table may not exist. Run daily-odds to populate." };
    if (!data?.length) continue;

    const players = data.map((r: Row) => ({
      name: str(r.player_name),
      odds: num(r.odds),
      rank: num(r.rank_in_market),
    }));
    const captureDate = str(latest.capture_date);
    const tName = str(data[0]?.tournament_name);

    if (playerName) {
      const qLower = playerName.toLowerCase().trim();
      const match = players.find((p: { name: string }) =>
        p.name.toLowerCase().includes(qLower) || qLower.includes(p.name.toLowerCase().split(" ").pop() ?? "")
      );
      return {
        tournament: tName,
        capture_date: captureDate,
        playing: !!match,
        player: match ? match.name : null,
        odds: match ? match.odds : null,
        rank: match ? match.rank : null,
        total_entrants: players.length,
      };
    }

    return {
      tournament: tName,
      capture_date: captureDate,
      players: players.slice(0, 50),
      total_entrants: players.length,
    };
  }
  return { found: false, note: "No outright data for this tournament." };
}

/* ── Tournament info ──────────────────────────────────────── */

export async function tournamentInfo(tournamentName: string): Promise<Row> {
  const searchTerms = resolveSearchTerms(tournamentName);
  let tours: Row[] = [];
  for (const term of searchTerms) {
    const { data } = await sb
      .from("oncourt_tours")
      .select("id, name, date, rank, country, court_id, altitude")
      .ilike("name", `%${term}%`)
      .order("date", { ascending: false })
      .limit(20);
    if (data?.length) tours = [...tours, ...data];
  }
  tours = tours.filter((t) => isMainTour(str(t.name)));
  if (!tours?.length) return { found: false, name: tournamentName };

  const courtIds = [...new Set((tours).map((t: Row) => num(t.court_id)))];
  const { data: courts } = await sb.from("oncourt_courts").select("id, name").in("id", courtIds);
  const courtMap: Record<number, string> = {};
  for (const c of courts ?? []) courtMap[num(c.id)] = str(c.name);

  const latestTour = tours[0];
  const tourIds = tours.map((t: Row) => num(t.id));

  const { data: gameAvg } = await sb
    .from("tournament_game_averages")
    .select("*")
    .in("tour_id", tourIds)
    .limit(5);

  const { data: serveProfile } = await sb
    .from("tournament_serve_profile")
    .select("*")
    .in("tour_id", tourIds)
    .limit(5);

  return {
    found: true,
    name: str(latestTour.name),
    surface: courtMap[num(latestTour.court_id)] ?? "Unknown",
    country: str(latestTour.country),
    altitude: latestTour.altitude,
    rank: latestTour.rank,
    editions: tours.map((t: Row) => ({ year: str(t.date).slice(0, 4), name: str(t.name) })),
    game_averages: gameAvg ?? [],
    serve_profile: serveProfile ?? [],
  };
}

/* ── Match prediction (wraps fair odds as analyst view) ──── */

function estimateHandicap(winProb: number, expectedTotal: number): { favouredPlayer: 1 | 2; estimatedMargin: number; handicapLine: number } {
  const p = Math.max(winProb, 1 - winProb);
  const favouredPlayer: 1 | 2 = winProb >= 0.5 ? 1 : 2;
  const marginFactor = (p - 0.5) * 2;
  const estimatedMargin = Math.round(marginFactor * expectedTotal * 0.3 * 10) / 10;
  const handicapLine = Math.round(estimatedMargin * 2) / 2;
  return { favouredPlayer, estimatedMargin, handicapLine };
}

export async function matchPrediction(playerName?: string): Promise<Row[]> {
  const MAX_CHAT_MATCH_ROWS = 40;
  const { data: odds } = await sb
    .from("daily_fair_odds")
    .select("id, tour_id, player1_id, player2_id, surface, p1_win_prob, p2_win_prob, odds1, odds2, expected_total_games, confidence")
    .order("tour_id")
    .limit(200);
  if (!odds?.length) return [{ note: "No matches found for today." }];

  const tIds = new Set<number>();
  for (const r of odds) {
    if (r.tour_id) tIds.add(r.tour_id as number);
  }

  const { data: tours } = await sb.from("oncourt_tours").select("id, name, rank").in("id", Array.from(tIds));

  const atpTourIds = new Set<number>();
  const tMap: Record<number, string> = {};
  for (const t of tours ?? []) {
    const name = str(t.name).toUpperCase();
    const rank = num(t.rank);
    const isChallenger = name.includes("CHALLENGER") || name.includes("CH ") || rank > 3;
    const isQualifying = name.includes("QUALIF");
    if (!isChallenger && !isQualifying) {
      atpTourIds.add(num(t.id));
      tMap[num(t.id)] = str(t.name);
    }
  }

  const atpOdds = odds.filter((r: Row) => atpTourIds.has(num(r.tour_id)));
  if (!atpOdds.length) return [{ note: "No ATP main tour matches found for today." }];

  const pIds = new Set<number>();
  for (const r of atpOdds) {
    if (r.player1_id) pIds.add(r.player1_id as number);
    if (r.player2_id) pIds.add(r.player2_id as number);
  }

  const { data: players } = await sb.from("oncourt_players").select("id, name, atp_rank").in("id", Array.from(pIds));

  const pMap: Record<number, { name: string; rank: number }> = {};
  for (const p of players ?? []) pMap[num(p.id)] = { name: str(p.name), rank: num(p.atp_rank) };

  const rows = atpOdds.map((r: Row) => {
    const p1prob = num(r.p1_win_prob);
    const etg = num(r.expected_total_games);
    const hcap = estimateHandicap(p1prob, etg);
    const p1 = pMap[num(r.player1_id)] ?? { name: "Unknown", rank: 0 };
    const p2 = pMap[num(r.player2_id)] ?? { name: "Unknown", rank: 0 };

    return {
      player1: p1.name,
      player1_rank: p1.rank,
      player2: p2.name,
      player2_rank: p2.rank,
      tournament: tMap[num(r.tour_id)] ?? "",
      surface: r.surface,
      p1_win_pct: Math.round(p1prob * 1000) / 10,
      p2_win_pct: Math.round((1 - p1prob) * 1000) / 10,
      expected_total_games: etg,
      favoured: hcap.favouredPlayer === 1 ? p1.name : p2.name,
      estimated_game_margin: hcap.estimatedMargin,
      suggested_handicap_line: hcap.handicapLine,
      confidence: r.confidence,
    };
  });

  if (playerName) {
    const q = playerName.toLowerCase();
    return rows.filter((r: Row) =>
      str(r.player1).toLowerCase().includes(q) || str(r.player2).toLowerCase().includes(q)
    );
  }
  if (rows.length <= MAX_CHAT_MATCH_ROWS) return rows;
  return [
    ...rows.slice(0, MAX_CHAT_MATCH_ROWS),
    {
      note: `Showing first ${MAX_CHAT_MATCH_ROWS} of ${rows.length} ATP main-draw matches for chat brevity.`,
      total_matches: rows.length,
    },
  ];
}

function isDoublesName(name: string): boolean {
  return (name ?? "").includes("/") || (name ?? "").includes("&");
}

function isMainTourFixture(tourName: string, rank?: number | null): boolean {
  const up = (tourName ?? "").toUpperCase();
  if (!up) return true;
  if (up.includes("CHALLENGER") || up.includes(" CH ") || up.includes(" ATP CH ")) return false;
  if (up.includes("QUALIF")) return false;
  if (typeof rank === "number" && Number.isFinite(rank) && rank > 3) return false;
  return true;
}

function normMatchName(s: string): string {
  return (s ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/-/g, "")
    .replace(/'/g, "")
    .trim();
}

function tokenizeMatchName(name: string): string[] {
  const cleaned = (name ?? "")
    .replace(/\s*\([^)]*\)/g, " ")
    .replace(/\s*\[[^\]]*\]/g, " ")
    .replace(/,/g, " ")
    .replace(/-/g, " ")
    .replace(/'/g, " ")
    .trim();
  return cleaned
    .split(/\s+/)
    .map(normMatchName)
    .filter(Boolean)
    .filter((t) => !/^[a-z]$/.test(t));
}

function surnameKeysForMatch(name: string): string[] {
  const t = tokenizeMatchName(name);
  if (!t.length) return [];
  const out = new Set<string>();
  const n = t.length;
  out.add(t[n - 1]);
  if (n >= 2) {
    out.add(t[n - 2]);
    out.add(`${t[n - 2]} ${t[n - 1]}`);
    out.add(`${t[n - 2]}${t[n - 1]}`);
  }
  return Array.from(out);
}

function firstWordForMatch(name: string): string {
  const t = tokenizeMatchName(name);
  return t.length ? t[0] : "";
}

function fullNameForMatch(name: string): string {
  return tokenizeMatchName(name).join(" ");
}

function pairKeysForMatch(a: string, b: string): string[] {
  const aKeys = surnameKeysForMatch(a);
  const bKeys = surnameKeysForMatch(b);
  const out = new Set<string>();
  for (const ka of aKeys) {
    for (const kb of bKeys) out.add(`${ka}|${kb}`);
  }
  return Array.from(out);
}

type FairRowForValue = {
  id: number;
  player1_name: string;
  player2_name: string;
  surface: string;
  confidence: string;
  odds1: number;
  odds2: number;
  p1_win_pct: number;
  p2_win_pct: number;
};

type PinRowForValue = {
  player1_name: string;
  player2_name: string;
  odds1: number;
  odds2: number;
};

export async function valuePicksToday(limit = 5, minValuePct = 3): Promise<Row> {
  const minWinPctGuard = 35;
  const maxFairOddsGuard = 4.5;
  const fairLimit = 2000;
  const { data: odds } = await sb
    .from("daily_fair_odds")
    .select("id, tour_id, player1_id, player2_id, surface, p1_win_prob, p2_win_prob, odds1, odds2, confidence")
    .order("tour_id")
    .limit(fairLimit);
  if (!odds?.length) {
    return { found: false, message: "No daily fair-odds rows found for today." };
  }

  const playerIds = [...new Set(odds.flatMap((r) => [num(r.player1_id), num(r.player2_id)]).filter((id) => id > 0))];
  const tourIds = [...new Set(odds.map((r) => num(r.tour_id)).filter((id) => id > 0))];

  const BATCH = 200;
  const playerRows: Row[] = [];
  for (let i = 0; i < playerIds.length; i += BATCH) {
    const chunk = playerIds.slice(i, i + BATCH);
    const { data } = await sb.from("oncourt_players").select("id, name").in("id", chunk);
    if (data?.length) playerRows.push(...data);
  }
  const tourRows: Row[] = [];
  for (let i = 0; i < tourIds.length; i += BATCH) {
    const chunk = tourIds.slice(i, i + BATCH);
    const { data } = await sb.from("oncourt_tours").select("id, name, rank").in("id", chunk);
    if (data?.length) tourRows.push(...data);
  }

  const playerMap = new Map<number, string>(playerRows.map((p) => [num(p.id), str(p.name)]));
  const tourMap = new Map<number, { name: string; rank: number | null }>(
    tourRows.map((t) => {
      const rankVal = t.rank != null ? Number(t.rank) : NaN;
      return [num(t.id), { name: str(t.name), rank: Number.isFinite(rankVal) ? rankVal : null }];
    })
  );

  const fairRows: FairRowForValue[] = [];
  for (const r of odds) {
    const id = num(r.id);
    const p1 = playerMap.get(num(r.player1_id)) ?? "";
    const p2 = playerMap.get(num(r.player2_id)) ?? "";
    if (!id || !p1 || !p2 || isDoublesName(p1) || isDoublesName(p2)) continue;
    const tMeta = tourMap.get(num(r.tour_id));
    if (!isMainTourFixture(tMeta?.name ?? "", tMeta?.rank ?? null)) continue;
    fairRows.push({
      id,
      player1_name: p1,
      player2_name: p2,
      surface: str(r.surface),
      confidence: str(r.confidence).toLowerCase() || "n/a",
      odds1: num(r.odds1),
      odds2: num(r.odds2),
      p1_win_pct: Math.round(num(r.p1_win_prob) * 1000) / 10,
      p2_win_pct: Math.round(num(r.p2_win_prob) * 1000) / 10,
    });
  }
  if (!fairRows.length) {
    return { found: false, message: "No ATP main-draw fair-odds rows found for today." };
  }

  const now = new Date();
  const today = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-${String(now.getUTCDate()).padStart(2, "0")}`;
  const y = new Date(now.getTime() - 86400000);
  const yesterday = `${y.getUTCFullYear()}-${String(y.getUTCMonth() + 1).padStart(2, "0")}-${String(y.getUTCDate()).padStart(2, "0")}`;

  let captureDate = today;
  let { data: snap } = await sb
    .from("bookmaker_odds_snapshot")
    .select("player1_name, player2_name, odds1, odds2, league")
    .eq("bookmaker", "Pinnacle")
    .eq("capture_date", today)
    .order("captured_at", { ascending: false })
    .limit(2000);

  if (!snap?.length) {
    const fallback = await sb
      .from("bookmaker_odds_snapshot")
      .select("player1_name, player2_name, odds1, odds2, league")
      .eq("bookmaker", "Pinnacle")
      .eq("capture_date", yesterday)
      .order("captured_at", { ascending: false })
      .limit(2000);
    snap = fallback.data ?? [];
    captureDate = yesterday;
  }

  const pinRows: PinRowForValue[] = (snap ?? [])
    .filter((r) => str(r.league) === "ATP")
    .map((r) => ({
      player1_name: str(r.player1_name),
      player2_name: str(r.player2_name),
      odds1: num(r.odds1),
      odds2: num(r.odds2),
    }))
    .filter((r) => r.player1_name && r.player2_name && !isDoublesName(r.player1_name) && !isDoublesName(r.player2_name));

  if (!pinRows.length) {
    return {
      found: false,
      capture_date: captureDate,
      message: "No Pinnacle ATP snapshot rows found for today/yesterday.",
    };
  }

  const pinLookup = new Map<string, Array<{ row: PinRowForValue; reversed: boolean }>>();
  const addLookup = (key: string, val: { row: PinRowForValue; reversed: boolean }) => {
    if (!key) return;
    const arr = pinLookup.get(key);
    if (arr) arr.push(val);
    else pinLookup.set(key, [val]);
  };
  for (const pin of pinRows) {
    for (const key of pairKeysForMatch(pin.player1_name, pin.player2_name)) {
      addLookup(key, { row: pin, reversed: false });
    }
    for (const key of pairKeysForMatch(pin.player2_name, pin.player1_name)) {
      addLookup(key, { row: pin, reversed: true });
    }
  }

  const matched = new Map<number, { pinOdds1: number; pinOdds2: number }>();
  const usedPin = new Set<PinRowForValue>();
  for (const fo of fairRows) {
    const candidateMap = new Map<string, { row: PinRowForValue; reversed: boolean; score: number }>();
    for (const key of pairKeysForMatch(fo.player1_name, fo.player2_name)) {
      for (const ent of pinLookup.get(key) ?? []) {
        const id = `${ent.row.player1_name}|${ent.row.player2_name}|${ent.reversed ? "R" : "N"}`;
        const prev = candidateMap.get(id);
        if (prev) prev.score += 1;
        else candidateMap.set(id, { row: ent.row, reversed: ent.reversed, score: 1 });
      }
    }
    if (!candidateMap.size) continue;

    const foP1First = firstWordForMatch(fo.player1_name);
    const foP2First = firstWordForMatch(fo.player2_name);
    const foP1Full = fullNameForMatch(fo.player1_name);
    const foP2Full = fullNameForMatch(fo.player2_name);

    for (const cand of candidateMap.values()) {
      const pinP1 = cand.reversed ? cand.row.player2_name : cand.row.player1_name;
      const pinP2 = cand.reversed ? cand.row.player1_name : cand.row.player2_name;
      if (foP1First && foP1First === firstWordForMatch(pinP1)) cand.score += 2;
      if (foP2First && foP2First === firstWordForMatch(pinP2)) cand.score += 2;
      if (foP1Full && foP1Full === fullNameForMatch(pinP1)) cand.score += 4;
      if (foP2Full && foP2Full === fullNameForMatch(pinP2)) cand.score += 4;
    }

    const ranked = Array.from(candidateMap.values())
      .filter((c) => !usedPin.has(c.row))
      .sort((a, b) => b.score - a.score);
    if (!ranked.length) continue;
    if (ranked.length > 1 && ranked[0].score === ranked[1].score) continue;

    const best = ranked[0];
    usedPin.add(best.row);
    matched.set(fo.id, {
      pinOdds1: best.reversed ? best.row.odds2 : best.row.odds1,
      pinOdds2: best.reversed ? best.row.odds1 : best.row.odds2,
    });
  }

  const confBoost = (c: string): number => (c === "high" ? 1 : c === "medium" ? 0.5 : 0);
  const picks = fairRows
    .map((fo) => {
      const pin = matched.get(fo.id);
      if (!pin) return null;
      const v1 = fo.odds1 > 1 && pin.pinOdds1 > 1 ? Math.round((pin.pinOdds1 / fo.odds1 - 1) * 10000) / 100 : -999;
      const v2 = fo.odds2 > 1 && pin.pinOdds2 > 1 ? Math.round((pin.pinOdds2 / fo.odds2 - 1) * 10000) / 100 : -999;
      if (v1 < minValuePct && v2 < minValuePct) return null;
      const p1Side = v1 >= v2;
      const sideWinPct = p1Side ? fo.p1_win_pct : fo.p2_win_pct;
      const sideFairOdds = p1Side ? fo.odds1 : fo.odds2;
      if (sideWinPct < minWinPctGuard) return null;
      if (sideFairOdds > maxFairOddsGuard) return null;
      return {
        matchup: `${fo.player1_name} vs ${fo.player2_name}`,
        player: p1Side ? fo.player1_name : fo.player2_name,
        opponent: p1Side ? fo.player2_name : fo.player1_name,
        side: p1Side ? "P1" : "P2",
        value_pct: p1Side ? v1 : v2,
        fair_odds: sideFairOdds,
        pinnacle_odds: p1Side ? pin.pinOdds1 : pin.pinOdds2,
        win_pct: sideWinPct,
        confidence: fo.confidence,
        surface: fo.surface,
        rank_score: (p1Side ? v1 : v2) + confBoost(fo.confidence),
      };
    })
    .filter((x): x is NonNullable<typeof x> => !!x)
    .sort((a, b) => b.rank_score - a.rank_score || b.value_pct - a.value_pct)
    .slice(0, Math.max(1, Math.min(15, Math.floor(limit))));

  return {
    found: true,
    capture_date: captureDate,
    min_value_pct: minValuePct,
    guard_min_win_pct: minWinPctGuard,
    guard_max_fair_odds: maxFairOddsGuard,
    fair_rows: fairRows.length,
    pinnacle_rows: pinRows.length,
    matched_rows: matched.size,
    picks,
  };
}

/* ── Player W-L record by surface ────────────────────────── */

export async function playerRecordBySurface(playerId: number, surface?: string): Promise<Row> {
  const { data: courts } = await sb.from("oncourt_courts").select("id, name").limit(50);
  const courtToSurface: Record<number, string> = {};
  for (const c of courts ?? []) {
    const n = str(c.name).toUpperCase();
    if (n.includes("CLAY")) courtToSurface[num(c.id)] = "Clay";
    else if (n.includes("GRASS")) courtToSurface[num(c.id)] = "Grass";
    else courtToSurface[num(c.id)] = "Hard";
  }

  const { data: wins } = await sb
    .from("oncourt_games")
    .select("tour_id")
    .eq("winner_id", playerId);
  const { data: losses } = await sb
    .from("oncourt_games")
    .select("tour_id")
    .eq("loser_id", playerId);

  const tourIds = new Set<number>();
  for (const m of [...(wins ?? []), ...(losses ?? [])]) tourIds.add(num(m.tour_id));

  const { data: tours } = await sb
    .from("oncourt_tours")
    .select("id, court_id, name")
    .in("id", Array.from(tourIds))
    .limit(5000);

  const tourSurface: Record<number, string> = {};
  for (const t of tours ?? []) {
    const s = courtToSurface[num(t.court_id)] ?? "Hard";
    if (isMainTour(str(t.name))) tourSurface[num(t.id)] = s;
  }

  const bySurface: Record<string, { wins: number; losses: number }> = {};
  for (const m of wins ?? []) {
    const s = tourSurface[num(m.tour_id)];
    if (!s) continue;
    if (!bySurface[s]) bySurface[s] = { wins: 0, losses: 0 };
    bySurface[s].wins += 1;
  }
  for (const m of losses ?? []) {
    const s = tourSurface[num(m.tour_id)];
    if (!s) continue;
    if (!bySurface[s]) bySurface[s] = { wins: 0, losses: 0 };
    bySurface[s].losses += 1;
  }

  const result: Record<string, { wins: number; losses: number; win_pct: number }> = {};
  for (const [s, r] of Object.entries(bySurface)) {
    const total = r.wins + r.losses;
    result[s] = { ...r, win_pct: total > 0 ? Math.round((r.wins / total) * 1000) / 10 : 0 };
  }

  if (surface && surface !== "all") {
    const filtered = result[surface];
    if (filtered) return { surface, ...filtered };
    return { surface, wins: 0, losses: 0, win_pct: 0, note: `No matches found on ${surface}` };
  }

  return { by_surface: result };
}

/* ── Player record by round ───────────────────────────────── */

export async function playerRecordByRound(playerId: number): Promise<Row> {
  const ROUND_NAMES: Record<number, string> = {
    1: "R1", 2: "R2", 3: "R3",
    4: "Qualifying R1", 5: "Qualifying R2", 6: "Qualifying R3",
    7: "R16", 9: "Quarter-Final", 10: "Semi-Final", 12: "Final",
  };

  const { data: wins } = await sb
    .from("oncourt_games")
    .select("round_id")
    .eq("winner_id", playerId);
  const { data: losses } = await sb
    .from("oncourt_games")
    .select("round_id")
    .eq("loser_id", playerId);

  const rounds: Record<string, { wins: number; losses: number }> = {};
  for (const m of wins ?? []) {
    const rName = ROUND_NAMES[num(m.round_id)] ?? `Round ${m.round_id}`;
    if (!rounds[rName]) rounds[rName] = { wins: 0, losses: 0 };
    rounds[rName].wins += 1;
  }
  for (const m of losses ?? []) {
    const rName = ROUND_NAMES[num(m.round_id)] ?? `Round ${m.round_id}`;
    if (!rounds[rName]) rounds[rName] = { wins: 0, losses: 0 };
    rounds[rName].losses += 1;
  }

  return { by_round: rounds };
}

/* ── Tournament past winners ──────────────────────────────── */

export async function tournamentPastWinners(tournamentName: string): Promise<Row[]> {
  const searchTerms = resolveSearchTerms(tournamentName);
  let allTours: Row[] = [];
  for (const term of searchTerms) {
    const { data } = await sb
      .from("oncourt_tours")
      .select("id, name, date, rank")
      .ilike("name", `%${term}%`)
      .order("date", { ascending: false })
      .limit(50);
    if (data?.length) allTours = [...allTours, ...data];
  }
  if (!allTours.length) return [];

  const mainTours = allTours.filter((t) => isMainTour(str(t.name)));

  const byYear: Record<string, Row> = {};
  for (const t of mainTours.length ? mainTours : allTours) {
    const year = str(t.date).slice(0, 4);
    if (!byYear[year]) byYear[year] = t;
  }
  const tours = Object.values(byYear).sort((a, b) =>
    str(b.date).localeCompare(str(a.date))
  );

  const results = [];
  for (const t of tours.slice(0, 20)) {
    const { data: finals } = await sb
      .from("oncourt_games")
      .select("winner_id, loser_id, result")
      .eq("tour_id", num(t.id))
      .eq("round_id", 12)
      .limit(5);
    if (!finals?.length) continue;
    for (const f of finals) {
      const { data: winner } = await sb.from("oncourt_players").select("name").eq("id", f.winner_id).maybeSingle();
      if (winner?.name?.includes("/")) continue;
      const { data: runnerUp } = await sb.from("oncourt_players").select("name").eq("id", f.loser_id).maybeSingle();
      results.push({
        year: str(t.date).slice(0, 4),
        tournament: str(t.name),
        winner: winner?.name ?? "",
        runner_up: runnerUp?.name ?? "",
        score: f.result,
      });
      break;
    }
  }
  return results;
}

/**
 * Match-level results for a specific tournament edition, with optional round/player filters.
 * Example: French Open 2025, round=QF, player=Alcaraz.
 */
export async function tournamentEditionResults(
  tournamentName: string,
  seasonYear?: number,
  round?: string,
  playerName?: string
): Promise<Row> {
  const searchTerms = resolveSearchTerms(tournamentName);
  let allTours: Row[] = [];
  for (const term of searchTerms) {
    const { data } = await sb
      .from("oncourt_tours")
      .select("id, name, date, rank")
      .ilike("name", `%${term}%`)
      .order("date", { ascending: false })
      .limit(120);
    if (data?.length) allTours = [...allTours, ...data];
  }
  if (!allTours.length) {
    return {
      found: false,
      tournament: tournamentName,
      message: "No tournament editions found for that name.",
    };
  }

  const mainTours = allTours.filter((t) => isMainTour(str(t.name)));
  const tours = mainTours.length ? mainTours : allTours;
  const availableYears = [...new Set(tours.map((t) => str(t.date).slice(0, 4)).filter(Boolean))]
    .sort((a, b) => b.localeCompare(a));

  const latestYear = availableYears.length ? Number(availableYears[0]) : undefined;
  const targetYear =
    seasonYear && Number.isFinite(seasonYear) && seasonYear > 1900 ? seasonYear : latestYear;
  if (!targetYear) {
    return {
      found: false,
      tournament: tournamentName,
      available_years: availableYears,
      message: "No valid season year found for this tournament.",
    };
  }

  const yearTours = tours.filter((t) => str(t.date).startsWith(`${targetYear}`));
  if (!yearTours.length) {
    return {
      found: false,
      tournament: tournamentName,
      season_year: targetYear,
      available_years: availableYears,
      message: "No edition found for that year.",
    };
  }

  const edition = [...yearTours].sort((a, b) => str(b.date).localeCompare(str(a.date)))[0];
  const requestedRoundId = normalizeRoundId(round);

  let q = sb
    .from("oncourt_games")
    .select("winner_id, loser_id, round_id, result, date")
    .eq("tour_id", num(edition.id));
  if (requestedRoundId) q = q.eq("round_id", requestedRoundId);
  const { data: games } = await q.limit(400);

  if (!games?.length) {
    return {
      found: false,
      tournament: str(edition.name),
      season_year: targetYear,
      round_requested: round ?? null,
      round_id: requestedRoundId,
      message: "No matches found for this edition/filter.",
    };
  }

  const playerIds = [...new Set(games.flatMap((g) => [num(g.winner_id), num(g.loser_id)]).filter((id) => id > 0))];
  const { data: players } = playerIds.length
    ? await sb.from("oncourt_players").select("id, name").in("id", playerIds)
    : { data: [] as Row[] };
  const pMap = new Map<number, string>((players ?? []).map((p) => [num(p.id), str(p.name)]));

  let playerIdFilter: number | null = null;
  let playerNameFilter = "";
  if (playerName && str(playerName).toLowerCase() !== "all") {
    playerNameFilter = str(playerName).toLowerCase();
    const found = await searchPlayer(playerName);
    if (found.length > 0 && num(found[0].id) > 0) playerIdFilter = num(found[0].id);
  }

  let matches = games
    .map((g) => {
      const winner = pMap.get(num(g.winner_id)) ?? `Player ${num(g.winner_id)}`;
      const loser = pMap.get(num(g.loser_id)) ?? `Player ${num(g.loser_id)}`;
      return {
        date: g.date,
        round_id: num(g.round_id),
        round: roundLabel(num(g.round_id)),
        winner_id: num(g.winner_id),
        winner,
        loser_id: num(g.loser_id),
        loser,
        score: str(g.result),
      };
    })
    .filter((m) => !m.winner.includes("/") && !m.loser.includes("/"));

  if (playerIdFilter) {
    matches = matches.filter((m) => m.winner_id === playerIdFilter || m.loser_id === playerIdFilter);
  } else if (playerNameFilter) {
    matches = matches.filter((m) =>
      m.winner.toLowerCase().includes(playerNameFilter) || m.loser.toLowerCase().includes(playerNameFilter)
    );
  }

  matches.sort((a, b) => {
    const byRound = b.round_id - a.round_id;
    if (byRound !== 0) return byRound;
    return str(b.date).localeCompare(str(a.date));
  });

  return {
    found: true,
    tournament: str(edition.name),
    season_year: targetYear,
    round_requested: round ?? null,
    round_id: requestedRoundId,
    player_filter: playerName || null,
    match_count: matches.length,
    matches: matches.slice(0, 120),
    available_years: availableYears,
  };
}

/* ── Court pace (CPI-based) ──────────────────────────────── */

export async function courtPace(tournamentName: string): Promise<Row> {
  const searchTerms = resolveSearchTerms(tournamentName);
  let rows: Row[] = [];
  for (const term of searchTerms) {
    const { data } = await sb
      .from("tournament_surface_speed")
      .select("tournament_name, season_year, cpi, surface, sample_size")
      .ilike("tournament_name", `%${term}%`)
      .order("season_year", { ascending: false })
      .limit(20);
    if (data?.length) rows = [...rows, ...data];
  }
  if (!rows.length) return { found: false, tournament: tournamentName };

  const latest = rows[0];
  const cpi = num(latest.cpi);
  const surface = str(latest.surface);

  let paceRating: string;
  if (surface === "Clay") {
    if (cpi > 0.95) paceRating = "Very fast for Clay";
    else if (cpi > 0.85) paceRating = "Fast for Clay";
    else if (cpi > 0.70) paceRating = "Average pace for Clay";
    else if (cpi > 0.55) paceRating = "Slow for Clay";
    else paceRating = "Very slow for Clay";
  } else if (surface === "Grass") {
    if (cpi > 1.15) paceRating = "Very fast for Grass";
    else if (cpi > 1.05) paceRating = "Fast for Grass";
    else if (cpi > 0.90) paceRating = "Average pace for Grass";
    else paceRating = "Slow for Grass";
  } else {
    if (cpi > 1.10) paceRating = "Very fast";
    else if (cpi > 0.95) paceRating = "Fast";
    else if (cpi > 0.80) paceRating = "Average pace";
    else if (cpi > 0.65) paceRating = "Slow";
    else paceRating = "Very slow";
  }

  const history = rows
    .filter((r) => str(r.tournament_name) === str(latest.tournament_name))
    .slice(0, 5)
    .map((r) => ({ year: r.season_year, cpi: num(r.cpi), surface: str(r.surface) }));

  return {
    found: true,
    tournament: str(latest.tournament_name),
    surface,
    cpi: Math.round(cpi * 100) / 100,
    pace_rating: paceRating,
    sample_size: latest.sample_size,
    recent_years: history,
  };
}

/* ── Tournament fav/dog ROI (from backtest CSVs) ───────────── */

function parseCsv(content: string): Record<string, string>[] {
  const lines = content.trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((h) => h.trim());
  const rows: Record<string, string>[] = [];
  for (let i = 1; i < lines.length; i++) {
    const vals = lines[i].split(",");
    const row: Record<string, string> = {};
    headers.forEach((h, j) => {
      row[h] = vals[j] ?? "";
    });
    rows.push(row);
  }
  return rows;
}

function matchesTournament(term: string, key: string, display: string): boolean {
  const t = term.toLowerCase().trim();
  const k = key.toLowerCase();
  const d = display.toLowerCase();
  // Avoid t.includes(firstWord): "Italian Open" would falsely match "Open 13" (Marseille) via "open"
  return k.includes(t) || d.includes(t) || t.includes(k);
}

function normalizeRoundId(roundInput?: string | number): number | null {
  if (roundInput == null) return null;
  if (typeof roundInput === "number" && Number.isFinite(roundInput)) return roundInput;
  const raw = str(roundInput).toLowerCase().trim();
  if (!raw) return null;
  if (/^\d+$/.test(raw)) return Number(raw);

  const compact = raw.replace(/[^a-z0-9]/g, "");
  if (compact === "f" || compact === "final") return 12;
  if (compact === "sf" || compact === "semifinal" || compact === "semis" || compact === "semi") return 10;
  if (compact === "qf" || compact === "quarterfinal" || compact === "quarters" || compact === "quarter") return 9;
  if (compact === "r16" || compact === "roundof16" || compact === "last16") return 7;
  if (compact === "r3" || compact === "thirdround") return 3;
  if (compact === "r2" || compact === "secondround") return 2;
  if (compact === "r1" || compact === "firstround") return 1;
  if (compact === "q3" || compact === "qualifying3") return 6;
  if (compact === "q2" || compact === "qualifying2") return 5;
  if (compact === "q1" || compact === "qualifying1") return 4;
  return null;
}

function roundLabel(roundId: number): string {
  const labels: Record<number, string> = {
    1: "R1",
    2: "R2",
    3: "R3",
    4: "Q1",
    5: "Q2",
    6: "Q3",
    7: "R16",
    9: "QF",
    10: "SF",
    12: "Final",
  };
  return labels[roundId] ?? `Round ${roundId}`;
}

/** Reads tournament-fav-dog-roi.csv. For deployment, ensure data/backtest/tournament-fav-dog-roi.csv is committed. */
export async function tournamentFavDogStats(tournamentName: string): Promise<Row> {
  const searchTerms = resolveSearchTerms(tournamentName);
  const csvPath = path.join(process.cwd(), "data", "backtest", "tournament-fav-dog-roi.csv");
  try {
    const content = await readFile(csvPath, "utf-8");
    const rows = parseCsv(content);
    const rolling = rows.filter((r) => (r.window_type ?? "") === "rolling_4" || (r.window_type ?? "") === "prior_editions");
    const byYear = rows.filter((r) => (r.window_type ?? "") === "year");
    const candidates = rolling.length ? rolling : byYear;
    for (const term of searchTerms) {
      const match = candidates.find((r) => matchesTournament(term, r.tournament_key ?? "", r.tournament_display ?? ""));
      if (match) {
        return {
          tournament: match.tournament_display ?? match.tournament_key,
          window: match.window_type,
          years: match.years,
          n_matches: num(match.n_matches),
          fav_bets: num(match.fav_bets),
          fav_wins: num(match.fav_wins),
          fav_roi_pct_shrunk: Math.round(num(match.fav_roi_pct_shrunk) * 100) / 100,
          dog_bets: num(match.dog_bets),
          dog_wins: num(match.dog_wins),
          dog_roi_pct_shrunk: Math.round(num(match.dog_roi_pct_shrunk) * 100) / 100,
        };
      }
    }
  } catch (err) {
    if (process.env.NODE_ENV === "development") {
      console.error("[tournamentFavDogStats]", err instanceof Error ? err.message : String(err));
    }
  }
  return {
    found: false,
    tournament: tournamentName,
    message: "No favourite/dog ROI data for this tournament. The backtest CSV may be missing or the tournament name may not match.",
  };
}

/** Reads tournament-seed-entry-stats.csv. For deployment, ensure data/backtest/tournament-seed-entry-stats.csv is committed. */
export async function tournamentSeedStats(tournamentName: string): Promise<Row> {
  const searchTerms = resolveSearchTerms(tournamentName);
  const csvPath = path.join(process.cwd(), "data", "backtest", "tournament-seed-entry-stats.csv");
  try {
    const content = await readFile(csvPath, "utf-8");
    const rows = parseCsv(content);
    const rolling = rows.filter((r) => (r.window_type ?? "") === "rolling_4" || (r.window_type ?? "") === "prior_editions");
    const byYear = rows.filter((r) => (r.window_type ?? "") === "year");
    const candidates = rolling.length ? rolling : byYear;
    let matchKey: string | null = null;
    let matchDisplay = "";
    for (const term of searchTerms) {
      const found = candidates.find((r) => matchesTournament(term, r.tournament_key ?? "", r.tournament_display ?? ""));
      if (found) {
        matchKey = found.tournament_key ?? null;
        matchDisplay = found.tournament_display ?? found.tournament_key ?? "";
        break;
      }
    }
    if (matchKey) {
      const segs = candidates.filter((r) => r.tournament_key === matchKey);
      return {
        tournament: matchDisplay,
        window: segs[0]?.window_type,
        years: segs[0]?.years,
        segments: segs.slice(0, 15).map((r) => ({
          segment: r.segment_type,
          family: r.segment_family,
          n_matches: num(r.n_matches),
          win_rate_pct: Math.round(num(r.win_rate_pct_raw) * 10) / 10,
          max_round: r.max_round,
          r1_win_rate: num(r.r1_matches) > 0 ? Math.round((num(r.r1_wins) / num(r.r1_matches)) * 1000) / 10 : null,
        })),
      };
    }
  } catch (err) {
    if (process.env.NODE_ENV === "development") {
      console.error("[tournamentSeedStats]", err instanceof Error ? err.message : String(err));
    }
  }
  return {
    found: false,
    tournament: tournamentName,
    message: "No seed/entry stats for this tournament. The backtest CSV may be missing or the tournament name may not match.",
  };
}
