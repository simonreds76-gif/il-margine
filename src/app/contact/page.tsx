import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Contact",
  description: "Get in touch with Il Margine. General enquiries and partnership or affiliate enquiries.",
  alternates: {
    canonical: `${BASE_URL}/contact`,
  },
  robots: "index, follow",
};

const LetterIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="w-full h-full text-emerald-400/80"
    aria-hidden
  >
    <rect x="2" y="4" width="20" height="16" rx="2" />
    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
  </svg>
);

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-4 pb-10 md:pt-6 md:pb-12 border-b border-slate-800/50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8"
          >
            <Image src="/favicon.png" alt="" width={40} height={40} className="h-10 w-10 object-contain shrink-0" />
            <span>← Home</span>
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-start gap-6 sm:gap-8 mb-10">
            <div className="w-16 h-16 sm:w-20 sm:h-20 shrink-0 rounded-xl bg-slate-800/60 border border-slate-700/50 flex items-center justify-center p-4">
              <LetterIcon />
            </div>
            <div>
              <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-3">Contact us</h1>
              <p className="text-slate-400 text-base leading-relaxed mb-4">
                We&apos;re happy to hear from you. Whether you have a general question about the service or are interested in working with us, drop a line to the address that best fits your enquiry. We aim to reply within a couple of working days. We don&apos;t share the details of our methodology, but we&apos;re happy to answer questions about what we offer.
              </p>
            </div>
          </div>

          <div className="space-y-8">
            <div className="rounded-xl bg-slate-800/40 border border-slate-700/50 p-5 sm:p-6">
              <h2 className="text-sm font-mono font-semibold text-emerald-400 tracking-wider mb-2">
                General enquiries
              </h2>
              <p className="text-slate-500 text-sm mb-3">
                Questions about the service, the edge, or how we work. Feedback and suggestions welcome.
              </p>
              <a
                href="mailto:contact@ilmargine.bet"
                className="text-slate-200 hover:text-emerald-400 transition-colors break-all font-medium"
              >
                contact@ilmargine.bet
              </a>
            </div>
            <div className="rounded-xl bg-slate-800/40 border border-slate-700/50 p-5 sm:p-6">
              <h2 className="text-sm font-mono font-semibold text-emerald-400 tracking-wider mb-2">
                Partnerships &amp; affiliate enquiries
              </h2>
              <p className="text-slate-500 text-sm mb-3">
                Commercial partnerships, affiliate programmes, or media requests. Use this address for anything business-related.
              </p>
              <a
                href="mailto:partners@ilmargine.bet"
                className="text-slate-200 hover:text-emerald-400 transition-colors break-all font-medium"
              >
                partners@ilmargine.bet
              </a>
            </div>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
