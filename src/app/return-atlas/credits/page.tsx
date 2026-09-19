import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHeading from "@/components/PageHeading";
import release from "@/data/return-atlas-release.json";

export const dynamic = "force-static";
export const revalidate = false;
export const metadata: Metadata = {
  title: "Return Atlas data & photo credits",
  description: "Historical data and player photograph attribution for Il Margine’s Return Atlas.",
  alternates: { canonical: "https://ilmargine.bet/return-atlas/credits" },
};

export default function CreditsPage() {
  return <div className="min-h-screen bg-[#0f1117] text-slate-100"><main className="site-container">
    <PageHeading eyebrow="Return Atlas" title="Data & photo credits"><p>Attribution for historical records and player photography.</p></PageHeading>
    <Link href="/return-atlas" prefetch={false} className="inline-flex min-h-11 items-center text-emerald-300">← Back to player records</Link>
    <article className="max-w-4xl space-y-6 text-slate-300 [&_h2]:mb-3 [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-white [&_p]:mb-4 [&_p]:leading-7 [&_a]:text-emerald-300 [&_li]:border-t [&_li]:border-slate-800 [&_ul]:list-none" dangerouslySetInnerHTML={{ __html: release.creditsHtml }} />
  </main><Footer /></div>;
}
