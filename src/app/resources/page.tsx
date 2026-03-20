"use client";

import { useState } from "react";
import Link from "next/link";
import Footer from "@/components/Footer";
import { RESOURCES, RESOURCE_CATEGORIES, type ResourceCategory } from "@/lib/resources";
import PageHomeLink from "@/components/PageHomeLink";

export default function ResourcesPage() {
  const [categoryFilter, setCategoryFilter] = useState<ResourceCategory | "">("");

  const filteredResources =
    categoryFilter === ""
      ? RESOURCES
      : RESOURCES.filter((r) => r.category === categoryFilter);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-6 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <PageHomeLink className="mb-8" />
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">
            RESOURCES
          </span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4">
            Betting Resources, Tools & Guides
          </h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed">
            Strategy pieces, calculators and reference pages for value, staking,
            bankroll management and the mechanics behind profitable betting.
          </p>
        </div>
      </section>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
        <div className="mb-8 md:mb-10">
          <label htmlFor="category-filter" className="sr-only">
            Filter by category
          </label>
          <select
            id="category-filter"
            value={categoryFilter}
            onChange={(e) =>
              setCategoryFilter((e.target.value || "") as ResourceCategory | "")
            }
            className="w-full md:w-auto min-w-[200px] bg-slate-900/50 border border-slate-700 px-4 py-2.5 rounded-lg text-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50"
          >
            <option value="">All categories</option>
            {RESOURCE_CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        {/* Article grid - 2-3 columns on desktop, single on mobile */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredResources.map((resource) => (
            <Link
              key={resource.href}
              href={resource.href}
              className="block p-6 bg-slate-900/50 border border-slate-800 rounded-lg hover:border-emerald-500/30 transition-colors group flex flex-col h-full"
            >
              <span className="inline-block text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded mb-3">
                {resource.category}
              </span>
              <h2 className="text-xl font-semibold text-slate-100 mb-2">
                {resource.title}
              </h2>
              <p className="text-slate-400 text-sm leading-relaxed mb-4 flex-1">
                {resource.description}
              </p>
              <div className="flex items-center justify-between mt-auto pt-2">
                <span className="text-xs text-slate-500 font-mono">
                  {resource.minRead} min read
                </span>
                <span className="text-sm font-medium text-emerald-400 group-hover:text-emerald-300">
                  Read article →
                </span>
              </div>
            </Link>
          ))}
        </div>

        {filteredResources.length === 0 && (
          <p className="text-slate-500 text-center py-12">
            No articles in this category yet. Check back soon.
          </p>
        )}

        <section className="mt-12 rounded-2xl border border-slate-800/80 bg-slate-900/45 p-6 md:p-8">
          <div className="max-w-3xl">
            <div className="text-xs font-mono uppercase tracking-[0.18em] text-slate-400">
              Reference Boards
            </div>
            <h2 className="mt-3 text-2xl font-semibold text-slate-100">
              Live reference pages
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">
              The site also has a couple of live boards that work more like reference tools
              than educational reads.
            </p>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <Link
              href="/penalty-takers"
              className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 transition-colors hover:border-emerald-500/25"
            >
              <div className="text-xs font-mono uppercase tracking-[0.18em] text-emerald-400">
                Club board
              </div>
              <h3 className="mt-3 text-xl font-semibold text-slate-100">
                Penalty Takers 2025/26
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                First, second and third-choice takers for every club across the top five leagues.
              </p>
              <div className="mt-4 text-sm font-medium text-emerald-400">
                Open club board →
              </div>
            </Link>

            <Link
              href="/penalty-takers/world-cup-2026"
              className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 transition-colors hover:border-emerald-500/25"
            >
              <div className="text-xs font-mono uppercase tracking-[0.18em] text-emerald-400">
                Tournament board
              </div>
              <h3 className="mt-3 text-xl font-semibold text-slate-100">
                World Cup 2026 Penalty Takers
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                Country-by-country hierarchy pages for the tournament with one page per nation.
              </p>
              <div className="mt-4 text-sm font-medium text-emerald-400">
                Open World Cup board →
              </div>
            </Link>
          </div>
        </section>
      </div>

      <Footer />
    </div>
  );
}

