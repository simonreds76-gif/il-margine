import fs from "node:fs/promises";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";
import { DailyPitchBoard } from "@/components/fair-odds-lab/DailyPitchBoard";
import { emptyBoard, isDailyBoard } from "@/components/fair-odds-lab/daily-board-data";
import { LabHitsSection } from "@/components/fair-odds-lab/LabHitsSection";
import { BASE_URL } from "@/lib/config";
import playerPortraits from "../../../data/goalscorer/lab-player-portraits.json";

export const metadata: Metadata = {
  title: "Goalscorer Fair Odds Lab | Starting XI & Bet365 Comparison",
  description: "Compare model fair odds and Bet365 anytime goalscorer prices across expected and confirmed starting lineups, with penalty duties and price timestamps.",
  alternates: { canonical: "/fair-odds-lab" },
  openGraph: { title: "Goalscorer Fair Odds Lab | Il Margine", url: `${BASE_URL}/fair-odds-lab`, type: "website" },
};
// Preserve the existing refresh budget: one shared board and one highlights fetch.
export const revalidate = 300;
const FALLBACK_BASE = "https://jsuu8rjgs8aaukun.public.blob.vercel-storage.com/fair-odds-lab/";
function artifactUrl(filename: string) {
  const configured = process.env.FAIR_ODDS_LAB_ARTIFACT_URL?.trim();
  try { return new URL(filename, configured || FALLBACK_BASE).toString(); }
  catch { return new URL(filename, FALLBACK_BASE).toString(); }
}
async function remote(url: string) {
  try {
    const response = await fetch(url, { next: { revalidate: 300 }, signal: AbortSignal.timeout(6000) });
    return response.ok ? await response.json() : null;
  } catch { return null; }
}
type Highlight = { id: string; player: string; player_photo_url?: string; match: string; date: string; best_odds: number; fair_odds: number;
  league?: string; competition?: string; team?: string; best_bookmaker?: string; goals_scored: number; super_sub_win?: boolean; super_sub_replacement?: string };

async function readClock() { return Date.now(); }

function highlightPortrait(h: Highlight) {
  if (/^https:\/\/images\.fotmob\.com\/image_resources\/playerimages\/\d+\.png$/.test(h.player_photo_url ?? "")) return h.player_photo_url;
  // Legacy player_id values belong to Understat, not FotMob. Use verified identities only.
  const name = h.player.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
  const id = (playerPortraits as Record<string, string>)[`${h.league}|${name}`];
  return id ? `https://images.fotmob.com/image_resources/playerimages/${id}.png` : undefined;
}

export default async function FairOddsLabPage({ searchParams }: { searchParams?: Promise<Record<string, string | string[] | undefined>> }) {
  const params = searchParams ? await searchParams : {};
  const asOf = await readClock();
  const preview = process.env.NODE_ENV === "development" && params.preview === "1";
  const boardUrl = process.env.FAIR_ODDS_LAB_BOARD_URL?.trim() || artifactUrl("daily-board.json");
  const [raw, highlightsRaw] = await Promise.all([
    preview ? fs.readFile(path.join(process.cwd(), "tests/fixtures/lab-daily-board.json"), "utf8").then(JSON.parse).catch(() => null) : remote(boardUrl),
    remote(process.env.FAIR_ODDS_LAB_HIGHLIGHTS_URL?.trim() || artifactUrl("highlights.json")),
  ]);
  const board = isDailyBoard(raw) ? raw : emptyBoard;
  const highlights: Highlight[] = Array.isArray(highlightsRaw?.highlights) ? highlightsRaw.highlights.filter((h: Highlight) =>
    h && typeof h.player === "string" && typeof h.match === "string" && Number.isFinite(h.best_odds) && h.best_odds > 1 &&
    Number.isFinite(h.fair_odds) && h.fair_odds > 1 && h.best_odds > h.fair_odds && h.goals_scored > 0 && !h.super_sub_win).slice(0, 6) : [];
  const structured = { "@context": "https://schema.org", "@type": "WebPage", name: "Goalscorer Fair Odds Lab", url: `${BASE_URL}/fair-odds-lab` };
  return <main className="min-h-screen bg-[#0e181d] text-slate-100">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structured).replace(/</g, "\\u003c") }} />
    <DailyPitchBoard initial={board} boardUrl={boardUrl} asOf={asOf} preview={preview} />
    <div className="mx-auto max-w-[1220px] px-4 pb-10 sm:px-6">
      {highlights.length > 0 && <LabHitsSection highlights={highlights.map(h => ({
        id: h.id, player: h.player, playerPhotoUrl: highlightPortrait(h), match: h.match, date: h.date, team: h.team, league: h.league,
        competition: h.competition || "Goalscorer", bestBookmaker: h.best_bookmaker || "Bet365",
        bestOdds: h.best_odds, fairOdds: h.fair_odds, goalsScored: h.goals_scored,
        modelChancePct: 100 / h.fair_odds, marketChancePct: 100 / h.best_odds,
        priceGapPp: 100 / h.fair_odds - 100 / h.best_odds,
      }))} />}
      <div className="mt-7 flex flex-wrap gap-5 text-sm text-slate-300"><Link href="/resources/fair-odds-lab-explained" className="underline underline-offset-4">How fair odds work</Link><Link href="/" className="underline underline-offset-4">Il Margine</Link></div>
    </div>
  </main>;
}
