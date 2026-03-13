/**
 * Test script: fetch Jeff Sackmann tennis_atp data from GitHub and compute
 * serve% / return% by player and surface.
 *
 * Run: node scripts/test-sackmann-stats.js
 * Last 12 months only: USE_12MO=1 node scripts/test-sackmann-stats.js
 *
 * Data source: https://github.com/JeffSackmann/tennis_atp (CC BY-NC-SA 4.0)
 * For local testing only - do not use in production without proper licensing.
 */

const BASE_URL = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master";

async function fetchCsv(year) {
  const url = `${BASE_URL}/atp_matches_${year}.csv`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
  return res.text();
}

function parseCsv(text) {
  const lines = text.trim().split("\n");
  if (lines.length < 2) return [];
  const header = lines[0].split(",");
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const values = parseRow(lines[i]);
    if (values.length !== header.length) continue;
    const row = {};
    header.forEach((h, j) => (row[h] = values[j]));
    rows.push(row);
  }
  return rows;
}

function parseRow(line) {
  const result = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      inQuotes = !inQuotes;
    } else if ((c === "," && !inQuotes) || c === "\n") {
      result.push(current.trim());
      current = "";
      if (c === "\n") break;
    } else {
      current += c;
    }
  }
  result.push(current.trim());
  return result;
}

function computeMatchStats(row) {
  const wSvpt = parseInt(row.w_svpt, 10);
  const lSvpt = parseInt(row.l_svpt, 10);
  const w1stWon = parseInt(row.w_1stWon, 10) || 0;
  const w2ndWon = parseInt(row.w_2ndWon, 10) || 0;
  const l1stWon = parseInt(row.l_1stWon, 10) || 0;
  const l2ndWon = parseInt(row.l_2ndWon, 10) || 0;

  if (!wSvpt || !lSvpt) return null; // need both for valid stats

  const winnerServePct = ((w1stWon + w2ndWon) / wSvpt) * 100;
  const winnerReturnPct = ((lSvpt - l1stWon - l2ndWon) / lSvpt) * 100;
  const loserServePct = ((l1stWon + l2ndWon) / lSvpt) * 100;
  const loserReturnPct = ((wSvpt - w1stWon - w2ndWon) / wSvpt) * 100;

  return {
    date: row.tourney_date,
    surface: (row.surface || "").toLowerCase(),
    winner: {
      name: row.winner_name,
      hand: row.winner_hand,
      servePct: winnerServePct,
      returnPct: winnerReturnPct,
      total: winnerServePct + winnerReturnPct,
    },
    loser: {
      name: row.loser_name,
      hand: row.loser_hand,
      servePct: loserServePct,
      returnPct: loserReturnPct,
      total: loserServePct + loserReturnPct,
    },
    loserIsLeftie: (row.loser_hand || "").toUpperCase() === "L",
    winnerIsLeftie: (row.winner_hand || "").toUpperCase() === "L",
  };
}

function dateToTimestamp(str) {
  if (!str || str.length !== 8) return 0;
  const y = parseInt(str.slice(0, 4), 10);
  const m = parseInt(str.slice(4, 6), 10);
  const d = parseInt(str.slice(6, 8), 10);
  return new Date(y, m - 1, d).getTime();
}

function aggregateByPlayer(matches, cutoffDate) {
  const byPlayer = new Map(); // playerName -> { surface -> { servePct[], returnPct[], vsLeftie: {...} } }

  for (const m of matches) {
    if (!m) continue;
    if (cutoffDate > 0 && dateToTimestamp(m.date) < cutoffDate) continue;

    const surface = m.surface || "hard";

    function add(player, servePct, returnPct, oppLeftie) {
      if (!byPlayer.has(player.name)) {
        byPlayer.set(player.name, {
          surfaces: new Map(),
          vsLeftie: { serve: [], return: [] },
        });
      }
      const p = byPlayer.get(player.name);
      if (!p.surfaces.has(surface)) {
        p.surfaces.set(surface, { serve: [], return: [] });
      }
      const s = p.surfaces.get(surface);
      s.serve.push(servePct);
      s.return.push(returnPct);
      if (oppLeftie) {
        p.vsLeftie.serve.push(servePct);
        p.vsLeftie.return.push(returnPct);
      }
    }

    add(m.winner, m.winner.servePct, m.winner.returnPct, m.loserIsLeftie);
    add(m.loser, m.loser.servePct, m.loser.returnPct, m.winnerIsLeftie);
  }

  return byPlayer;
}

