import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";
import { RESOURCES, RESOURCE_CATEGORIES, type Resource, type ResourceCategory } from "@/lib/resources";
import { CLUB_PENALTY_SEASON } from "@/lib/club-penalty-takers";

type PageProps = {
  searchParams?: Promise<{ category?: string | string[] }>;
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
    "shrink-0 rounded-full border px-3 py-2 text-[11px] font-mono uppercase tracking-[0.14em] transition",
    isActive
      ? "border-emerald-400/45 bg-emerald-400/12 text-emerald-200"
      : "border-slate-800 bg-slate-900/55 text-slate-400 hover:border-slate-600 hover:text-slate-200",
  ].join(" ");
}

function formatResourceDate(datePublished?: string): string | null {
  if (!datePublished) return null;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${datePublished}T12:00:00Z`));
}

function ResourceCard({ resource, prominent = false }: { resource: Resource; prominent?: boolean }) {
  const dateLabel = formatResourceDate(resource.dateModified ?? resource.datePublished);

  return (
    <Link
      href={resource.href}
      className={[
        "group relative flex h-full overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/55 transition duration-300 hover:-translate-y-0.5 hover:border-emerald-500/35 hover:bg-slate-900/75",
        prominent ? "min-h-[310px] p-7 sm:p-8" : "p-5 sm:p-6",
      ].join(" ")}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-400/45 to-transparent opacity-0 transition group-hover:opacity-100" />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <span className="rounded-md border border-emerald-400/15 bg-emerald-400/8 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-emerald-300">
            {resource.category}
          </span>
          {dateLabel ? (
            <time dateTime={resource.dateModified ?? resource.datePublished} className="font-mono text-[10px] uppercase tracking-[0.12em] text-slate-500">
              Updated {dateLabel}
            </time>
          ) : null}
        </div>
        <h2 className={[
          "font-semibold leading-tight text-slate-100 transition-colors group-hover:text-emerald-200",
          prominent ? "max-w-xl text-2xl sm:text-3xl" : "text-xl",
        ].join(" ")}>
          {resource.title}
        </h2>
        <p className={[
          "mt-4 flex-1 leading-relaxed text-slate-400",
          prominent ? "max-w-2xl text-base" : "text-sm",
        ].join(" ")}>
          {resource.excerpt ?? resource.description}
        </p>
        <div className="mt-6 flex items-center justify-between border-t border-slate-800/80 pt-4">
          <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">
            {resource.minRead} min read
          </span>
          <span className="text-sm font-medium text-emerald-400 transition-transform group-hover:translate-x-1">
            Read guide -&gt;
          </span>
        </div>
      </div>
    </Link>
  );
}

export default async function ResourcesPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const categoryFilter = getSelectedCategory(params?.category);
  const filteredResources = categoryFilter === ""
    ? RESOURCES
    : RESOURCES.filter((resource) => resource.category === categoryFilter);
  const featuredResources = RESOURCES.filter((resource) => resource.featured);
  const browseResources = categoryFilter === ""
    ? filteredResources.filter((resource) => !resource.featured)
    : filteredResources;
  const collectionSchema = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "Sports Betting Resources & Guides",
    description:
      "Practical sports betting guides covering closing line value, Kelly staking, ROI, tennis models and fair odds.",
    url: `${BASE_URL}/resources`,
    mainEntity: {
      "@type": "ItemList",
      itemListElement: RESOURCES.map((resource, index) => ({
        "@type": "ListItem",
        position: index + 1,
        name: resource.title,
        url: `${BASE_URL}${resource.href}`,
      })),
    },
  };
  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: BASE_URL },
      { "@type": "ListItem", position: 2, name: "Resources", item: `${BASE_URL}/resources` },
    ],
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify([collectionSchema, breadcrumbSchema]) }}
      />

      <section className="relative overflow-hidden border-b border-slate-800/60">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_75%_20%,rgba(16,185,129,0.10),transparent_35%),linear-gradient(120deg,rgba(15,23,42,0.75),transparent_58%)]" />
        <div className="pointer-events-none absolute inset-y-0 right-0 hidden w-1/2 opacity-25 md:block [background-image:linear-gradient(rgba(52,211,153,0.10)_1px,transparent_1px),linear-gradient(90deg,rgba(52,211,153,0.10)_1px,transparent_1px)] [background-size:34px_34px]" />
        <div className="relative mx-auto max-w-6xl px-4 pb-10 pt-6 sm:px-6 md:pb-14 lg:px-8">
          <PageHomeLink className="mb-7" />
          <div className="grid items-end gap-8 md:grid-cols-[minmax(0,1fr)_280px]">
            <div>
              <span className="mb-3 block font-mono text-xs uppercase tracking-[0.2em] text-emerald-400">
                Il Margine knowledge base
              </span>
              <h1 className="max-w-4xl text-3xl font-semibold leading-tight text-slate-50 sm:text-4xl md:text-5xl">
                Sports betting guides, calculators and model research
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
                Learn how to judge a betting edge before risking money. Start with closing-line value,
                stake sizing and verified records, then explore the tennis and fair-odds research behind our public work.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 border-t border-slate-800 pt-5 md:grid-cols-1 md:border-l md:border-t-0 md:pl-7 md:pt-0">
              <div><div className="font-mono text-lg text-emerald-300">{RESOURCES.length}</div><div className="mt-1 text-xs text-slate-500">Guides and tools</div></div>
              <div><div className="font-mono text-lg text-emerald-300">2</div><div className="mt-1 text-xs text-slate-500">Core formulas</div></div>
              <div><div className="font-mono text-lg text-emerald-300">0</div><div className="mt-1 text-xs text-slate-500">Guaranteed outcomes</div></div>
            </div>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-6xl px-4 py-9 sm:px-6 md:py-14 lg:px-8">
        <nav aria-label="Resource categories" className="-mx-4 mb-9 overflow-x-auto px-4 pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:mx-0 sm:px-0 md:mb-12">
          <div className="flex w-max gap-2 sm:w-auto sm:flex-wrap">
            <Link href={categoryHref("")} className={categoryClasses("", categoryFilter)}>All resources</Link>
            {RESOURCE_CATEGORIES.map((category) => (
              <Link key={category} href={categoryHref(category)} className={categoryClasses(category, categoryFilter)}>{category}</Link>
            ))}
          </div>
        </nav>

        {categoryFilter === "" ? (
          <section aria-labelledby="start-here" className="mb-14">
            <div className="mb-6 flex items-end justify-between gap-4">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-emerald-400">Start here</div>
                <h2 id="start-here" className="mt-2 text-2xl font-semibold text-slate-100 sm:text-3xl">Build the right foundation</h2>
              </div>
              <p className="hidden max-w-sm text-right text-sm leading-6 text-slate-500 md:block">
                Price quality, record verification and disciplined staking are the three checks that come before any selection.
              </p>
            </div>
            <div className="grid gap-5 lg:grid-cols-2">
              {featuredResources[0] ? <ResourceCard resource={featuredResources[0]} prominent /> : null}
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-1">
                {featuredResources.slice(1).map((resource) => <ResourceCard key={resource.href} resource={resource} />)}
              </div>
            </div>
          </section>
        ) : null}

        <section aria-labelledby="resource-library">
          <div className="mb-6">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-slate-500">{categoryFilter || "Research library"}</div>
            <h2 id="resource-library" className="mt-2 text-2xl font-semibold text-slate-100 sm:text-3xl">
              {categoryFilter ? `${categoryFilter} resources` : "More guides and working notes"}
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {browseResources.map((resource) => <ResourceCard key={resource.href} resource={resource} />)}
          </div>
        </section>

        <section className="mt-14 overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/45">
          <div className="border-b border-slate-800/80 p-6 md:flex md:items-end md:justify-between md:gap-8 md:p-8">
            <div className="max-w-2xl">
              <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-emerald-400">Live reference boards</div>
              <h2 className="mt-3 text-2xl font-semibold text-slate-100 sm:text-3xl">Research that changes with teams and markets</h2>
            </div>
            <p className="mt-3 max-w-md text-sm leading-6 text-slate-400 md:mt-0 md:text-right">These are maintained data products rather than static educational articles.</p>
          </div>
          <div className="grid md:grid-cols-2">
            <Link href="/penalty-takers" className="group p-6 transition hover:bg-slate-900/70 md:border-r md:border-slate-800/80 md:p-8">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-400">Club football</div>
              <h3 className="mt-3 text-xl font-semibold text-slate-100 group-hover:text-emerald-200">Penalty Takers {CLUB_PENALTY_SEASON}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-400">First, second and third-choice takers across the top five leagues, with team-specific evidence pages.</p>
              <div className="mt-5 text-sm font-medium text-emerald-400">Open club board -&gt;</div>
            </Link>
            <Link href="/fair-odds-lab" className="group border-t border-slate-800/80 p-6 transition hover:bg-slate-900/70 md:border-t-0 md:p-8">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-400">Model prices</div>
              <h3 className="mt-3 text-xl font-semibold text-slate-100 group-hover:text-emerald-200">Goalscorer Fair Odds Lab</h3>
              <p className="mt-3 text-sm leading-6 text-slate-400">Current model prices, reference odds and visible uncertainty flags for selected goalscorer markets.</p>
              <div className="mt-5 text-sm font-medium text-emerald-400">Open Fair Odds Lab -&gt;</div>
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
