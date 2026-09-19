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

const title = "Return Atlas | ATP Tennis Player ROI & Betting History";
const description = "Explore ATP tennis players’ historical betting returns at Pinnacle odds. Compare favourites and underdogs, betting on or against, by season and surface.";
const url = "https://ilmargine.bet/return-atlas";
export const metadata: Metadata = {
  title, description, alternates: { canonical: url }, robots: { index: true, follow: true },
  openGraph: { title, description, url, type: "website" },
  twitter: { card: "summary_large_image", title, description },
};

const date = (value: string) => new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(value + "T12:00:00Z"));

export default function ReturnAtlasPage() {
  return <div className="min-h-screen bg-[#0f1117] text-slate-100">
    <main className="return-atlas" data-look="ledger">
      <header className="hero page-heading">
        <div className="hero-copy">
          <PageHomeLink />
          <p className="eyebrow">Tennis research</p>
          <h1 className="product-wordmark"><Image src={release.logoUrl} alt="Return Atlas" width={2172} height={724} priority unoptimized /></h1>
          <p className="intro">Explore ATP players’ historical returns. Compare betting on or against a player by season, surface and favourite or underdog status.</p>
          <div className="hero-meta"><span>ATP main tour</span><span>Pinnacle odds</span><span>1u per bet</span><a href="#how-it-works">How it works ↓</a></div>
          <p className="release-dates">Data checked {date(release.checkedAt)} <span aria-hidden="true">·</span> Latest included match {date(release.through)}</p>
        </div>
      </header>
      <ReturnAtlasClient indexUrl={release.indexUrl} detailsBase={release.detailsBase} version={release.version} checkedAt={release.checkedAt} />
      <section className="atlas-about" aria-label="About Return Atlas">
        <h2>ATP tennis betting history, player by player</h2>
        <p>Explore {release.matches.toLocaleString("en-GB")} matched results across {release.players} players from {release.years[0]}–{release.years.at(-1)}. Every included bet uses a hypothetical one-unit stake. Betting against a player means backing their opponent at the opponent’s recorded odds.</p>
        <p>Favourite and underdog describe the named player. Historical returns include winning and losing bets and do not predict future profits. Qualifying, Challenger, ITF, team events, unfinished matches and unresolved records are excluded. The latest included match date can be earlier than the date the archives were checked.</p>
        <details><summary className="cursor-pointer py-3 font-semibold text-slate-200">How is player ROI calculated?</summary><p>ROI is net profit divided by total stakes, expressed as a percentage. At a flat stake of 1u, a win at 2.50 returns 1.50u profit and a loss costs 1u. The table includes both, using the recorded price for the side you select.</p></details>
        <details><summary className="cursor-pointer py-3 font-semibold text-slate-200">What counts as a favourite or underdog?</summary><p>The favourite has the shorter of the two recorded prices; the underdog has the longer price. Equal prices appear in all matches but neither split. These labels always describe the named player, including when you choose to bet against them.</p></details>
        <details><summary className="cursor-pointer py-3 font-semibold text-slate-200">Are these Il Margine’s published tennis picks?</summary><p>No. This is a historical research tool showing what backing each player or opponent would have returned. Our <Link href="/tennis-tips" prefetch={false}>published tennis tips and results</Link> are tracked separately.</p></details>
        <Link href="/return-atlas/credits" prefetch={false}>Data &amp; photo credits →</Link>
      </section>
    </main>
    <Footer />
  </div>;
}
