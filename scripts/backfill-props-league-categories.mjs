#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createClient } from "@supabase/supabase-js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TEAM_LOGO_MAP_PATH = path.join(ROOT, "data", "goalscorer", "team-logo-map.json");

const MANIFEST_LEAGUE_TO_CATEGORY = {
  epl: "pl",
  "serie-a": "seriea",
  "la-liga": "laliga",
  bundesliga: "bundesliga",
  "ligue-1": "ligue1",
};

const CATEGORY_LABELS = {
  pl: "Premier League",
  seriea: "Serie A",
  laliga: "La Liga",
  bundesliga: "Bundesliga",
  ligue1: "Ligue 1",
};

const args = new Set(process.argv.slice(2));
const APPLY = args.has("--apply");
const INCLUDE_PENDING = args.has("--include-pending");
const LIMIT_ARG = process.argv.find((arg) => arg.startsWith("--limit="));
const LIMIT = LIMIT_ARG ? Number(LIMIT_ARG.split("=")[1]) : null;
const PAGE_SIZE = 1000;

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return;
  const text = fs.readFileSync(filePath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const idx = trimmed.indexOf("=");
    const key = trimmed.slice(0, idx).trim();
    let value = trimmed.slice(idx + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!process.env[key]) process.env[key] = value;
  }
}

function normalizeText(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/gi, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function splitMatchEvent(event) {
  const normalized = String(event ?? "").replace(/\s+/g, " ").trim();
  if (!normalized) return null;
  const parts = normalized.split(/\s+(?:vs|v|at)\s+/i);
  if (parts.length < 2) return null;
  return [parts[0], parts.slice(1).join(" ")];
}

function buildTeamAliases() {
  const manifest = JSON.parse(fs.readFileSync(TEAM_LOGO_MAP_PATH, "utf8"));
  const aliases = [];

  for (const [leagueKey, league] of Object.entries(manifest.leagues ?? {})) {
    const category = MANIFEST_LEAGUE_TO_CATEGORY[leagueKey];
    if (!category) continue;

    for (const [displayName, team] of Object.entries(league.teams ?? {})) {
      const candidates = [displayName, team.team_key, team.fotmob_name, team.fotmob_short_name].filter(Boolean);
      for (const candidate of candidates) {
        const alias = normalizeText(candidate);
        if (alias.length >= 3) aliases.push({ alias, category });
      }
    }
  }

  const seen = new Set();
  return aliases
    .filter((row) => {
      const key = `${row.alias}|${row.category}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => b.alias.length - a.alias.length);
}

const TEAM_ALIASES = buildTeamAliases();

function resolveTeamCategory(teamName) {
  const normalized = normalizeText(teamName);
  if (!normalized) return null;

  for (const row of TEAM_ALIASES) {
    if (normalized === row.alias) return row.category;
    if (row.alias.length >= 5 && (normalized.includes(row.alias) || row.alias.includes(normalized))) {
      return row.category;
    }
  }

  return null;
}

function inferCategory(event) {
  const teams = splitMatchEvent(event);
  if (!teams) return null;
  const homeCategory = resolveTeamCategory(teams[0]);
  const awayCategory = resolveTeamCategory(teams[1]);
  if (homeCategory && homeCategory === awayCategory) return homeCategory;
  return null;
}

async function fetchCandidateRows(supabase) {
  const rows = [];
  let from = 0;

  while (true) {
    let query = supabase
      .from("bets")
      .select("id,market,category,event,player,selection,status,match_date,posted_at,settled_at")
      .eq("market", "props")
      .eq("category", "other")
      .order("match_date", { ascending: false })
      .range(from, from + PAGE_SIZE - 1);

    if (!INCLUDE_PENDING) {
      query = query.in("status", ["won", "lost", "void"]);
    }

    const { data, error } = await query;
    if (error) throw new Error(error.message);
    rows.push(...(data ?? []));
    if (!data || data.length < PAGE_SIZE) break;
    if (LIMIT && rows.length >= LIMIT) break;
    from += PAGE_SIZE;
  }

  return LIMIT ? rows.slice(0, LIMIT) : rows;
}

function summarize(rows) {
  const counts = new Map();
  for (const row of rows) counts.set(row.newCategory, (counts.get(row.newCategory) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

async function applyUpdates(supabase, rows) {
  let updated = 0;
  for (const row of rows) {
    const { error } = await supabase.from("bets").update({ category: row.newCategory }).eq("id", row.id);
    if (error) throw new Error(`Failed updating bet ${row.id}: ${error.message}`);
    updated += 1;
  }
  return updated;
}

async function main() {
  loadEnvFile(path.join(ROOT, ".env.local"));

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.");
  }

  const supabase = createClient(url, key);
  const candidates = await fetchCandidateRows(supabase);
  const changes = candidates
    .map((row) => ({ ...row, newCategory: inferCategory(row.event) }))
    .filter((row) => row.newCategory && row.newCategory !== row.category);

  console.log("================================================================");
  console.log("Props League Category Backfill");
  console.log("================================================================");
  console.log(`Mode: ${APPLY ? "APPLY" : "DRY RUN"}`);
  console.log(`Pending rows included: ${INCLUDE_PENDING ? "yes" : "no"}`);
  console.log(`Candidate props/other rows scanned: ${candidates.length}`);
  console.log(`Rows that can be safely recategorised: ${changes.length}`);
  console.log("");

  for (const [category, count] of summarize(changes)) {
    console.log(`${CATEGORY_LABELS[category] ?? category}: ${count}`);
  }

  console.log("");
  console.log("Examples:");
  for (const row of changes.slice(0, 20)) {
    console.log(
      `#${row.id} ${row.match_date ?? "no-date"} | ${row.event} | ${row.player ?? "-"} | ${row.selection} | ${row.status} | other -> ${row.newCategory}`,
    );
  }

  if (!APPLY) {
    console.log("");
    console.log("No database writes made. Re-run with --apply to update these rows.");
    return;
  }

  const updated = await applyUpdates(supabase, changes);
  console.log("");
  console.log(`Updated rows: ${updated}`);
}

main().catch((error) => {
  console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
