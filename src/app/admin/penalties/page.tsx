import { redirect } from "next/navigation";
import { isAdminSession } from "@/lib/admin-auth";
import PenaltyReviewDesk from "./PenaltyReviewDesk";
export const dynamic = "force-dynamic";
export const metadata = {title: "Private penalty reviews", robots: {index: false, follow: false}};
export default async function PenaltyReviewsPage() {
  if (!await isAdminSession()) redirect("/admin");
  return <main className="min-h-screen bg-[#0f1117] px-4 py-8 text-slate-100"><div className="mx-auto max-w-5xl"><header className="mb-7 flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-emerald-300">Il Margine · Private</p><h1 className="mt-2 text-3xl font-bold">Penalty reviews</h1><p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">Review the evidence, keep the current order or publish your revised hierarchy. Done closes the ticket without changing any takers.</p></div><a className="rounded-xl border border-slate-600 px-4 py-3 text-sm" href="/admin">Back to Admin</a></header><PenaltyReviewDesk /></div></main>;
}
