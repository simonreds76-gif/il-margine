import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "ATP Tennis Tips",
  description: "ATP tennis betting tips and analysis. All tennis tips are on our Tennis Tips page.",
  alternates: {
    canonical: `${BASE_URL}/tennis-tips`,
  },
  robots: "index, follow",
};

export default function ATPTennisPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-6 pb-10 md:pt-6 md:pb-12 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4">ATP Tennis Tips</h1>
          <p className="text-slate-300 mb-6">
            We’ve consolidated all tennis coverage—ATP, Challenger, and majors—on one page.
          </p>
          <Link
            href="/tennis-tips"
            className="inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-black font-semibold px-5 py-2.5 rounded-lg transition-colors"
          >
            Go to Tennis Tips →
          </Link>
        </div>
      </section>
      <Footer />
    </div>
  );
}
