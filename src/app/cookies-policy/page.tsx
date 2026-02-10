import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Cookies Policy",
  description: "How Il Margine uses cookies. Essential cookies, and optional analytics and affiliate cookies when enabled, with consent.",
  alternates: {
    canonical: `${BASE_URL}/cookies-policy`,
  },
  robots: "index, follow",
};

export default function CookiesPolicyPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-6 pb-10 md:pt-6 md:pb-12 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8"
          >
            <Image src="/favicon.png" alt="" width={40} height={40} className="h-10 w-10 object-contain shrink-0" />
            <span>← Home</span>
          </Link>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-8">Cookies Policy</h1>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300 space-y-4 text-sm leading-relaxed">
            <p>
              This page explains how we use cookies and similar technologies on ilmargine.bet. For how we handle
              your personal data overall, see our{" "}
              <Link href="/privacy-policy" className="text-emerald-400 hover:text-emerald-300 underline">
                Privacy Policy
              </Link>.
            </p>
            <h2 className="text-lg font-semibold text-slate-200 mt-8 mb-2">What are cookies?</h2>
            <p>
              Cookies are small text files stored on your device when you visit a website. They are widely used to
              make sites work, remember preferences, or understand how visitors use the site.
            </p>
            <h2 className="text-lg font-semibold text-slate-200 mt-8 mb-2">Our use of cookies</h2>
            <p>
              We use <strong className="text-slate-200">analytics cookies</strong> (Google Analytics) only after you
              accept our cookie banner. We do not set non-essential cookies until you click &ldquo;Accept&rdquo;.
              Our site or hosting may set strictly necessary cookies (e.g. for security or preferences); we do not
              use these for tracking.
            </p>
            <p>
              If we add affiliate or other optional cookies in future, we will update this page and seek consent
              where required.
            </p>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
