import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import PremiumProofStats from "@/components/PremiumProofStats";
import { BASE_URL } from "@/lib/config";
import { isExternalPremiumHref, premiumJoinHref } from "@/lib/premium";

const url = `${BASE_URL}/premium`;

export const metadata: Metadata = {
  title: "Il Margine Premium | Football Props and ATP Tennis Picks",
  description:
    "Founding access for Il Margine Premium: football player props and ATP tennis value picks backed by a public, stake-weighted track record.",
  alternates: { canonical: url },
  robots: "index, follow",
  openGraph: {
    type: "website",
    locale: "en_GB",
    siteName: "Il Margine",
    url,
    title: "Il Margine Premium - Player Props and ATP Tennis Value Picks",
    description:
      "A tracked football props and ATP tennis value service built around public records, model-led pricing, and unit-stake discipline.",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine Premium" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Il Margine Premium - Player Props and ATP Tennis Value Picks",
    description:
      "A tracked football props and ATP tennis value service built around public records, model-led pricing, and unit-stake discipline.",
    images: ["/og.png"],
  },
};

type PricingPlan = {
  name: string;
  price: string;
  cadence: string;
  body: string;
  features: string[];
  featured?: boolean;
};

const pricing: PricingPlan[] = [
  {
    name: "Free sample",
    price: "Free",
    cadence: "public preview",
    body: "A limited look at the process: selected free picks, weekly record recap, and public proof links.",
    features: ["1-2 public picks per week", "Weekly record recap", "Public track-record access"],
  },
  {
    name: "Founding monthly",
    price: "$19",
    cadence: "per month",
    body: "The launch offer for early members while the premium feed builds reviews and platform proof.",
    features: ["Full premium pick feed", "Football player props", "ATP tennis selections", "Stake guidance in units"],
    featured: true,
  },
  {
    name: "Weekly pass",
    price: "$9",
    cadence: "per week",
    body: "Low-friction access for bettors who want to test the feed before committing monthly.",
    features: ["7 days of premium picks", "Good for trial weeks", "Cancel before renewal"],
  },
];

const proofPillars = [
  "Public site ledger",
  "Pre-result timestamps",
  "Settlement audit trail",
  "No edited history",
] as const;

const platformChecklist = [
  ["Whop", "Launch first", "Immediate checkout, marketplace exposure, affiliate/referral growth."],
  ["DubClub", "Apply same day", "Sports-betting-native delivery and Play of the Day trials."],
  ["Winible", "Apply same day", "Alternative capper platform with SMS/email/app delivery."],
  ["SharpDuel", "Create listing", "Extra marketplace exposure under soccer, player props and tennis."],
  ["CapperTek", "Create profile", "Long-tail proof/listing surface with documented pick history."],
] as const;

