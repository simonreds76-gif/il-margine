import fs from "node:fs/promises";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";
import { DailyPitchBoard } from "@/components/fair-odds-lab/DailyPitchBoard";
import { emptyBoard, isDailyBoard } from "@/components/fair-odds-lab/daily-board-data";
import { BASE_URL } from "@/lib/config";

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
type Highlight = { id: string; player: string; match: string; date: string; best_odds: number; fair_odds: number;
  goals_scored: number; super_sub_win?: boolean; super_sub_replacement?: string };

async function readClock() { return Date.now(); }

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
      {highlights.length > 0 && !preview && <section className="mt-4 border-t border-slate-700 pt-7" aria-label="Selected scoring examples"><h2 className="text-xl font-semibold">Latest scoring examples</h2><p className="mt-2 text-sm text-slate-400">Selected winners from previously recorded Lab research signals. This is not a complete performance record or evidence of profitability.</p><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{highlights.map(h => <article key={h.id} className="rounded-xl border border-slate-700 bg-[#17262d] p-4"><p className="text-xs text-emerald-300">Scored · {h.date}</p><h3 className="mt-1 font-semibold">{h.player}</h3><p className="mt-1 text-xs text-slate-400">{h.match}</p><p className="mt-3 font-mono text-sm">Recorded fair {h.fair_odds.toFixed(2)} · Bet365 {h.best_odds.toFixed(2)}</p></article>)}</div></section>}
      <div className="mt-7 flex flex-wrap gap-5 text-sm text-slate-300"><Link href="/resources/fair-odds-lab-explained" className="underline underline-offset-4">How fair odds work</Link><Link href="/" className="underline underline-offset-4">Il Margine</Link></div>
    </div>
  </main>;
}
