import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import type { Metadata } from "next";
import { supabase } from "@/lib/supabase";
import { BASE_URL } from "@/lib/config";
import { slugifyTip, parseTipSlugId } from "@/lib/slugify";
import { isWorldCupPropsTip, WORLD_CUP_TIP_IMAGE_PATH } from "@/lib/world-cup-tips";
import BookmakerLogo from "@/components/BookmakerLogo";
import MarketBadge from "@/components/MarketBadge";
import PropsAlertsCta from "@/components/PropsAlertsCta";
import TipPageTracker from "@/components/TipPageTracker";
import Footer from "@/components/Footer";
import { formatStake, formatMatchDate, formatOdds } from "@/lib/format";
import { assessTipSeoReadiness, stripTipSeoMarker, tipPreviewPath } from "@/lib/tip-seo";

// Admin changes invalidate the affected tip URL directly. Keep a daily fallback
// for automated settlements instead of regenerating every crawled tip each minute.
export const revalidate = 86400;
const DEFAULT_SOCIAL_IMAGE = `${BASE_URL}/og-social-20260629.png`;

/** Spell out common abbreviations on the tip page (no need to shorten here). */
function displaySelection(selection: string): string {
  const s = (selection || "").trim();
  if (s.toUpperCase() === "ML") return "Moneyline";
  return s;
}

