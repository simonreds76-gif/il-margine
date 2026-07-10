import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { RESOURCES, RESOURCE_CATEGORIES, type ResourceCategory } from "@/lib/resources";
import { CLUB_PENALTY_SEASON } from "@/lib/club-penalty-takers";

type PageProps = {
  searchParams?: Promise<{
    category?: string | string[];
  }>;
};

function getSelectedCategory(category?: string | string[]): ResourceCategory | "" {
  const value = Array.isArray(category) ? category[0] : category;
  return RESOURCE_CATEGORIES.includes(value as ResourceCategory) ? (value as ResourceCategory) : "";
}

function categoryHref(category: ResourceCategory | ""): string {
  return category ? `/resources?category=${encodeURIComponent(category)}` : "/resources";
}

function categoryClasses(category: ResourceCategory | "", selected: ResourceCategory | ""): string {
  const isActive = category === selected;
  return [
    "rounded-full border px-3 py-1.5 text-xs font-mono uppercase tracking-[0.16em] transition",
    isActive
      ? "border-emerald-400/45 bg-emerald-400/12 text-emerald-200"
      : "border-slate-800 bg-slate-900/55 text-slate-400 hover:border-slate-600 hover:text-slate-200",
  ].join(" ");
}

function formatResourceDate(datePublished?: string): string | null {
  if (!datePublished) return null;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${datePublished}T12:00:00Z`));
}

export default async function ResourcesPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const categoryFilter = getSelectedCategory(params?.category);
  const filteredResources = categoryFilter === "" ? RESOURCES : RESOURCES.filter((resource) => resource.category === categoryFilter);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="border-b border-slate-800/50 pt-6 pb-12 md:pt-6 md:pb-16">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <PageHomeLink className="mb-8" />
          <span className="mb-3 block font-mono text-xs tracking-wider text-emerald-400">
            RESOURCES
          </span>
          <h1 className="mb-4 text-3xl font-semibold text-slate-100 sm:text-4xl">
            Betting Resources, Tools & Guides
          </h1>
          <p className="max-w-2xl text-base leading-relaxed text-slate-300 sm:text-lg">
            Strategy pieces, calculators and reference pages for value, staking,
            bankroll management and the mechanics behind profitable betting.
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 md:py-16 lg:px-8">
        <nav aria-label="Resource categories" className="mb-8 flex flex-wrap gap-2 md:mb-10">
          <Link href={categoryHref("")} className={categoryClasses("", categoryFilter)}>
            All categories
          </Link>
          {RESOURCE_CATEGORIES.map((category) => (
            <Link key={category} href={categoryHref(category)} className={categoryClasses(category, categoryFilter)}>
              {category}
            </Link>
          ))}
        </nav>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filteredResources.map((resource) => {
            const dateLabel = formatResourceDate(resource.datePublished);
            return (
              <Link
                key={resource.href}
                href={resource.href}
                className="group flex h-full flex-col rounded-lg border border-slate-800 bg-slate-900/50 p-6 transition-colors hover:border-emerald-500/30"
              >
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="inline-block rounded bg-emerald-500/10 px-2 py-1 font-mono text-xs text-emerald-400">
                    {resource.category}
                  </span>
                  {dateLabel ? (
                    <time dateTime={resource.datePublished} className="font-mono text-xs text-slate-500">
                      {dateLabel}
                    </time>
                  ) : null}
                </div>
                <h2 className="mb-2 text-xl font-semibold text-slate-100 transition-colors group-hover:text-emerald-300">
                  {resource.title}
                </h2>
                <p className="mb-4 flex-1 text-sm leading-relaxed text-slate-400">
                  {resource.excerpt ?? resource.description}
                </p>
                <div className="mt-auto flex items-center justify-between pt-2">
                  <span className="font-mono text-xs text-slate-500">
                    {resource.minRead} min read
                  </span>
                  <span className="text-sm font-medium text-emerald-400 group-hover:text-emerald-300">
                    Read article -&gt;
                  </span>
                </div>
              </Link>
            );
          })}
        </div>

        {filteredResources.length === 0 ? (
          <p className="py-12 text-center text-slate-500">
            No articles in this category yet. Check back soon.
          </p>
        ) : null}

        <section className="mt-12 rounded-2xl border border-slate-800/80 bg-slate-900/45 p-6 md:p-8">
          <div className="max-w-3xl">
            <div className="font-mono text-xs uppercase tracking-[0.18em] text-slate-400">
              Reference Boards
            </div>
            <h2 className="mt-3 text-2xl font-semibold text-slate-100">
              Live reference pages
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">
              The site also has live boards that work more like reference tools
              than educational reads.
            </p>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <Link
              href="/penalty-takers"
              className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 transition-colors hover:border-emerald-500/25"
            >
              <div className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">
                Club board
              </div>
              <h3 className="mt-3 text-xl font-semibold text-slate-100">
                Penalty Takers {CLUB_PENALTY_SEASON}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                First, second and third-choice takers for every club across the top five leagues,
                with individual club pages for team-specific searches.
              </p>
              <div className="mt-4 text-sm font-medium text-emerald-400">
                Open club board -&gt;
              </div>
            </Link>

            <Link
              href="/penalty-takers/world-cup-2026"
              className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 transition-colors hover:border-emerald-500/25"
            >
              <div className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">
                Tournament board
              </div>
              <h3 className="mt-3 text-xl font-semibold text-slate-100">
                World Cup 2026 Penalty Takers
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                Country-by-country hierarchy pages for the tournament with one page per nation.
              </p>
              <div className="mt-4 text-sm font-medium text-emerald-400">
                Open World Cup board -&gt;
              </div>
            </Link>
          </div>
        </section>
      </div>

      <Footer />
    </div>
  );
}
