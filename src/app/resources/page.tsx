"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import { RESOURCES, RESOURCE_CATEGORIES, type ResourceCategory } from "@/lib/resources";

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
            RESOURCES
          </span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4">
            Betting Strategy & Educational Guides
          </h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed">
            In-depth articles on bankroll management, value identification, and the
            mathematics of profitable betting.
          </p>
        </div>
      </section>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
        {/* Category filter - visible on mobile, optional on desktop for future */}
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
              className="block p-6 bg-slate-900/50 border border-slate-800 rounded-lg hover:border-emerald-500/30 transition-colors"
            >
              <span className="inline-block text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded mb-3">
                {resource.category}
              </span>
              <h2 className="text-xl font-semibold text-slate-100 mb-2">
                {resource.title}
              </h2>
              <p className="text-slate-400 text-sm leading-relaxed mb-4">
                {resource.description}
              </p>
              <span className="text-xs text-slate-500 font-mono">
                {resource.minRead} min read
              </span>
            </Link>
          ))}
        </div>

        {filteredResources.length === 0 && (
          <p className="text-slate-500 text-center py-12">
            No articles in this category yet. Check back soon.
          </p>
        )}
      </div>

      <Footer />
    </div>
  );
}