function formatAuditTimestamp(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
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
  const title = `${bet.event} - ${bet.selection} | Betting Tip`;
  const description =
    bet.market === "tennis"
      ? `Tennis tip: ${bet.event}. ${bet.selection} at ${formatOdds(bet.odds)}. ${bet.category}. Il Margine.`
      : `Player props tip: ${bet.event}. ${bet.player ? bet.player + " - " : ""}${bet.selection} at ${formatOdds(bet.odds)}. Il Margine.`;
  const url = `${BASE_URL}/tips/${canonicalSlug}`;
  const worldCupGraphic = isWorldCupPropsTip(bet) ? `${BASE_URL}${WORLD_CUP_TIP_IMAGE_PATH}` : null;
  const seoAssessment = assessTipSeoReadiness(bet);
  const canonicalUrl = seoAssessment.eligible ? `${BASE_URL}${tipPreviewPath(bet)}` : url;

  return {
    title,
    description,
    alternates: { canonical: canonicalUrl },
    openGraph: {
      type: "article",
      locale: "en_GB",
      url,
      siteName: "Il Margine",
      title,
      description,
      publishedTime: bet.posted_at,
      modifiedTime: bet.settled_at ?? bet.posted_at,
      images: [
        {
          url: worldCupGraphic ?? DEFAULT_SOCIAL_IMAGE,
          width: 1200,
          height: worldCupGraphic ? 1200 : 630,
          alt: worldCupGraphic ? "Il Margine World Cup free picks" : "Il Margine betting with mathematical edge",
          type: "image/png",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [worldCupGraphic ?? DEFAULT_SOCIAL_IMAGE],
    },
    robots: {
      index: false,
      follow: true,
    },
  };
}

export default async function TipPage({ params }: PageProps) {
  const { slugId } = await params;
  const id = parseTipSlugId(slugId);
  if (id === null) notFound();
  const bet = await getBet(id);
  if (!bet) notFound();

  if (assessTipSeoReadiness(bet).eligible) {
    permanentRedirect(tipPreviewPath(bet));
  }

  const canonicalSlug = slugifyTip(bet.event, bet.id);
  if (slugId !== canonicalSlug) {
    permanentRedirect(`/tips/${canonicalSlug}`);
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

  const heroName = bet.player || displaySelection(bet.selection);
  const heroSelection = bet.player ? displaySelection(bet.selection) : null;
  const postedLabel = formatAuditTimestamp(bet.posted_at);
  const settledLabel = formatAuditTimestamp(bet.settled_at);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <TipPageTracker betId={bet.id} market={bet.market} category={bet.category} status={bet.status} />
      {/* Hero: player name huge, selection as accent subtitle, match as context */}
      <section className="relative pt-6 pb-10 md:pt-8 md:pb-14 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-950/20 via-transparent to-transparent pointer-events-none" />
        <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-emerald-500/60 to-emerald-600/0 pointer-events-none" />
        <div className="relative max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6 text-sm">
            <Link href="/" className="text-slate-500 hover:text-emerald-400/90 transition-colors">Home</Link>
            <span className="text-slate-600">/</span>
            <Link href={listHref} className="text-slate-500 hover:text-emerald-400/90 transition-colors">{listLabel}</Link>
            <span className="text-slate-600">/</span>
            <span className="text-emerald-400 font-medium">Tip</span>
          </div>

          <div className="flex items-center gap-2 mb-5 flex-wrap">
            <MarketBadge market={bet.market} category={bet.category} event={bet.event} />
            <span className="text-xs font-mono px-2.5 py-1 rounded-md border border-slate-600 text-slate-400 bg-slate-800/50">
              {formatMatchDate(bet.match_date)}
            </span>
            <span className={`text-xs font-mono px-2.5 py-1 rounded-md font-medium ${statusClass}`}>{statusLabel}</span>
          </div>

          <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight text-white mb-2">
            {heroName}
          </h1>
          {heroSelection && (
            <p className="text-xl sm:text-2xl font-medium text-emerald-400 mb-3">{heroSelection}</p>
          )}
          <p className="text-slate-500 text-base">{bet.event}</p>
          <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-800/70 pt-4 text-xs text-slate-500">
            {postedLabel ? (
              <span>
                Published{" "}
                <time dateTime={bet.posted_at} className="font-mono text-slate-300">
                  {postedLabel}
                </time>
              </span>
            ) : null}
            {settledLabel ? (
              <span>
                Settled{" "}
                <time dateTime={bet.settled_at ?? undefined} className="font-mono text-slate-300">
                  {settledLabel}
                </time>
              </span>
            ) : null}
            <span>Times shown in London time</span>
          </div>
        </div>
      </section>

      {/* Card: odds, stake, bookmaker as a 3-column grid — no Market row (it's in the hero) */}
      <section className="pb-12 md:pb-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="rounded-xl border border-slate-700/80 bg-slate-900/80 shadow-xl ring-1 ring-slate-800/60 overflow-hidden">
            <div className="grid grid-cols-3 divide-x divide-slate-700/60">
              <div className="p-6 text-center">
                <span className="block text-[11px] font-medium uppercase tracking-widest text-slate-500 mb-2">Posted odds</span>
                <span className="block font-mono text-2xl sm:text-3xl font-bold text-white">{formatOdds(bet.odds)}</span>
              </div>
              <div className="p-6 text-center">
                <span className="block text-[11px] font-medium uppercase tracking-widest text-slate-500 mb-2">Stake</span>
                <span className="block font-mono text-2xl sm:text-3xl font-bold text-white">{formatStake(bet.stake)}u</span>
              </div>
              <div className="p-6 flex flex-col items-center justify-center">
                <span className="block text-[11px] font-medium uppercase tracking-widest text-slate-500 mb-3">Bookmaker</span>
                <BookmakerLogo
                  bookmaker={Array.isArray(bet.bookmaker) ? bet.bookmaker[0] : bet.bookmaker}
                  size="lg"
                />
              </div>
            </div>

            {(bet.status === "won" || bet.status === "lost") && bet.profit_loss != null && (
              <div className="border-t border-slate-700/60 px-6 py-5 flex justify-between items-center">
                <span className="text-sm font-medium uppercase tracking-widest text-slate-500">Result</span>
                <span className={`font-mono text-xl font-bold ${bet.profit_loss >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {bet.profit_loss >= 0 ? "+" : ""}{bet.profit_loss.toFixed(2)}u
                </span>
              </div>
            )}

            {stripTipSeoMarker(bet.notes) && (
              <div className="border-t border-slate-700/60 px-6 py-5">
                <span className="text-sm font-medium uppercase tracking-widest text-slate-500 block mb-2">Notes</span>
                <p className="text-slate-300 text-sm leading-relaxed">{stripTipSeoMarker(bet.notes)}</p>
              </div>
            )}
          </div>

          {bet.market === "props" ? <PropsAlertsCta source="props_tip_page" className="mt-6" /> : null}

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
