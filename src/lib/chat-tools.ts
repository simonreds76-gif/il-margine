import { createClient } from "@supabase/supabase-js";

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

const TOURNAMENT_ALIASES: Record<string, string[]> = {
  "roland garros":     ["French Open"],
  "french open":       ["French Open"],
  "garros":            ["French Open"],
  "paris slam":        ["French Open"],
  "wimbledon":         ["Wimbledon"],
  "us open":           ["US Open", "U.S. Open"],
  "u.s. open":         ["US Open", "U.S. Open"],
  "flushing":          ["US Open", "U.S. Open"],
  "australian open":   ["Australian Open"],
  "melbourne":         ["Australian Open"],
  "indian wells":      ["Indian Wells", "BNP Paribas"],
  "bnp paribas":       ["Indian Wells", "BNP Paribas"],
  "miami":             ["Miami"],
  "monte carlo":       ["Monte Carlo", "Monte-Carlo"],
  "monte-carlo":       ["Monte Carlo", "Monte-Carlo"],
  "montecarlo":        ["Monte Carlo", "Monte-Carlo"],
  "rome":              ["Rome", "Roma", "Italian Open", "Internazionali"],
  "roma":              ["Rome", "Roma", "Italian Open", "Internazionali"],
  "italian open":      ["Rome", "Roma", "Italian Open", "Internazionali"],
  "internazionali":    ["Rome", "Roma", "Italian Open", "Internazionali"],
  "foro italico":      ["Rome", "Roma", "Italian Open", "Internazionali"],
  "madrid":            ["Madrid", "Mutua Madrid"],
  "mutua":             ["Madrid", "Mutua Madrid"],
  "shanghai":          ["Shanghai"],
  "canada":            ["Canada", "Canadian Open", "Montreal", "Toronto", "National Bank"],
  "canadian":          ["Canada", "Canadian Open", "Montreal", "Toronto", "National Bank"],
  "montreal":          ["Canada", "Canadian Open", "Montreal", "Toronto", "National Bank"],
  "toronto":           ["Canada", "Canadian Open", "Montreal", "Toronto", "National Bank"],
  "cincinnati":        ["Cincinnati", "Western & Southern"],
  "western & southern":["Cincinnati", "Western & Southern"],
  "barcelona":         ["Barcelona"],
  "hamburg":           ["Hamburg"],
  "queen's":           ["Queen's", "Queens"],
  "queens":            ["Queen's", "Queens"],
  "halle":             ["Halle"],
  "beijing":           ["Beijing", "China Open"],
  "china open":        ["Beijing", "China Open"],
  "basel":             ["Basel"],
  "vienna":            ["Vienna", "Erste Bank"],
  "erste bank":        ["Vienna", "Erste Bank"],
  "paris masters":     ["Paris", "Bercy", "Rolex Paris"],
  "bercy":             ["Paris", "Bercy", "Rolex Paris"],
  "atp finals":        ["ATP Finals", "Tour Finals", "Masters Cup", "Nitto"],
  "tour finals":       ["ATP Finals", "Tour Finals", "Masters Cup", "Nitto"],
  "nitto":             ["ATP Finals", "Tour Finals", "Masters Cup", "Nitto"],
  "dubai":             ["Dubai"],
  "doha":              ["Doha", "Qatar"],
  "qatar":             ["Doha", "Qatar"],
  "acapulco":          ["Acapulco", "Mexican Open"],
  "mexican open":      ["Acapulco", "Mexican Open"],
  "rotterdam":         ["Rotterdam", "ABN AMRO"],
  "abn amro":          ["Rotterdam", "ABN AMRO"],
  "monte":             ["Monte Carlo", "Monte-Carlo"],
  "washington":        ["Washington", "Citi Open"],
  "citi open":         ["Washington", "Citi Open"],
  "tokyo":             ["Tokyo", "Japan Open"],
  "japan open":        ["Tokyo", "Japan Open"],
  "brisbane":          ["Brisbane"],
  "auckland":          ["Auckland"],
  "adelaide":          ["Adelaide"],
  "marseille":         ["Marseille", "Open 13"],
  "lyon":              ["Lyon"],
  "stuttgart":         ["Stuttgart"],
  "s-hertogenbosch":   ["s-Hertogenbosch", "Libema"],
  "eastbourne":        ["Eastbourne"],
  "los cabos":         ["Los Cabos"],
  "umag":              ["Umag"],
  "gstaad":            ["Gstaad"],
  "kitzbuhel":         ["Kitzbuhel", "Kitzbuehel"],
  "winston-salem":     ["Winston-Salem"],
  "zhuhai":            ["Zhuhai"],
  "sofia":             ["Sofia"],
  "stockholm":         ["Stockholm"],
  "antwerp":           ["Antwerp", "European Open"],
  "metz":              ["Metz", "Moselle"],
};