function JoinButton({ className = "" }: { className?: string }) {
  const href = premiumJoinHref();
  const external = isExternalPremiumHref(href);
  return (
    <a
      href={href}
      target={external && !href.startsWith("mailto:") ? "_blank" : undefined}
      rel={external && !href.startsWith("mailto:") ? "noopener noreferrer" : undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-500 px-6 py-3 text-sm font-bold text-white transition-all hover:bg-emerald-400 hover:shadow-[0_0_40px_rgba(16,185,129,0.18)] ${className}`.trim()}
    >
      Join founding access <span aria-hidden="true">&rarr;</span>
    </a>
  );
}

export default function PremiumPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="relative overflow-hidden border-b border-slate-800/40 pt-6 pb-16 md:pb-20">
        <div
          className="pointer-events-none absolute inset-x-0 -top-28 h-[620px]"
          style={{ background: "radial-gradient(ellipse 1100px 520px at 50% -110px, rgba(16,185,129,0.1), transparent)" }}
        />
        <div className="pointer-events-none absolute -right-32 top-4 h-96 w-96 rounded-full bg-emerald-500/[0.035] blur-[110px]" />

        <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <PageHomeLink className="mb-10" />
          <div className="grid gap-10 lg:grid-cols-[1.05fr,0.95fr] lg:items-center">
            <div>
              <span className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
                Premium founding access
              </span>
              <h1 className="mt-5 max-w-4xl text-4xl font-semibold leading-[0.98] tracking-tight text-white sm:text-5xl md:text-6xl">
                Football props and ATP tennis value picks. Tracked in public.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-relaxed text-slate-300 sm:text-lg">
                Il Margine Premium is the paid feed for bettors who want every public-quality selection: football player props, ATP tennis spots, and model-led value signals with unit staking and a visible record.
              </p>
              <div className="mt-7 flex flex-wrap gap-2 text-[11px] font-mono font-semibold uppercase tracking-[0.12em] text-slate-400">
                {proofPillars.map((item) => (
                  <span key={item} className="rounded-full border border-slate-700/50 bg-[#0c0f14] px-3 py-2">
                    {item}
                  </span>
                ))}
              </div>
              <div className="mt-8 flex flex-wrap gap-3">
                <JoinButton />
                <Link
                  href="/track-record"
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700/70 bg-[#0c0f14] px-6 py-3 text-sm font-semibold text-slate-200 transition-colors hover:border-emerald-500/35 hover:text-emerald-300"
                >
                  Inspect track record <span aria-hidden="true">&rarr;</span>
                </Link>
                <Link
                  href="/calculator"
                  className="inline-flex items-center justify-center gap-2 rounded-xl px-2 py-3 text-sm font-medium text-slate-500 transition-colors hover:text-emerald-400"
                >
                  Returns calculator <span aria-hidden="true">&rarr;</span>
                </Link>
              </div>
              <p className="mt-4 max-w-xl text-xs leading-relaxed text-slate-600">
                Betting involves risk. Past performance does not guarantee future results. Il Margine provides research and analysis only; we do not operate a sportsbook or take wagers.
              </p>
            </div>

            <div className="rounded-3xl border border-emerald-500/15 bg-[#0a0d12] p-5 shadow-2xl shadow-black/30 md:p-6">
              <div className="mb-4 text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-emerald-400/90">
                Live proof panel
              </div>
              <PremiumProofStats />
            </div>
          </div>
        </div>
      </section>

      <section id="founding-access" className="border-b border-slate-800/30 py-16 md:py-20 scroll-mt-24">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 max-w-2xl">
            <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
              Pricing
            </span>
            <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Simple founding offer</h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-500">
              The launch price is intentionally low to build reviews, screenshots, and marketplace traction. Once social proof exists, the monthly plan moves toward the normal price.
            </p>
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            {pricing.map((plan) => (
              <div
                key={plan.name}
                className={`relative overflow-hidden rounded-2xl border p-6 ${
                  plan.featured
                    ? "border-emerald-500/35 bg-emerald-500/[0.055]"
                    : "border-slate-700/45 bg-[#0c0f14]"
                }`}
              >
                {plan.featured ? (
                  <div className="absolute right-4 top-4 rounded-full border border-emerald-400/25 bg-emerald-500/10 px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-emerald-300">
                    First 50
                  </div>
                ) : null}
                <h3 className="text-lg font-semibold text-slate-100">{plan.name}</h3>
                <div className="mt-4 flex items-end gap-2">
                  <span className="font-mono text-4xl font-black tracking-tight text-slate-100">{plan.price}</span>
                  <span className="pb-1 text-sm text-slate-500">{plan.cadence}</span>
                </div>
                <p className="mt-4 min-h-[4rem] text-sm leading-relaxed text-slate-500">{plan.body}</p>
                <ul className="mt-5 space-y-2 text-sm text-slate-300">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex gap-2">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400/80" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                {plan.featured ? <JoinButton className="mt-6 w-full" /> : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-slate-800/30 py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="grid gap-10 lg:grid-cols-[0.9fr,1.1fr]">
            <div>
              <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
                What members get
              </span>
              <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">A value feed, not a hype channel</h2>
              <p className="mt-4 text-sm leading-relaxed text-slate-500">
                The product is built around price disagreement and disciplined posting. No parlays as filler, no play-of-the-year language, no deleted losses.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                ["Football player props", "Shots, shots on target, fouls, cards and selected role-based markets when the number is wrong."],
                ["ATP tennis", "Selective moneyline, handicap and totals spots when the price beats our fair number."],
                ["Fair Odds Lab", "A model-led research layer for goalscorer value and probability gaps."],
                ["Unit staking", "Every pick includes stake size in units so followers can scale to their own bankroll."],
              ].map(([title, body]) => (
                <div key={title} className="rounded-2xl border border-slate-700/45 bg-[#0c0f14] p-5">
                  <h3 className="text-base font-semibold text-slate-200">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-500">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-slate-800/30 py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 max-w-2xl">
            <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
              Marketplace rollout
            </span>
            <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Where premium access launches</h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-500">
              The site remains the proof layer. Whop, DubClub, Winible, SharpDuel and CapperTek are the sales and discovery layers.
            </p>
          </div>
          <div className="overflow-hidden rounded-2xl border border-slate-700/45 bg-[#0c0f14]">
            {platformChecklist.map(([platform, status, reason]) => (
              <div key={platform} className="grid gap-2 border-b border-slate-800/50 px-5 py-4 last:border-b-0 md:grid-cols-[0.75fr,0.75fr,1.5fr] md:items-center">
                <div className="font-semibold text-slate-200">{platform}</div>
                <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-emerald-400">{status}</div>
                <div className="text-sm leading-relaxed text-slate-500">{reason}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="relative overflow-hidden rounded-3xl border border-emerald-500/20 bg-emerald-500/[0.055] p-6 md:p-8 lg:p-10">
            <div className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-emerald-400/[0.08] blur-[70px]" />
            <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div>
                <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-300">
                  Founding access
                </span>
                <h2 className="text-2xl font-semibold text-white sm:text-3xl">Join before the first platform price rise.</h2>
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">
                  The first sales goal is simple: get paying members, collect reviews, and prove that the public record converts into a premium business.
                </p>
              </div>
              <JoinButton className="shrink-0" />
            </div>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
