import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { Metadata } from "next";
import { supabase } from "@/lib/supabase";
import { BASE_URL } from "@/lib/config";
import { slugifyTip, parseTipSlugId } from "@/lib/slugify";
import BookmakerLogo from "@/components/BookmakerLogo";
import MarketBadge from "@/components/MarketBadge";
import Footer from "@/components/Footer";
import { formatStake, formatMatchDate, formatOdds } from "@/lib/format";

/** Revalidate tip pages every 60s so settled status and new tips show without full dynamic. */
export const revalidate = 60;

/** Spell out common abbreviations on the tip page (no need to shorten here). */
function displaySelection(selection: string): string {
  const s = (selection || "").trim();
  if (s.toUpperCase() === "ML") return "Moneyline";
  return s;
}

interface PageProps {
  params: Promise<{ slugId: string }>;
}

async function getBet(id: number) {
  const { data, error } = await supabase
    .from("bets")
    .select("*, bookmaker:bookmakers(*)")
    .eq("id", id)
    .single();
  if (error || !data) return null;
  return data;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slugId } = await params;
  const id = parseTipSlugId(slugId);
  if (id === null) return { title: "Tip not found" };
  const bet = await getBet(id);
  if (!bet) return { title: "Tip not found" };

  const canonicalSlug = slugifyTip(bet.event, bet.id);
  const title = `${bet.event} – ${bet.selection} | Betting Tip`;
  const description =
    bet.market === "tennis"
      ? `Tennis tip: ${bet.event}. ${bet.selection} at ${formatOdds(bet.odds)}. ${bet.category}. Il Margine.`
      : `Player props tip: ${bet.event}. ${bet.player ? bet.player + " – " : ""}${bet.selection} at ${formatOdds(bet.odds)}. Il Margine.`;
  const url = `${BASE_URL}/tips/${canonicalSlug}`;

  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      locale: "en_GB",
      url,
      siteName: "Il Margine",
      title,
      description,
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
    robots: "index, follow",
  };
}

export default async function TipPage({ params }: PageProps) {
  const { slugId } = await params;
  const id = parseTipSlugId(slugId);
  if (id === null) notFound();
  const bet = await getBet(id);
  if (!bet) notFound();

  const canonicalSlug = slugifyTip(bet.event, bet.id);
  if (slugId !== canonicalSlug) {
    redirect(`/tips/${canonicalSlug}`);
  }

  const listHref = bet.market === "tennis" ? "/tennis-tips" : bet.market === "props" ? "/player-props" : "/";
  const listLabel = bet.market === "tennis" ? "Tennis Tips" : bet.market === "props" ? "Player Props" : "Home";

  const statusLabel = bet.status === "pending" ? "Pending" : bet.status === "won" ? "Won" : bet.status === "lost" ? "Lost" : "Void";
  const statusClass =
    bet.status === "pending"
      ? "bg-amber-500/20 text-amber-400"
      : bet.status === "won"
        ? "bg-emerald-500/20 text-emerald-400"
        : bet.status === "lost"
          ? "bg-red-500/20 text-red-400"
          : "bg-slate-500/20 text-slate-400";

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-6 pb-12 md:pt-8 md:pb-16 border-b border-slate-800/50">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6 text-sm">
            <Link href="/" className="text-slate-500 hover:text-slate-300">
              Home
            </Link>
            <span className="text-slate-600">/</span>
            <Link href={listHref} className="text-slate-500 hover:text-slate-300">
              {listLabel}
            </Link>
            <span className="text-slate-600">/</span>
            <span className="text-emerald-400">Tip</span>
          </div>

          <div className="flex items-center gap-2 mb-6">
            <MarketBadge market={bet.market} category={bet.category} />
            <span className="text-xs font-mono px-2 py-1 rounded border border-slate-700 text-slate-400">
              {formatMatchDate(bet.match_date)}
            </span>
            <span className={`text-xs font-mono px-2 py-1 rounded ${statusClass}`}>{statusLabel}</span>
          </div>

          {/* The pick is the hero – large and bold. Match is context. */}
          {bet.player ? (
            <>
              <p className="text-slate-500 text-sm font-medium uppercase tracking-wider mb-1">Pick</p>
              <h1 className="text-4xl sm:text-5xl font-bold text-slate-100 tracking-tight mb-2">
                {bet.player}
              </h1>
              <p className="text-lg text-slate-400 mb-8">{bet.event}</p>
            </>
          ) : (
            <>
              <p className="text-slate-500 text-sm font-medium uppercase tracking-wider mb-1">Pick</p>
              <h1 className="text-4xl sm:text-5xl font-bold text-slate-100 tracking-tight mb-2">
                {displaySelection(bet.selection)}
              </h1>
              <p className="text-lg text-slate-400 mb-8">{bet.event}</p>
            </>
          )}

          <div className="bg-slate-900/60 rounded-xl border border-slate-700/80 p-6 space-y-4 shadow-lg">
            <div className="flex justify-between items-center">
              <span className="text-slate-500 text-sm">Market</span>
              <span className="font-medium text-slate-200">{displaySelection(bet.selection)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500 text-sm">Odds</span>
              <span className="font-mono text-lg font-semibold text-slate-100">{formatOdds(bet.odds)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500 text-sm">Stake</span>
              <span className="font-mono text-slate-200">{formatStake(bet.stake)}u</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500 text-sm">Bookmaker</span>
              <div className="flex items-center justify-end">
                <BookmakerLogo
                  bookmaker={Array.isArray(bet.bookmaker) ? bet.bookmaker[0] : bet.bookmaker}
                  size="sm"
                />
              </div>
            </div>
            {(bet.status === "won" || bet.status === "lost") && bet.profit_loss != null && (
              <div className="flex justify-between items-center pt-2 border-t border-slate-700">
                <span className="text-slate-500">Result</span>
                <span className={bet.profit_loss >= 0 ? "text-emerald-400 font-mono" : "text-red-400 font-mono"}>
                  {bet.profit_loss >= 0 ? "+" : ""}{bet.profit_loss.toFixed(2)}u
                </span>
              </div>
            )}
            {bet.notes && (
              <div className="pt-4 border-t border-slate-700">
                <span className="text-slate-500 text-sm block mb-2">Notes</span>
                <p className="text-slate-300 text-sm leading-relaxed">{bet.notes}</p>
              </div>
            )}
          </div>

          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              href={listHref + "#picks"}
              className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              ← Back to {listLabel}
            </Link>
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">
              Home
            </Link>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
