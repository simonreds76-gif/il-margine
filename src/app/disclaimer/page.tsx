import Link from "next/link";
import Image from "next/image";

export default function Disclaimer() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="py-12 md:py-16 border-b border-slate-800/50 relative overflow-hidden">
        <div className="absolute inset-0 flex items-center justify-center opacity-[0.14] pointer-events-none">
          <Image
            src="/banner.png"
            alt=""
            width={1200}
            height={400}
            className="w-full max-w-4xl h-auto object-contain"
          />
        </div>
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
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

      <footer className="border-t border-slate-800 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <Link href="/" className="font-semibold text-sm text-slate-200 hover:text-white">
              Il Margine
            </Link>
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <Link href="/disclaimer" className="hover:text-slate-300">Disclaimer</Link>
              <Link href="/privacy-policy" className="hover:text-slate-300">Privacy Policy</Link>
              <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="hover:text-slate-300">
                Responsible Gambling
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
