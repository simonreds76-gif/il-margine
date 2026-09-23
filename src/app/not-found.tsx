import Link from "next/link";
import EditorialIcon from "@/components/EditorialIcon";

export default function NotFound() {
  return <main className="site-container site-section min-h-[60vh]">
    <EditorialIcon name="method" className="mb-6 h-16 w-16" />
    <p className="site-eyebrow">Page not found · 404</p>
    <h1 className="mt-3 text-3xl font-semibold">Let&apos;s get you back to the research.</h1>
    <p className="mt-4 max-w-xl text-slate-300">This address may have changed. Browse the current selections or return to the homepage.</p>
    <div className="mt-6 flex flex-wrap gap-5"><Link href="/" className="site-text-link">Back to Il Margine →</Link><Link href="/tennis-tips" className="site-text-link">Tennis tips →</Link><Link href="/player-props" className="site-text-link">Football player props →</Link></div>
  </main>;
}
