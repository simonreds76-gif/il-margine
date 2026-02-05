import Link from "next/link";

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link href="/" className="text-sm text-slate-500 hover:text-slate-300 mb-6 inline-block">
            ← Home
          </Link>
          <h1 className="text-3xl font-bold mb-8">Privacy Policy</h1>
          <div className="prose prose-invert prose-slate max-w-none text-slate-300 space-y-4 text-sm leading-relaxed">
            <p>
              This policy describes how we handle your information when you use il-margine.bet (and related domains).
            </p>
            <p>
              <strong className="text-slate-200">Information we collect.</strong> When you visit the site we may log
              technical data such as IP address, browser type and pages viewed. If we add analytics (e.g. Google
              Analytics), that will involve cookies and similar technologies; we will update this page and provide a
              simple way to accept or manage preferences.
            </p>
            <p>
              <strong className="text-slate-200">How we use it.</strong> We use this to run and improve the site, and
              to comply with the law. We do not sell your data.
            </p>
            <p>
              <strong className="text-slate-200">Cookies.</strong> We may use essential and analytics cookies. When
              analytics are enabled, we will add a short notice and a link to this policy so you can accept or find out
              more.
            </p>
            <p>
              <strong className="text-slate-200">Your rights.</strong> Under UK GDPR you have rights including access,
              correction and deletion. To exercise them or ask questions, contact us (e.g. via the contact method
              stated on the site).
            </p>
            <p>
              <strong className="text-slate-200">Changes.</strong> We may update this policy; the latest version will
              be on this page.
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
