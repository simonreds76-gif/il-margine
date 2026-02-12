import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Resources | Il Margine",
  description:
    "Betting strategy guides, bankroll management, and educational resources from Il Margine.",
  alternates: {
    canonical: `${BASE_URL}/resources`,
  },
  robots: "index, follow",
};

const RESOURCES = [
  {
    href: "/resources/kelly-criterion-sports-betting",
    title: "The Kelly Criterion for Sports Betting",
    description:
      "Master optimal bet sizing. Learn the mathematics, fractional Kelly strategies, and how to apply it to player props and tennis betting.",
  },
];

export default function ResourcesPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-6 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8"
          >
            <Image
              src="/favicon.png"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 object-contain shrink-0"
            />
            <span>← Home</span>
          </Link>
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">
            BETTING EDUCATION
          </span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4">
            Resources
          </h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed">
            Strategy guides and educational content to improve your betting
            discipline and bankroll management.
          </p>
        </div>
      </section>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
        <div className="grid gap-6">
          {RESOURCES.map((resource) => (
            <Link
              key={resource.href}
              href={resource.href}
              className="block p-6 bg-slate-900/50 border border-slate-800 rounded-lg hover:border-emerald-500/30 transition-colors"
            >
              <h2 className="text-xl font-semibold text-slate-100 mb-2">
                {resource.title}
              </h2>
              <p className="text-slate-400">{resource.description}</p>
            </Link>
          ))}
        </div>
      </div>

      <Footer />
    </div>
  );
}
