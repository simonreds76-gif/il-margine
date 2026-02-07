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

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8"
          >
            <Image src="/favicon.png" alt="" width={40} height={40} className="block rounded" unoptimized />
            <span>← Home</span>
          </Link>
          <h1 className="text-3xl font-bold mb-2">Contact us</h1>
          <p className="text-slate-400 text-sm mb-10">
            We&apos;re happy to hear from you. Use the address that best fits your enquiry.
          </p>
          <div className="space-y-8">
            <div>
              <h2 className="text-sm font-mono font-semibold text-emerald-400 tracking-wider mb-2">
                General enquiries
              </h2>
              <a
                href="mailto:contact@ilmargine.bet"
                className="text-slate-200 hover:text-emerald-400 transition-colors break-all"
              >
                contact@ilmargine.bet
              </a>
            </div>
            <div>
              <h2 className="text-sm font-mono font-semibold text-emerald-400 tracking-wider mb-2">
                Partnerships &amp; affiliate enquiries
              </h2>
              <a
                href="mailto:contact@ilmargine.bet"
                className="text-slate-200 hover:text-emerald-400 transition-colors break-all"
              >
                contact@ilmargine.bet
              </a>
            </div>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
