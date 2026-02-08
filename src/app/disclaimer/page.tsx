import Link from "next/link";
import Footer from "@/components/Footer";

export default function Disclaimer() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-4 pb-10 md:pt-6 md:pb-12 border-b border-slate-800/50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link href="/" className="text-sm text-slate-500 hover:text-slate-300 mb-6 inline-block">
            ← Home
          </Link>
          <h1 className="text-3xl font-bold mb-8">Disclaimer</h1>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300 space-y-4 text-sm leading-relaxed">
            <p>
              Past performance does not guarantee future results. All tips, analysis and statistics on this site are for
              information and entertainment purposes only. They do not constitute legal, financial or betting advice.
            </p>
            <p>
              You must be 18 or over to use this site and to gamble in the UK. Gambling can be addictive. Please bet
              responsibly and only within your means. If you need support, visit{" "}
              <a
                href="https://www.begambleaware.org"
                target="_blank"
                rel="noopener noreferrer"
                className="text-emerald-400 hover:text-emerald-300 underline"
              >
                BeGambleAware.org
              </a>
              .
            </p>
            <p>
              We are not responsible for any loss or damage arising from your use of the information on this site or
              from following any selections. Odds and availability are subject to change. You are solely responsible
              for your betting decisions.
            </p>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
