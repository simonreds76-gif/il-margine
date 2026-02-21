/**
 * Check last 7 days bets - run with: node scripts/check-last7.js
 * Requires .env.local with NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
 */
const { createClient } = require("@supabase/supabase-js");
const fs = require("fs");
const path = require("path");

// Load .env.local
const envPath = path.join(__dirname, "..", ".env.local");
if (fs.existsSync(envPath)) {
  const env = fs.readFileSync(envPath, "utf8");
  env.split("\n").forEach((line) => {
    const m = line.match(/^([^#=]+)=(.*)$/);
    if (m) process.env[m[1].trim()] = m[2].trim().replace(/^["']|["']$/g, "");
  });
}

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!url || !key) {
  console.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.local");
  process.exit(1);
}

const supabase = createClient(url, key);

async function main() {
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  console.log("Last 7 days window:", sevenDaysAgo.toISOString(), "to now\n");

  const { data, error } = await supabase
    .from("bets")
    .select("id, event, selection, odds, stake, profit_loss, settled_at, market, status")
    .in("status", ["won", "lost"])
    .not("settled_at", "is", null)
    .gte("settled_at", sevenDaysAgo.toISOString())
    .order("settled_at", { ascending: false });

  if (error) {
    console.error("Error:", error.message);
    process.exit(1);
  }

  const sum = (data || []).reduce((s, b) => s + (Number(b.profit_loss) || 0), 0);

  console.log("Count:", data.length);
  console.log("Total P/L:", sum.toFixed(2) + "u\n");
  console.log("Bets:");
  console.log("-".repeat(80));
  (data || []).forEach((b) => {
    const pl = Number(b.profit_loss) || 0;
    const sign = pl >= 0 ? "+" : "";
    console.log(`${b.settled_at?.slice(0, 10)} | ${b.event} | ${b.selection} | ${b.odds} @ ${b.stake}u | ${sign}${pl.toFixed(2)}u`);
  });
}

main();
