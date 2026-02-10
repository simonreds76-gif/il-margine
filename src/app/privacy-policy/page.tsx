import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";

export default function PrivacyPolicy() {
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
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-8">Privacy Policy</h1>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300 space-y-4 text-sm leading-relaxed">
            <p>
              This policy describes how we handle your information when you use ilmargine.bet (and related domains).
            </p>
            <p>
              <strong className="text-slate-200">Information we collect.</strong> When you visit the site we may log
              technical data such as IP address, browser type and pages viewed. We use Google Analytics only if you
              accept our cookie banner; that involves cookies and similar technologies. See our{" "}
              <Link href="/cookies-policy" className="text-emerald-400 hover:text-emerald-300 underline">
                Cookies policy
              </Link>{" "}
              for details.
            </p>
            <p>
              <strong className="text-slate-200">How we use it.</strong> We use this to run and improve the site, and
              to comply with the law. We do not sell your data.
            </p>
            <p>
              <strong className="text-slate-200">Cookies.</strong> We use essential and, with your consent, analytics
              cookies. You can accept or find out more via the cookie notice on the site.
            </p>
            <p>
              <strong className="text-slate-200">Your rights.</strong> Under UK GDPR you have rights including access,
              correction, deletion and the right to withdraw consent. To exercise them or ask questions, contact us at{" "}
              <a href="mailto:contact@ilmargine.bet" className="text-emerald-400 hover:text-emerald-300 underline">
                contact@ilmargine.bet
              </a>.
            </p>
            <p>
              <strong className="text-slate-200">Changes.</strong> We may update this policy; the latest version will
              be on this page.
            </p>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
