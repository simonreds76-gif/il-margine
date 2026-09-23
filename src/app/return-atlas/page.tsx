import EditorialIcon from "@/components/EditorialIcon";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import ReturnAtlasClient from "@/components/return-atlas/ReturnAtlasClient";
import release from "@/data/return-atlas-release.json";
import "./return-atlas.css";

export const dynamic = "force-static";
export const revalidate = false;

const title = "Return Atlas: ATP Player ROI & Betting History";
const description = "Explore ATP tennis players’ historical betting returns at Pinnacle odds. Compare favourites and underdogs, betting on or against, by season, surface and odds range.";
const url = "https://ilmargine.bet/return-atlas";
export const metadata: Metadata = {
  title, description, alternates: { canonical: url }, robots: { index: true, follow: true },
  openGraph: { title, description, url, type: "website", images: [{ url: `${url}/assets/share-20260920-square.png`, width: 1200, height: 1200, type: "image/png", alt: "Return Atlas — ATP tennis betting returns by player, season and surface" }] },
  twitter: { card: "summary_large_image", title, description, images: [`${url}/assets/share-20260920-wide.png`] },
};

const date = (value: string) => new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(value + "T12:00:00Z"));
const archiveMatches = Object.values(release.coverage).reduce((total, year) => total + year.archive_completed_main_draw_matches, 0);
const coveragePercent = (100 * release.matches / archiveMatches).toFixed(1);

export default function ReturnAtlasPage() {
  return <div className="min-h-screen bg-[#0f1117] text-slate-100">
    <main className="return-atlas" data-look="ledger">
      <header className="hero page-heading">
        <div className="hero-copy">
          <PageHomeLink />
          <p className="eyebrow">Tennis research</p>
          <h1 className="product-wordmark"><span className="sr-only">Return Atlas: ATP Tennis Betting History</span><Image src={release.logoUrl} alt="" aria-hidden="true" width={2172} height={724} priority unoptimized /></h1>
          <p className="intro">Explore ATP players’ historical returns. Compare betting on or against a player by season, surface, odds range and favourite or underdog status.</p>
          <div className="hero-meta"><span>ATP main tour</span><span>Pinnacle odds</span><span>1u per bet</span><a href="#how-it-works">How it works ↓</a></div>
          <p className="release-dates">Data checked {date(release.checkedAt)} <span aria-hidden="true">·</span> Latest included match {date(release.through)}</p>
        </div>
      </header>
      <ReturnAtlasClient indexUrl={release.indexUrl} detailsBase={release.detailsBase} version={release.version} checkedAt={release.checkedAt} />
      <section className="atlas-about" aria-label="About Return Atlas">
        <p className="about-eyebrow">THE RECORD BEHIND THE RETURNS</p>
        <h2>ATP tennis betting history.<br />Every player has a different story.</h2>
        <p className="about-intro">See how backing a player—or their opponent—would have performed at Pinnacle odds. Compare seasons, surfaces and results as favourite or underdog across ATP main-tour singles, including the Grand Slams.</p>
        <dl className="about-numbers">
          <div><dt>Matches with odds</dt><dd>{release.matches.toLocaleString("en-GB")}</dd></div>
          <div><dt>Player records</dt><dd>{release.players.toLocaleString("en-GB")}</dd></div>
          <div><dt>Seasons covered</dt><dd>{release.years[0]}–{release.years.at(-1)}</dd></div>
        </dl>
        <div className="about-guide">
          <div><EditorialIcon name="compare" className="mb-3 h-10 w-10" /><h3>Bet on or bet against</h3><p>Back the named player, or back their opponent at the opponent’s recorded price. Each view shows its own profit and ROI.</p></div>
          <div><EditorialIcon name="markets" className="mb-3 h-10 w-10" /><h3>Favourite or underdog</h3><p>Split the record by the named player’s position in the market. The labels describe that player, whichever side you back.</p></div>
          <div><EditorialIcon name="bankroll" className="mb-3 h-10 w-10" /><h3>The same stake, every time</h3><p>Every match uses a hypothetical 1-unit stake. Wins and losses both count, so you can compare records on the same basis.</p></div>
        </div>
        <details><summary>Which ATP matches are included?</summary><p>The current release includes <strong>{release.matches.toLocaleString("en-GB")} of {archiveMatches.toLocaleString("en-GB")} eligible completed matches in our results archive ({coveragePercent}%)</strong>. Coverage runs from {release.years[0]} to {date(release.through)}; it is not a complete record of every ATP match or player’s career.</p><p>Only completed main-draw singles with a verified result and Pinnacle prices for both players are included. Qualifying, Challenger, ITF, team events, exhibitions, Olympics, retirements, walkovers and unresolved records are excluded. Missing matches can affect returns and rankings.</p><p>Archives were checked on {date(release.checkedAt)}. That is separate from the latest included match date.</p></details>
        <details><summary className="cursor-pointer py-3 font-semibold text-slate-200">How is player ROI calculated?</summary><p>ROI is net profit divided by total stakes, expressed as a percentage. At a flat stake of 1u, a win at 2.50 returns 1.50u profit and a loss costs 1u. The table includes both, using the recorded price for the side you select.</p></details>
        <details><summary className="cursor-pointer py-3 font-semibold text-slate-200">What counts as a favourite or underdog?</summary><p>The favourite has the shorter of the two recorded prices; the underdog has the longer price. Equal prices appear in all matches but neither split. These labels always describe the named player, including when you choose to bet against them.</p></details>
        <details><summary className="cursor-pointer py-3 font-semibold text-slate-200">How do odds-range filters work?</summary><p>Choose a preset range or enter your own minimum and maximum decimal odds. The range always describes the named player, even when betting against them. Rankings, profit curves and match counts update for that selection. In each player’s record, compare the odds bands side by side and select one to see the matches behind it.</p><p>Preset bands exclude the lower boundary and include the upper boundary; custom ranges include both limits. The minimum-match filter applies after the odds, season, surface and player-role filters. A high historical ROI from a small sample is not evidence of a repeatable edge.</p></details>
        <details><summary className="cursor-pointer py-3 font-semibold text-slate-200">Are these Il Margine’s published tennis picks?</summary><p>No. This is a historical research tool showing what backing each player or opponent would have returned. Our <Link href="/tennis-tips" prefetch={false}>published tennis tips and results</Link> are tracked separately.</p></details>
        <p className="about-note">Historical returns describe what happened. They do not predict future profits.</p>
        <Link href="/return-atlas/credits" prefetch={false}>Data &amp; photo credits →</Link>
      </section>
    </main>
    <Footer />
  </div>;
}