function avg(arr) {
  if (!arr || arr.length === 0) return null;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function formatPct(n) {
  return n == null ? "–" : n.toFixed(1) + "%";
}

async function main() {
  console.log("Fetching atp_matches_2023.csv and atp_matches_2024.csv...\n");

  const [csv2023, csv2024] = await Promise.all([
    fetchCsv(2023),
    fetchCsv(2024),
  ]);

  const rows2023 = parseCsv(csv2023);
  const rows2024 = parseCsv(csv2024);

  const allRows = [...rows2023, ...rows2024];
  const matches = allRows.map(computeMatchStats).filter(Boolean);

  const twelveMonthsAgo = Date.now() - 365 * 24 * 60 * 60 * 1000;
  // Use cutoff 0 = include all data (for testing); or twelveMonthsAgo for last 12mo
  const useCutoff = process.env.USE_12MO ? twelveMonthsAgo : 0;

  const byPlayer = aggregateByPlayer(matches, useCutoff);

  console.log(`Parsed ${matches.length} matches with serve/return stats (last 12 months window).\n`);
  console.log("Sample: top 10 players by match count on Hard (serve% / return% / total)\n");

  const hardStats = [];
  for (const [name, data] of byPlayer.entries()) {
    const s = data.surfaces.get("hard");
    if (!s || s.serve.length < 5) continue;
    const serve = avg(s.serve);
    const ret = avg(s.return);
    hardStats.push({
      name,
      matches: s.serve.length,
      serve,
      return: ret,
      total: serve + ret,
      vsLeftieMatches: data.vsLeftie.serve.length,
      vsLeftieTotal: data.vsLeftie.serve.length
        ? avg(data.vsLeftie.serve) + avg(data.vsLeftie.return)
        : null,
    });
  }

  hardStats.sort((a, b) => b.matches - a.matches);
  const top = hardStats.slice(0, 12);

  console.log("Player                  | Matches | Serve%  | Return% | Total   | vs Leftie (n) | vs Leftie total");
  console.log("-".repeat(95));
  for (const p of top) {
    const vsL = p.vsLeftieMatches
      ? `${p.vsLeftieMatches} | ${formatPct(p.vsLeftieTotal)}`
      : "–";
    console.log(
      `${p.name.padEnd(22)} | ${String(p.matches).padStart(6)} | ${formatPct(p.serve).padStart(6)} | ${formatPct(p.return).padStart(6)} | ${formatPct(p.total).padStart(6)} | ${String(vsL).padStart(14)}`
    );
  }

  // Sample matchup: Sinner vs Zverev
  console.log("\n--- Sample matchup: Sinner vs Zverev (Hard) ---");
  const sinner = hardStats.find((p) => p.name.includes("Sinner"));
  const zverev = hardStats.find((p) => p.name.includes("Zverev"));
  if (sinner && zverev) {
    const diff = sinner.total - zverev.total;
    console.log(`Sinner:  ${formatPct(sinner.serve)} serve + ${formatPct(sinner.return)} return = ${formatPct(sinner.total)} total`);
    console.log(`Zverev:  ${formatPct(zverev.serve)} serve + ${formatPct(zverev.return)} return = ${formatPct(zverev.total)} total`);
    console.log(`Total diff: ${diff > 0 ? "+" : ""}${diff.toFixed(1)} → Sinner favored (higher total)`);
  }

  console.log("\n--- Test complete. Data: Jeff Sackmann tennis_atp (CC BY-NC-SA 4.0) ---");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