function resolveSearchTerms(input: string): string[] {
  const lower = input.toLowerCase().trim();
  for (const [alias, dbNames] of Object.entries(TOURNAMENT_ALIASES)) {
    if (lower.includes(alias)) return dbNames;
  }
  return [input];
}

const JUNK_TOUR_KEYWORDS = ["junior", "qualif", "boys", "girls", "legends", "doubles", "wheelchair"];
function isMainTour(name: string): boolean {
  const lower = name.toLowerCase();
  return !JUNK_TOUR_KEYWORDS.some((kw) => lower.includes(kw));
}

/* ── Player search (fuzzy by surname) ─────────────────────── */

/** Common spelling variants for player search (e.g. Maroszan -> Marozsan for Hungarian names). */
function searchVariants(q: string): string[] {
  const variants = [q];
  const lower = q.toLowerCase();
  if (lower.includes("maroszan")) variants.push(q.replace(/maroszan/gi, "Marozsan"));
  if (lower.includes("marozsan") && !lower.includes("maroszan")) variants.push(q.replace(/marozsan/gi, "Maroszan"));
  return [...new Set(variants)];
}

export async function searchPlayer(name: string): Promise<Row[]> {
  const q = name.trim();
  if (!q) return [];
  for (const term of searchVariants(q)) {
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

  let q = sb
    .from("player_h2h")
    .select("*")
    .eq("player_a_id", lowId)
    .eq("player_b_id", highId);
  if (surface) q = q.eq("surface", surface);
  const { data: h2h } = await q.limit(10);

  const { data: matches } = await sb
    .from("oncourt_games")
    .select("winner_id, loser_id, tour_id, round_id, result, date")
    .or(`and(winner_id.eq.${playerAId},loser_id.eq.${playerBId}),and(winner_id.eq.${playerBId},loser_id.eq.${playerAId})`)
    .order("date", { ascending: false })
    .limit(20);

  const enriched = [];
  for (const m of matches ?? []) {
    const { data: tour } = await sb
      .from("oncourt_tours")
      .select("name, court_id")
      .eq("id", m.tour_id)
      .maybeSingle();
    enriched.push({ ...m, tournament: tour?.name ?? "" });
  }

  return {
    summary: h2h ?? [],
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

  const enriched = [];
  for (const m of allMatches.slice(0, 30)) {
    const opponentId = num(m.winner_id) === playerId ? num(m.loser_id) : num(m.winner_id);
    const { data: opp } = await sb.from("oncourt_players").select("name").eq("id", opponentId).maybeSingle();
    const won = num(m.winner_id) === playerId;
    enriched.push({
      date: m.date,
      opponent: opp?.name ?? `Player ${opponentId}`,
      won,
      score: m.result,
      round_id: m.round_id,
    });
  }

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

export async function playerRecordVsLefties(playerId: number): Promise<Row> {
  const lefties = new Set(await fetchAllLeftieIds());
  if (!lefties.size) return { overall: { wins: 0, losses: 0 }, note: "No leftie reference data" };

  const winsQ = sb
    .from("oncourt_games")
    .select("winner_id, loser_id, tour_id, result, date")
    .eq("winner_id", playerId)
    .in("loser_id", Array.from(lefties))
    .order("date", { ascending: false })
    .limit(500);

  const lossesQ = sb
    .from("oncourt_games")
    .select("winner_id, loser_id, tour_id, result, date")
    .eq("loser_id", playerId)
    .in("winner_id", Array.from(lefties))
    .order("date", { ascending: false })
    .limit(500);

  const [{ data: wins }, { data: losses }] = await Promise.all([winsQ, lossesQ]);
  const allWins = wins ?? [];
  const allLosses = losses ?? [];

  const { data: tours } = await sb.from("oncourt_tours").select("id, court_id").limit(10000);
  const { data: courts } = await sb.from("oncourt_courts").select("id, name").limit(50);
  const courtToSurface: Record<number, string> = {};
  for (const c of courts ?? []) {
    const n = str(c.name).toUpperCase();
    if (n.includes("CLAY")) courtToSurface[num(c.id)] = "Clay";
    else if (n.includes("GRASS")) courtToSurface[num(c.id)] = "Grass";
    else if (n.includes("I.HARD") || n === "I.HARD" || n.includes("INDOOR")) courtToSurface[num(c.id)] = "I.hard";
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
  return rows;
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
