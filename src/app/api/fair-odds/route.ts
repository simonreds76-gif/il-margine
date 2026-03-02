import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
/** Service role used only for bookmaker_odds_snapshot so Pinnacle shows even if RLS blocks anon. */
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

export interface FairOddsRow {
  id: number;
  tournament: string;
  surface: string;
  player1_id: number;
  player2_id: number;
  player1_name: string;
  player2_name: string;
  p1_win_prob: number;
  p2_win_prob: number;
  odds1: number;
  odds2: number;
  p1_serve?: number;
  p1_return?: number;
  p1_total?: number;
  p2_serve?: number;
  p2_return?: number;
  p2_total?: number;
  expected_total_games?: number;
  pinnacle_odds1?: number;
  pinnacle_odds2?: number;
  pinnacle_margin?: number;
  value_p1?: number;
  value_p2?: number;
}

const API_TIMEOUT_MS = 15000;

async function run(): Promise<Response> {
  if (!url || !anonKey) {
    return NextResponse.json(
      { error: "Missing Supabase env (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY)" },
      { status: 500 }
    );
  }
  const supabase = createClient(url, anonKey);

  const FAIR_ODDS_LIMIT = 2000;

  const { data: oddsRows, error: oddsErr } = await supabase
    .from("daily_fair_odds")
    .select("id, tour_id, player1_id, player2_id, surface, p1_win_prob, p2_win_prob, odds1, odds2, expected_total_games, ou_line_1, ou_over_1, ou_under_1, ou_line_2, ou_over_2, ou_under_2, ou_line_3, ou_over_3, ou_under_3")
    .order("tour_id")
    .order("draw")
    .order("round_id")
    .limit(FAIR_ODDS_LIMIT);

  if (oddsErr) {
    return NextResponse.json({ error: oddsErr.message }, { status: 500 });
  }
  if (!oddsRows?.length) {
    return NextResponse.json({ matches: [] });
  }

  const playerIds = new Set<number>();
  const tourIds = new Set<number>();
  const statsKeys = new Set<string>();
  for (const r of oddsRows) {
    if (r.player1_id != null) playerIds.add(r.player1_id);
    if (r.player2_id != null) playerIds.add(r.player2_id);
    if (r.tour_id != null) tourIds.add(r.tour_id);
    if (r.player1_id != null && r.surface) statsKeys.add(`${r.player1_id}:${r.surface}`);
    if (r.player2_id != null && r.surface) statsKeys.add(`${r.player2_id}:${r.surface}`);
  }

  const [playersRes, toursRes, statsRes] = await Promise.all([
    playerIds.size
      ? supabase.from("oncourt_players").select("id, name").in("id", Array.from(playerIds))
      : { data: [] as { id: number; name: string }[] },
    tourIds.size
      ? supabase.from("oncourt_tours").select("id, name").in("id", Array.from(tourIds))
      : { data: [] as { id: number; name: string }[] },
    playerIds.size
      ? supabase
          .from("player_surface_stats")
          .select("player_id, surface, hold_pct, return_pct")
          .in("player_id", Array.from(playerIds))
      : { data: [] as { player_id: number; surface: string; hold_pct: number | null; return_pct: number | null }[] },
  ]);

  const players = new Map<number, string>();
  for (const p of playersRes.data ?? []) {
    players.set(p.id, p.name ?? `Player ${p.id}`);
  }
  const tours = new Map<number, string>();
  for (const t of toursRes.data ?? []) {
    tours.set(t.id, t.name ?? "");
  }
  const stats = new Map<string, { hold_pct: number; return_pct: number }>();
  for (const s of statsRes.data ?? []) {
    const key = `${s.player_id}:${s.surface}`;
    if (!statsKeys.has(key)) continue;
    const hold = s.hold_pct != null ? Number(s.hold_pct) : 0;
    const ret = s.return_pct != null ? Number(s.return_pct) : 0;
    stats.set(key, { hold_pct: hold, return_pct: ret });
  }

  // Use UTC date so it matches script: datetime.now(timezone.utc).date().isoformat()
  const now = new Date();
  const today = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-${String(now.getUTCDate()).padStart(2, "0")}`;
  let pinnacleRows: {
    player1_name: string;
    player2_name: string;
    odds1: number;
    odds2: number;
    ou_line?: number;
    ou_over?: number;
    ou_under?: number;
  }[] = [];
  const snapshotClient = url && serviceRoleKey ? createClient(url, serviceRoleKey) : supabase;
  const { data: snapshotData } = await snapshotClient
    .from("bookmaker_odds_snapshot")
    .select("player1_name, player2_name, odds1, odds2, ou_line, ou_over, ou_under")
    .eq("bookmaker", "Pinnacle")
    .eq("capture_date", today)
    .eq("league", "ATP")
    .limit(500);
  if (snapshotData?.length) {
    pinnacleRows = snapshotData.map((row) => ({
      player1_name: (row.player1_name ?? "").trim(),
      player2_name: (row.player2_name ?? "").trim(),
      odds1: Number(row.odds1 ?? 0),
      odds2: Number(row.odds2 ?? 0),
      ou_line: row.ou_line != null ? Number(row.ou_line) : undefined,
      ou_over: row.ou_over != null ? Number(row.ou_over) : undefined,
      ou_under: row.ou_under != null ? Number(row.ou_under) : undefined,
    }));
  }

  /** Normalise for lookup: lowercase, strip accents, hyphens, apostrophes. */
  function norm(s: string): string {
    return (s ?? "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/-/g, "")
      .replace(/'/g, "")
      .trim();
  }
  /** Surname from "Surname, F." | "Surname F." | "First Last". Handles both Pinnacle and OnCourt formats. */
  function normaliseSurname(name: string): string {
    const raw = (name ?? "").trim();
    const beforeComma = raw.split(",")[0].trim();
    const parts = beforeComma.split(/\s+/).filter(Boolean);
    if (parts.length === 0) return "";
    if (parts.length === 1) return norm(parts[0]);
    const last = parts[parts.length - 1] ?? "";
    const isInitial = /^[A-Za-z]\.?$/.test(last);
    const surname = isInitial ? (parts[parts.length - 2] ?? last) : last;
    return norm(surname);
  }
  /** First word (for "Surname First" / OnCourt-style). Use as fallback when primary key doesn't match. */
  function normaliseFirstWord(name: string): string {
    const raw = (name ?? "").trim().split(",")[0].trim();
    const parts = raw.split(/\s+/).filter(Boolean);
    return parts.length ? norm(parts[0]) : "";
  }

  /** Simple Levenshtein distance for short strings (surnames). */
  function levenshtein(a: string, b: string): number {
    if (a === b) return 0;
    if (!a.length) return b.length;
    if (!b.length) return a.length;
    const matrix: number[][] = [];
    for (let i = 0; i <= a.length; i++) matrix[i] = [i];
    for (let j = 0; j <= b.length; j++) matrix[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
      for (let j = 1; j <= b.length; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        matrix[i][j] = Math.min(
          matrix[i - 1][j] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j - 1] + cost
        );
      }
    }
    return matrix[a.length][b.length];
  }

  type PinnacleRow = (typeof pinnacleRows)[0];
  function matchPinnacle(
    fairOddsRows: { id: number; player1_name: string; player2_name: string }[],
    pinRows: PinnacleRow[]
  ): Map<number, { pinnacle_odds1: number; pinnacle_odds2: number; pinnacle_margin: number; pinnacle_ou_line?: number; pinnacle_ou_over?: number; pinnacle_ou_under?: number }> {
    const matched = new Map<
      number,
      { pinnacle_odds1: number; pinnacle_odds2: number; pinnacle_margin: number; pinnacle_ou_line?: number; pinnacle_ou_over?: number; pinnacle_ou_under?: number }
    >();
    const pinLookup = new Map<string, { row: PinnacleRow; reversed: boolean }>();
    for (const pin of pinRows) {
      if ((pin.player1_name ?? "").includes("/") || (pin.player2_name ?? "").includes("/")) continue;
      if ((pin.player1_name ?? "").includes("&") || (pin.player2_name ?? "").includes("&")) continue;
      const s1 = normaliseSurname(pin.player1_name ?? "");
      const s2 = normaliseSurname(pin.player2_name ?? "");
      if (!s1 || !s2) continue;
      const key1 = `${s1}|${s2}`;
      const key2 = `${s2}|${s1}`;
      pinLookup.set(key1, { row: pin, reversed: false });
      pinLookup.set(key2, { row: pin, reversed: true });
    }
    console.log(
      "[fair-odds] Fair-odds names (singles):",
      fairOddsRows.map((r) => `${r.player1_name} | ${r.player2_name}`)
    );
    console.log(
      "[fair-odds] Pinnacle names:",
      pinRows.map((r) => `${r.player1_name} | ${r.player2_name}`)
    );
    for (const fo of fairOddsRows) {
      const p1 = fo.player1_name ?? "";
      const p2 = fo.player2_name ?? "";
      const s1 = normaliseSurname(p1);
      const s2 = normaliseSurname(p2);
      if (!s1 || !s2) continue;
      let key = `${s1}|${s2}`;
      let ent = pinLookup.get(key);
      if (!ent) {
        const f1 = normaliseFirstWord(p1);
        const f2 = normaliseFirstWord(p2);
        if (f1 && f2) {
          key = `${f1}|${f2}`;
          ent = pinLookup.get(key);
          if (!ent) ent = pinLookup.get(`${f2}|${f1}`);
        }
      }
      // Fuzzy fallback: Levenshtein on surnames (catches transliteration variants)
      if (!ent) {
        let bestDist = 3;
        let bestKey = "";
        for (const [pKey, pVal] of pinLookup) {
          const [ps1, ps2] = pKey.split("|");
          const d1 = levenshtein(s1, ps1);
          const d2 = levenshtein(s2, ps2);
          const total = d1 + d2;
          if (total < bestDist && d1 <= 2 && d2 <= 2) {
            bestDist = total;
            bestKey = pKey;
            ent = pVal;
          }
        }
        if (ent) {
          console.log(`[fair-odds] Fuzzy match: ${s1}|${s2} → ${bestKey} (dist=${bestDist})`);
        }
      }
      if (!ent) continue;
      const pin = ent.row;
      const margin =
        pin.odds1 > 0 && pin.odds2 > 0 ? 1 / pin.odds1 + 1 / pin.odds2 - 1 : 0;
      if (ent.reversed) {
        matched.set(fo.id, {
          pinnacle_odds1: pin.odds2,
          pinnacle_odds2: pin.odds1,
          pinnacle_margin: margin,
          pinnacle_ou_line: pin.ou_line,
          pinnacle_ou_over: pin.ou_under,
          pinnacle_ou_under: pin.ou_over,
        });
      } else {
        matched.set(fo.id, {
          pinnacle_odds1: pin.odds1,
          pinnacle_odds2: pin.odds2,
          pinnacle_margin: margin,
          pinnacle_ou_line: pin.ou_line,
          pinnacle_ou_over: pin.ou_over,
          pinnacle_ou_under: pin.ou_under,
        });
      }
    }

    // Log unmatched Pinnacle rows for debugging
    const matchedPinKeys = new Set<string>();
    for (const [, val] of matched) {
      matchedPinKeys.add(`${val.pinnacle_odds1}|${val.pinnacle_odds2}`);
      matchedPinKeys.add(`${val.pinnacle_odds2}|${val.pinnacle_odds1}`);
    }
    const unmatchedPin = pinRows.filter((pin) => {
      if ((pin.player1_name ?? "").includes("/") || (pin.player2_name ?? "").includes("/")) return false;
      if ((pin.player1_name ?? "").includes("&") || (pin.player2_name ?? "").includes("&")) return false;
      const k = `${pin.odds1}|${pin.odds2}`;
      const kRev = `${pin.odds2}|${pin.odds1}`;
      return !matchedPinKeys.has(k) && !matchedPinKeys.has(kRev);
    });
    if (unmatchedPin.length > 0) {
      console.log(
        `[fair-odds] Unmatched Pinnacle rows:`,
        unmatchedPin.map((p) => `${p.player1_name} vs ${p.player2_name} → surname key: ${normaliseSurname(p.player1_name)}|${normaliseSurname(p.player2_name)}`)
      );
      console.log(
        `[fair-odds] Fair-odds surname keys:`,
        fairOddsRows.map((r) => `${normaliseSurname(r.player1_name)}|${normaliseSurname(r.player2_name)}`)
      );
    }

    console.log(
      `[fair-odds] Pinnacle matching: ${matched.size}/${fairOddsRows.length} matched, ${pinRows.length} Pinnacle rows (WTA/doubles/name mismatch may leave some unmatched).`
    );
    return matched;
  }

  const isDoubles = (name: string) => (name ?? "").includes("/") || (name ?? "").includes("&");
  const fairOddsRowsForMatch = oddsRows
    .map((r) => ({
      id: r.id,
      player1_name: (r.player1_id != null ? players.get(r.player1_id) : null) ?? "",
      player2_name: (r.player2_id != null ? players.get(r.player2_id) : null) ?? "",
    }))
    .filter((r) => !isDoubles(r.player1_name) && !isDoubles(r.player2_name));
  const pinnacleMap = matchPinnacle(fairOddsRowsForMatch, pinnacleRows);

  const matches: FairOddsRow[] = oddsRows.map((r) => {
    const p1Stats = r.player1_id != null && r.surface ? stats.get(`${r.player1_id}:${r.surface}`) : null;
    const p2Stats = r.player2_id != null && r.surface ? stats.get(`${r.player2_id}:${r.surface}`) : null;
    const p1Name = (r.player1_id != null ? players.get(r.player1_id) : null) ?? "";
    const p2Name = (r.player2_id != null ? players.get(r.player2_id) : null) ?? "";
    const pinnacle = pinnacleRows.length ? pinnacleMap.get(r.id) ?? null : null;
    const ourOdds1 = r.odds1 != null ? Number(r.odds1) : 0;
    const ourOdds2 = r.odds2 != null ? Number(r.odds2) : 0;
    const valueP1 =
      pinnacle && ourOdds1 > 1 && pinnacle.pinnacle_odds1 > 1
        ? Math.round((pinnacle.pinnacle_odds1 / ourOdds1 - 1) * 10000) / 100
        : undefined;
    const valueP2 =
      pinnacle && ourOdds2 > 1 && pinnacle.pinnacle_odds2 > 1
        ? Math.round((pinnacle.pinnacle_odds2 / ourOdds2 - 1) * 10000) / 100
        : undefined;
    return {
      id: r.id,
      tournament: (r.tour_id != null ? tours.get(r.tour_id) : null) ?? "",
      surface: r.surface ?? "",
      player1_id: r.player1_id ?? 0,
      player2_id: r.player2_id ?? 0,
      player1_name: p1Name,
      player2_name: p2Name,
      p1_win_prob: r.p1_win_prob != null ? Number(r.p1_win_prob) : 0,
      p2_win_prob: r.p2_win_prob != null ? Number(r.p2_win_prob) : 0,
      odds1: ourOdds1,
      odds2: ourOdds2,
      p1_serve: p1Stats ? Math.round(p1Stats.hold_pct * 1000) / 10 : undefined,
      p1_return: p1Stats ? Math.round(p1Stats.return_pct * 1000) / 10 : undefined,
      p1_total: p1Stats ? Math.round((p1Stats.hold_pct + p1Stats.return_pct) * 1000) / 10 : undefined,
      p2_serve: p2Stats ? Math.round(p2Stats.hold_pct * 1000) / 10 : undefined,
      p2_return: p2Stats ? Math.round(p2Stats.return_pct * 1000) / 10 : undefined,
      p2_total: p2Stats ? Math.round((p2Stats.hold_pct + p2Stats.return_pct) * 1000) / 10 : undefined,
      expected_total_games: r.expected_total_games != null ? Number(r.expected_total_games) : undefined,
      ou_line_1: r.ou_line_1 != null ? Number(r.ou_line_1) : undefined,
      ou_over_1: r.ou_over_1 != null ? Number(r.ou_over_1) : undefined,
      ou_under_1: r.ou_under_1 != null ? Number(r.ou_under_1) : undefined,
      ou_line_2: r.ou_line_2 != null ? Number(r.ou_line_2) : undefined,
      ou_over_2: r.ou_over_2 != null ? Number(r.ou_over_2) : undefined,
      ou_under_2: r.ou_under_2 != null ? Number(r.ou_under_2) : undefined,
      ou_line_3: r.ou_line_3 != null ? Number(r.ou_line_3) : undefined,
      ou_over_3: r.ou_over_3 != null ? Number(r.ou_over_3) : undefined,
      ou_under_3: r.ou_under_3 != null ? Number(r.ou_under_3) : undefined,
      pinnacle_odds1: pinnacle?.pinnacle_odds1,
      pinnacle_odds2: pinnacle?.pinnacle_odds2,
      pinnacle_margin: pinnacle?.pinnacle_margin,
      pinnacle_ou_line: pinnacle?.pinnacle_ou_line,
      pinnacle_ou_over: pinnacle?.pinnacle_ou_over,
      pinnacle_ou_under: pinnacle?.pinnacle_ou_under,
      value_p1: valueP1,
      value_p2: valueP2,
    };
  });

  const pinnacleHint =
    pinnacleRows.length === 0
      ? "No Pinnacle rows for today (UTC). Run: npm run daily-odds. Ensure .env.local has SUPABASE_SERVICE_ROLE_KEY so the API can read bookmaker_odds_snapshot."
      : pinnacleMap.size === 0
        ? "Pinnacle snapshot loaded but no matches linked (name mismatch?). Check server log for match counts."
        : undefined;

  return NextResponse.json({
    matches,
    pinnacle_count: pinnacleRows.length,
    pinnacle_matched_count: pinnacleMap.size,
    ...(pinnacleHint ? { pinnacle_hint: pinnacleHint } : {}),
  });
}

export async function GET() {
  const timeout = new Promise<Response>((resolve) =>
    setTimeout(
      () => resolve(NextResponse.json({ error: "Fair-odds API timed out (15s). Check Supabase or network." }, { status: 503 })),
      API_TIMEOUT_MS
    )
  );
  try {
    return await Promise.race([run(), timeout]);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Fair-odds API error" },
      { status: 500 }
    );
  }
}
