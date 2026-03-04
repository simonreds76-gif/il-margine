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

  const fullTipText = bet.player && bet.selection
    ? `${bet.player} ${displaySelection(bet.selection)}`
    : bet.player
      ? bet.player
      : displaySelection(bet.selection);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Hero block: gradient tint + full tip up entirely */}
      <section className="relative pt-6 pb-10 md:pt-8 md:pb-14 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-950/20 via-transparent to-transparent pointer-events-none" />
        <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-emerald-500/60 to-emerald-600/20 pointer-events-none" />
        <div className="relative max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6 text-sm">
            <Link href="/" className="text-slate-500 hover:text-emerald-400/90 transition-colors">
              Home
            </Link>
            <span className="text-slate-600">/</span>
            <Link href={listHref} className="text-slate-500 hover:text-emerald-400/90 transition-colors">
              {listLabel}
            </Link>
            <span className="text-slate-600">/</span>
            <span className="text-emerald-400 font-medium">Tip</span>
          </div>

          <div className="flex items-center gap-2 mb-6 flex-wrap">
            <MarketBadge market={bet.market} category={bet.category} />
            <span className="text-xs font-mono px-2.5 py-1 rounded-md border border-slate-600 text-slate-400 bg-slate-800/50">
              {formatMatchDate(bet.match_date)}
            </span>
            <span className={`text-xs font-mono px-2.5 py-1 rounded-md font-medium ${statusClass}`}>{statusLabel}</span>
          </div>

          {/* Full tip as hero – e.g. "Javi Guerra Over 1.5 Fouls" or "Altmaier" + match */}
          <p className="text-emerald-400/90 text-xs font-semibold uppercase tracking-widest mb-3">Pick</p>
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight mb-3 text-slate-100">
            {fullTipText}
          </h1>
          <p className="text-slate-400 text-base sm:text-lg">{bet.event}</p>
        </div>
      </section>

      <section className="pb-12 md:pb-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="rounded-xl border border-emerald-500/25 bg-slate-900/80 p-6 space-y-4 shadow-xl shadow-emerald-950/20 ring-1 ring-slate-700/50">
            <div className="flex justify-between items-center">
              <span className="text-slate-500 text-sm">Market</span>
              <span className="font-medium text-emerald-400/90">{displaySelection(bet.selection)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500 text-sm">Odds</span>
              <span className="font-mono text-xl font-bold text-emerald-400">{formatOdds(bet.odds)}</span>
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
              <div className="flex justify-between items-center pt-4 border-t border-slate-700/80">
                <span className="text-slate-500 text-sm">Result</span>
                <span className={`font-mono font-semibold ${bet.profit_loss >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {bet.profit_loss >= 0 ? "+" : ""}{bet.profit_loss.toFixed(2)}u
                </span>
              </div>
            )}
            {bet.notes && (
              <div className="pt-4 border-t border-slate-700/80">
                <span className="text-slate-500 text-sm block mb-2">Notes</span>
                <p className="text-slate-300 text-sm leading-relaxed">{bet.notes}</p>
              </div>
            )}
          </div>

          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              href={listHref + "#picks"}
              className="text-sm font-medium text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              ← Back to {listLabel}
            </Link>
            <Link href="/" className="text-sm text-slate-500 hover:text-emerald-400/80 transition-colors">
              Home
            </Link>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
