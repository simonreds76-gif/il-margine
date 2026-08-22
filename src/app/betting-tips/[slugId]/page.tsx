import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import BookmakerLogo from "@/components/BookmakerLogo";
import Footer from "@/components/Footer";
import MarketBadge from "@/components/MarketBadge";
import PropsAlertsCta from "@/components/PropsAlertsCta";
import TipPageTracker from "@/components/TipPageTracker";
import { BASE_URL } from "@/lib/config";
import { formatMatchDate, formatOdds, formatStake } from "@/lib/format";
import { fetchSeoTipFixture, type SeoTipBet } from "@/lib/tip-seo-server";

// Admin mutations explicitly invalidate betting-tip pages, so public reads can
// use a long cache without delaying edits or settlements.
export const revalidate = 86400;

interface PageProps {
  params: Promise<{ slugId: string }>;
}

function marketLabel(market: string): string {
  return market === "tennis" ? "Tennis match preview" : "Player props preview";
}

function hubFor(market: string): { href: string; label: string } {
  return market === "tennis"
    ? { href: "/tennis-tips", label: "Tennis Tips" }
    : { href: "/player-props", label: "Player Props" };
}

function resultLabel(status: string): string {
  if (status === "won") return "Won";
  if (status === "lost") return "Lost";
  if (status === "void") return "Void";
  return "Pending";
}

function resultClasses(status: string): string {
  if (status === "won") return "border-emerald-400/25 bg-emerald-400/10 text-emerald-300";
  if (status === "lost") return "border-rose-400/25 bg-rose-400/10 text-rose-300";
  if (status === "void") return "border-slate-500/30 bg-slate-500/10 text-slate-300";
  return "border-amber-400/25 bg-amber-400/10 text-amber-200";
}

function selectionLabel(bet: SeoTipBet): string {
  const selection = bet.selection.trim().toUpperCase() === "ML" ? "Moneyline" : bet.selection;
  return bet.player ? `${bet.player} - ${selection}` : selection;
}

function bookmakerFor(bet: SeoTipBet) {
  const value = bet.bookmaker as SeoTipBet["bookmaker"] | SeoTipBet["bookmaker"][];
  return Array.isArray(value) ? value[0] : value;
}

function formatPublishedDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatSeoDate(value: string): string {
  const date = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function previewDescription(fixture: Awaited<ReturnType<typeof fetchSeoTipFixture>>): string {
  if (!fixture) return "";
  const selections = fixture.bets.slice(0, 3).map(selectionLabel).join(", ");
  const suffix = fixture.bets.length > 3 ? ` and ${fixture.bets.length - 3} more` : "";
  return `${fixture.seed.event} prediction and betting analysis for ${formatMatchDate(fixture.seed.match_date)}. Tracked selections: ${selections}${suffix}.`;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slugId } = await params;
  const fixture = await fetchSeoTipFixture(slugId);
  if (!fixture) {
    return { title: "Betting preview not found", robots: { index: false, follow: true } };
  }

  const dateLabel = formatSeoDate(fixture.seed.match_date);
  const title =
    fixture.seed.market === "tennis"
      ? `${fixture.seed.event} Prediction & Betting Tips - ${dateLabel}`
      : `${fixture.seed.event} Player Props & Betting Tips - ${dateLabel}`;
  const description = previewDescription(fixture);
  const canonicalUrl = `${BASE_URL}${fixture.canonicalPath}`;
  const imageUrl = `${canonicalUrl}/opengraph-image`;

  return {
    title,
    description,
    alternates: { canonical: canonicalUrl },
    robots: { index: !fixture.allVoid, follow: true },
    openGraph: {
      type: "website",
      locale: "en_GB",
      url: canonicalUrl,
      siteName: "Il Margine",
      title,
      description,
      images: [{ url: imageUrl, width: 1200, height: 630, alt: `${fixture.seed.event} betting preview` }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [imageUrl],
    },
  };
}

export default async function BettingPreviewPage({ params }: PageProps) {
  const { slugId } = await params;
  const fixture = await fetchSeoTipFixture(slugId);
  if (!fixture) notFound();
  if (`/betting-tips/${slugId}` !== fixture.canonicalPath) permanentRedirect(fixture.canonicalPath);

  const hub = hubFor(fixture.seed.market);
  const description = previewDescription(fixture);
  const canonicalUrl = `${BASE_URL}${fixture.canonicalPath}`;
  const imageUrl = `${canonicalUrl}/opengraph-image`;
  const reasoning = Array.from(
    new Set(fixture.analyses.map((entry) => entry.assessment.analysis.trim()).filter(Boolean)),
  );
  const analysisCopy = reasoning.length
    ? reasoning
    : [
        `Il Margine logged ${fixture.bets.length} ${fixture.bets.length === 1 ? "selection" : "selections"} for ${fixture.seed.event} before the match. The ledger preserves the original pick, price, stake and bookmaker.`,
        "This page updates the same public record after settlement. Posted odds are not replaced with later market prices.",
      ];
  const settled = fixture.bets.filter((bet) => bet.status !== "pending");
  const totalProfit = settled.reduce((sum, bet) => sum + Number(bet.profit_loss || 0), 0);
  const webPageSchema = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name:
      fixture.seed.market === "tennis"
        ? `${fixture.seed.event} prediction and betting tips`
        : `${fixture.seed.event} player props and betting tips`,
    description,
    image: [imageUrl],
    datePublished: fixture.datePublished,
    dateModified: fixture.dateModified,
    mainEntityOfPage: canonicalUrl,
    // This is a betting-analysis page, not a ticketable event page. Using
    // SportsEvent here makes Google require venue, organizer and offer data.
    about: {
      "@type": "Thing",
      name: fixture.seed.event,
    },
    mainEntity: {
      "@type": "ItemList",
      numberOfItems: fixture.bets.length,
      itemListElement: fixture.bets.map((bet, index) => ({
        "@type": "ListItem",
        position: index + 1,
        item: {
          "@type": "Thing",
          name: selectionLabel(bet),
          description: `${selectionLabel(bet)} at ${formatOdds(bet.odds)}, ${formatStake(bet.stake)} units.`,
        },
      })),
    },
  };
  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: BASE_URL },
      { "@type": "ListItem", position: 2, name: hub.label, item: `${BASE_URL}${hub.href}` },
      { "@type": "ListItem", position: 3, name: fixture.seed.event, item: canonicalUrl },
    ],
  };

  return (
    <div className="min-h-screen bg-[#0b0e14] text-slate-100">
      <TipPageTracker
        betId={fixture.canonicalId}
        market={fixture.seed.market}
        category={fixture.seed.category}
        status={fixture.seed.status}
      />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(webPageSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <main>
        <section className="relative overflow-hidden border-b border-slate-800/80">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_0%,rgba(16,185,129,0.16),transparent_38%),radial-gradient(circle_at_88%_28%,rgba(245,158,11,0.09),transparent_28%)]" />
          <div className="relative mx-auto max-w-5xl px-4 py-10 sm:px-6 md:py-16 lg:px-8">
            <nav className="mb-8 flex flex-wrap items-center gap-2 text-sm text-slate-500" aria-label="Breadcrumb">
              <Link href="/" className="transition-colors hover:text-emerald-300">Home</Link>
              <span>/</span>
              <Link href={hub.href} className="transition-colors hover:text-emerald-300">{hub.label}</Link>
              <span>/</span>
              <span className="text-slate-300">Match preview</span>
            </nav>

            <div className="mb-5 flex flex-wrap items-center gap-3">
              <MarketBadge
                market={fixture.seed.market}
                category={fixture.seed.category}
                event={fixture.seed.event}
                showLabel
              />
              <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
                {marketLabel(fixture.seed.market)}
              </span>
              <span className="font-mono text-xs text-slate-400">{formatMatchDate(fixture.seed.match_date)}</span>
            </div>

            <h1 className="max-w-4xl text-4xl font-black tracking-[-0.035em] text-white sm:text-5xl md:text-6xl">
              {fixture.seed.event}
            </h1>
            <p className="mt-4 max-w-3xl text-lg leading-relaxed text-slate-300">
              Posted selections, prices and transparent settlement for this fixture.
            </p>
            <div className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-500">
              <span>
                Published <time dateTime={fixture.datePublished} className="font-mono text-slate-300">{formatPublishedDate(fixture.datePublished)}</time>
              </span>
              <span>{fixture.bets.length} tracked {fixture.bets.length === 1 ? "selection" : "selections"}</span>
              <span>Odds and stakes are recorded at publication</span>
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-5xl gap-8 px-4 py-10 sm:px-6 md:py-14 lg:grid-cols-[minmax(0,1fr)_300px] lg:px-8">
          <div className="space-y-10">
            <section aria-labelledby="selections-heading">
              <div className="mb-5 flex items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400">Tracked ledger</p>
                  <h2 id="selections-heading" className="mt-2 text-2xl font-bold text-white">Selections for the match</h2>
                </div>
              </div>

              <div className="space-y-3">
                {fixture.bets.map((bet) => (
                  <article key={bet.id} className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/65">
                    <div className="grid gap-5 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                      <div>
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] ${resultClasses(bet.status)}`}>
                            {resultLabel(bet.status)}
                          </span>
                          <span className="text-xs text-slate-500">{bet.category}</span>
                        </div>
                        <h3 className="text-lg font-bold text-white">{selectionLabel(bet)}</h3>
                      </div>

                      <div className="grid grid-cols-3 gap-2 sm:min-w-[285px]">
                        <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2.5">
                          <span className="block text-[9px] uppercase tracking-[0.16em] text-slate-600">Odds</span>
                          <span className="mt-1 block font-mono text-lg font-bold text-white">{formatOdds(bet.odds)}</span>
                        </div>
                        <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2.5">
                          <span className="block text-[9px] uppercase tracking-[0.16em] text-slate-600">Stake</span>
                          <span className="mt-1 block font-mono text-lg font-bold text-white">{formatStake(bet.stake)}u</span>
                        </div>
                        <div className="flex min-w-0 items-center justify-center rounded-xl border border-slate-800 bg-slate-950/60 px-2 py-2.5">
                          <BookmakerLogo bookmaker={bookmakerFor(bet)} size="sm" noLink />
                        </div>
                      </div>
                    </div>

                    {bet.status !== "pending" ? (
                      <div className="flex items-center justify-between border-t border-slate-800 px-5 py-3 text-sm">
                        <span className="text-slate-500">Settled result</span>
                        <span className={`font-mono font-bold ${Number(bet.profit_loss || 0) >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {Number(bet.profit_loss || 0) >= 0 ? "+" : ""}
                          {Number(bet.profit_loss || 0).toFixed(2)}u
                        </span>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>

              {fixture.seed.market === "props" ? (
                <PropsAlertsCta source="seo_match_preview" className="mt-6" />
              ) : null}
            </section>

            <section aria-labelledby="analysis-heading" className="rounded-2xl border border-slate-800 bg-slate-900/45 p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-300">
                {reasoning.length ? "Match analysis" : "Recorded betting view"}
              </p>
              <h2 id="analysis-heading" className="mt-2 text-2xl font-bold text-white">
                {reasoning.length ? "Why these bets" : "What this page records"}
              </h2>
              <div className="mt-5 space-y-5 text-base leading-8 text-slate-300">
                {analysisCopy.map((paragraph, index) => <p key={`${index}-${paragraph.slice(0, 20)}`}>{paragraph}</p>)}
              </div>
            </section>

            {settled.length > 0 ? (
              <section aria-labelledby="result-heading" className="rounded-2xl border border-slate-800 bg-slate-950/55 p-6">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Transparent update</p>
                <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
                  <div>
                    <h2 id="result-heading" className="text-xl font-bold text-white">Settled match result</h2>
                    <p className="mt-1 text-sm text-slate-500">{settled.length} of {fixture.bets.length} selections settled.</p>
                  </div>
                  <span className={`font-mono text-2xl font-black ${totalProfit >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                    {totalProfit >= 0 ? "+" : ""}{totalProfit.toFixed(2)}u
                  </span>
                </div>
              </section>
            ) : null}
          </div>

          <aside className="space-y-5 lg:sticky lg:top-6 lg:self-start">
            <div className="rounded-2xl border border-emerald-400/20 bg-emerald-950/20 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">Record policy</p>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                Every selection remains in the public ledger at its original posted odds and stake. Results are added after settlement.
              </p>
              <Link href="/track-record" className="mt-4 inline-flex text-sm font-semibold text-emerald-300 hover:text-emerald-200">
                View the full record {"->"}
              </Link>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">More analysis</p>
              <Link href={hub.href} className="mt-3 block text-lg font-bold text-white hover:text-emerald-300">
                Browse {hub.label}
              </Link>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                Current selections, settled results and model-led betting analysis.
              </p>
            </div>
          </aside>
        </section>
      </main>
      <Footer />
    </div>
  );
}
