import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";

import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";

const PAGE_URL = `${BASE_URL}/fair-odds-lab/world-cup`;

type WorldCupLabArtifact = {
  generated_at?: string | null;
  model_status?: string;
  fair_odds_status?: string;
  public_signal_status?: string;
  public_record?: string;
  settlement?: string;
  signals?: unknown[];
};

export const revalidate = 300;

export const metadata: Metadata = {
  title: "World Cup 2026 Goalscorer Research Lab | Il Margine",
  description:
    "Untracked World Cup 2026 goalscorer research lab. This national-team lane is separate from the validated club Fair Odds Lab.",
  alternates: {
    canonical: PAGE_URL,
  },
  robots: {
    index: false,
    follow: false,
  },
  openGraph: {
    type: "website",
    url: PAGE_URL,
    title: "World Cup 2026 Goalscorer Research Lab | Il Margine",
    description:
      "Research-only World Cup 2026 goalscorer leans. Not part of the Il Margine tracked record.",
    images: [{ url: `${BASE_URL}/og.png`, width: 1200, height: 630, alt: "Il Margine World Cup research lab" }],
  },
};

function readWorldCupLabArtifact(): WorldCupLabArtifact {
  const artifactPath = path.join(process.cwd(), "public", "fair-odds-lab", "world-cup", "signals.json");
  if (!fs.existsSync(artifactPath)) {
    return {
      generated_at: null,
      model_status: "NOT_VALIDATED",
      fair_odds_status: "NOT_AUTHORISED",
      public_signal_status: "DISABLED",
      public_record: "EXCLUDED",
      settlement: "internal",
      signals: [],
    };
  }

  try {
    return JSON.parse(fs.readFileSync(artifactPath, "utf8")) as WorldCupLabArtifact;
  } catch {
    return {
      generated_at: null,
      model_status: "ARTIFACT_PARSE_FAILED",
      fair_odds_status: "NOT_AUTHORISED",
      public_signal_status: "DISABLED",
      public_record: "EXCLUDED",
      settlement: "internal",
      signals: [],
    };
  }
}

function statusLabel(value: string | undefined, fallback: string) {
  return (value || fallback).replaceAll("_", " ");
}

export default function WorldCupFairOddsLabPage() {
  const artifact = readWorldCupLabArtifact();
  const signalsCount = Array.isArray(artifact.signals) ? artifact.signals.length : 0;

  return (
    <div className="min-h-screen bg-[#07110f] text-slate-100">
      <main className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(87,209,150,0.18),transparent_32%),linear-gradient(135deg,rgba(15,23,42,0.92),rgba(2,6,23,0.98))]" />
        <div className="relative mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <PageHomeLink />
            <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-mono uppercase tracking-[0.18em] text-emerald-200">
              Research only
            </span>
            <span className="rounded-full border border-amber-300/30 bg-amber-300/10 px-3 py-1 text-xs font-mono uppercase tracking-[0.18em] text-amber-100">
              Noindex
            </span>
          </div>

          <section className="rounded-[2rem] border border-emerald-400/20 bg-slate-950/70 p-6 shadow-[0_24px_90px_rgba(0,0,0,0.35)] sm:p-9">
            <p className="mb-4 text-xs font-mono uppercase tracking-[0.28em] text-emerald-300">
              World Cup 2026
            </p>
            <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-white sm:text-6xl">
              Goalscorer research lab, separated from the club model.
            </h1>
            <p className="mt-5 max-w-4xl text-base leading-7 text-slate-300 sm:text-lg">
              World Cup 2026 research lab. Untracked. Il Margine has no validated national-team goalscorer
              model yet. The picks below are research leans drawn from our club model, the World Cup penalty
              hierarchy, and confirmed lineups. They are not part of the Il Margine tracked record.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["model_status", statusLabel(artifact.model_status, "NOT_VALIDATED")],
                ["fair_odds_status", statusLabel(artifact.fair_odds_status, "NOT_AUTHORISED")],
                ["public_record", statusLabel(artifact.public_record, "EXCLUDED")],
                ["settlement", statusLabel(artifact.settlement, "internal")],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
                  <div className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500">{label}</div>
                  <div className="mt-2 text-sm font-semibold uppercase tracking-[0.12em] text-emerald-200">
                    {value}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="mt-6 grid gap-4 lg:grid-cols-[1.35fr_0.65fr]">
            <div className="rounded-[1.5rem] border border-slate-800 bg-slate-950/70 p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-mono uppercase tracking-[0.2em] text-slate-500">Current research rows</p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">{signalsCount} signals</h2>
                </div>
                <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-mono uppercase tracking-[0.16em] text-slate-300">
                  Generated: {artifact.generated_at || "not started"}
                </span>
              </div>

              <div className="mt-6 rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-6">
                <p className="text-lg font-semibold text-slate-100">No World Cup goalscorer rows are authorised yet.</p>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                  This page is intentionally empty until the Phase 0 data foundation is complete: team-strength tiers,
                  penalty hierarchy freshness, confirmed lineups, and append-only shadow settlement. That keeps the
                  validated club Fair Odds Lab clean.
                </p>
              </div>
            </div>

            <aside className="rounded-[1.5rem] border border-emerald-400/20 bg-emerald-950/10 p-6">
              <p className="text-xs font-mono uppercase tracking-[0.2em] text-emerald-300">Guard rails</p>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
                <li>No presumed-XI row can be public.</li>
                <li>Penalty-dependent rows need fresh hierarchy evidence.</li>
                <li>WC samples never merge with the club Fair Odds Lab record.</li>
                <li>X posts must say research lean and untracked.</li>
              </ul>
              <div className="mt-6 flex flex-col gap-3">
                <Link
                  href="/player-props/world-cup-2026"
                  className="rounded-full bg-emerald-400 px-4 py-2 text-center text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
                >
                  World Cup props hub
                </Link>
                <Link
                  href="/penalty-takers/world-cup-2026"
                  className="rounded-full border border-slate-700 px-4 py-2 text-center text-sm font-semibold text-slate-200 transition hover:border-emerald-400/60 hover:text-emerald-200"
                >
                  Penalty hierarchy
                </Link>
              </div>
            </aside>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
