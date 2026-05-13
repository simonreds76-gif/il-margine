import type { ReactNode } from "react";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";

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
  const schema = {
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
    mainEntityOfPage: `${BASE_URL}${canonicalPath}`,
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <section className="border-b border-slate-800/50 pt-6 pb-8 md:pt-6 md:pb-10">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <PageHomeLink className="mb-6" />
          <nav className="mb-6 flex items-center gap-2 text-sm text-slate-500">
            <Link href="/" className="hover:text-slate-300">
              Home
            </Link>
            <span>/</span>
            <Link href="/resources" className="hover:text-slate-300">
              Resources
            </Link>
            <span>/</span>
            <span className="text-slate-300">{title}</span>
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
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 md:py-16 lg:px-8">
        <div className="lg:grid lg:grid-cols-[240px_1fr] lg:gap-16">
          <aside className="mb-10 lg:sticky lg:top-24 lg:mb-0 lg:self-start">
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-5">
              <h3 className="mb-4 font-mono text-xs uppercase tracking-wider text-slate-500">
                Contents
              </h3>
              <nav className="space-y-2">
                {toc.map((item, index) => (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    className="block text-sm text-slate-400 transition-colors hover:text-emerald-400"
                  >
                    {index + 1}. {item.label}
                  </a>
                ))}
              </nav>
            </div>
          </aside>

          <article className="space-y-6 text-base leading-relaxed text-slate-300">
            {children}
          </article>
        </div>
      </div>

      <Footer />
    </div>
  );
}
