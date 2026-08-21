import type { ReactNode } from "react";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import ResourceContentsNav from "@/components/ResourceContentsNav";
import { BASE_URL } from "@/lib/config";
import { RESOURCES } from "@/lib/resources";

type TocItem = {
  id: string;
  label: string;
};

type ResourceArticlePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  canonicalPath: string;
  datePublished: string;
  dateModified?: string;
  toc: TocItem[];
  children: ReactNode;
};

export default function ResourceArticlePage({
  eyebrow,
  title,
  description,
  canonicalPath,
  datePublished,
  dateModified,
  toc,
  children,
}: ResourceArticlePageProps) {
  const articleSchema = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: title,
    description,
    datePublished,
    dateModified: dateModified ?? datePublished,
    author: {
      "@type": "Organization",
      name: "Il Margine",
    },
    publisher: {
      "@type": "Organization",
      name: "Il Margine",
      logo: {
        "@type": "ImageObject",
        url: `${BASE_URL}/logo.png`,
      },
    },
    image: `${BASE_URL}/og-social-20260629.png`,
    mainEntityOfPage: `${BASE_URL}${canonicalPath}`,
  };
  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: BASE_URL,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "Resources",
        item: `${BASE_URL}/resources`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: title,
        item: `${BASE_URL}${canonicalPath}`,
      },
    ],
  };
  const currentResource = RESOURCES.find((resource) => resource.href === canonicalPath);
  const relatedResources = RESOURCES.filter(
    (resource) =>
      resource.href !== canonicalPath &&
      resource.href.startsWith("/resources/") &&
      (resource.tag === currentResource?.tag || resource.category === currentResource?.category),
  )
    .sort((left, right) => Number(right.featured) - Number(left.featured))
    .slice(0, 3);
  const formatDate = (value: string) =>
    new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date(`${value}T12:00:00Z`));

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify([articleSchema, breadcrumbSchema]) }}
      />

      <section className="border-b border-slate-800/50 pt-6 pb-8 md:pt-6 md:pb-10">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <PageHomeLink className="mb-6" />
          <nav aria-label="Breadcrumb" className="mb-6 flex items-center gap-2 text-sm text-slate-500">
            <Link href="/" className="hover:text-slate-300">
              Home
            </Link>
            <span>/</span>
            <Link href="/resources" className="hover:text-slate-300">
              Resources
            </Link>
            <span aria-hidden="true">/</span>
            <span aria-current="page" className="truncate text-slate-300 sm:max-w-xl">
              {title}
            </span>
          </nav>
          <span className="mb-2 block font-mono text-xs uppercase tracking-wider text-emerald-400">
            {eyebrow}
          </span>
          <h1 className="mb-4 max-w-4xl text-3xl font-semibold text-slate-100 sm:text-4xl">
            {title}
          </h1>
          <p className="max-w-3xl text-base leading-relaxed text-slate-300 sm:text-lg">
            {description}
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">
            <time dateTime={dateModified ?? datePublished}>
              Updated {formatDate(dateModified ?? datePublished)}
            </time>
            {currentResource ? <span>{currentResource.minRead} min read</span> : null}
            <span>Written by Il Margine</span>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 md:py-16 lg:px-8">
        <div className="lg:grid lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-14">
          <ResourceContentsNav items={toc} />

          <article className="min-w-0 space-y-6 text-base leading-7 text-slate-300 sm:text-[17px] sm:leading-8">
            {children}

            {relatedResources.length > 0 ? (
              <section className="mt-14 border-t border-slate-800 pt-8" aria-labelledby="related-guides">
                <div className="mb-5 flex items-end justify-between gap-4">
                  <div>
                    <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-400">
                      Continue reading
                    </div>
                    <h2 id="related-guides" className="mt-2 text-2xl font-semibold text-slate-100">
                      Related betting guides
                    </h2>
                  </div>
                  <Link href="/resources" className="hidden text-sm text-slate-400 hover:text-emerald-300 sm:block">
                    All resources -&gt;
                  </Link>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {relatedResources.map((resource) => (
                    <Link
                      key={resource.href}
                      href={resource.href}
                      className="rounded-xl border border-slate-800 bg-slate-900/45 p-4 transition hover:border-emerald-500/35 hover:bg-slate-900/70"
                    >
                      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-400">
                        {resource.category}
                      </div>
                      <h3 className="mt-2 text-base font-semibold leading-snug text-slate-100">
                        {resource.title}
                      </h3>
                    </Link>
                  ))}
                </div>
              </section>
            ) : null}
          </article>
        </div>
      </div>

      <Footer />
    </div>
  );
}
