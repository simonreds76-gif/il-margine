"use client";

import { useEffect } from "react";
import Link from "next/link";
import Footer from "@/components/Footer";
import { useChatContext } from "@/contexts/ChatContext";

const SUGGESTED = [
  "CPI of Miami in 2024?",
  "How do underdogs do at Indian Wells?",
  "Sinner's record vs left-handed players?",
  "Who's won Indian Wells the most?",
  "Dimitrov's record at Monte Carlo?",
];

export default function RogerPage() {
  const ctx = useChatContext();
  const openChat = ctx?.openChat;
  const openChatWithMessage = ctx?.openChatWithMessage;

  useEffect(() => {
    openChat?.();
  }, [openChat]);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-6 pb-12 md:pt-8 md:pb-16 border-b border-slate-800/50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link
            href="/resources"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8"
          >
            <span>← Resources</span>
          </Link>
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">
            TENNIS STATS CHATBOT · VERSION 1.0
          </span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4">
            Meet Roger
          </h1>
          <p className="text-lg text-slate-300 leading-relaxed mb-4">
            Roger is our tennis stats chatbot, named in honour of Roger Federer. Ask about ATP head to head records, tournament history, serve stats, player records at venues, and more. Anything relevant to tennis to enhance your betting.
          </p>
          <p className="text-sm text-slate-500 leading-relaxed mb-2">
            Limits may apply during peak usage.
          </p>
          <p className="text-sm text-slate-500 leading-relaxed mb-6">
            Player records and head-to-head use full ATP history. Fav/dog ROI and betting stats are based on the last four years.
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => openChat?.()}
              className="inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
            >
              Open Roger
            </button>
            <Link
              href="/tennis-tips"
              className="inline-flex items-center gap-2 border border-slate-600 hover:border-slate-400 text-slate-200 font-medium px-6 py-3 rounded-lg transition-colors"
            >
              View Tennis Tips
            </Link>
          </div>
        </div>
      </section>

      <section className="py-12 md:py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl font-semibold text-slate-100 mb-4">What you can ask</h2>
          <ul className="space-y-2 text-slate-300">
            <li>• Head-to-head records between any ATP players</li>
            <li>• Player records at specific tournaments (Indian Wells, Roland Garros, etc.)</li>
            <li>• Court pace (CPI) by tournament and year</li>
            <li>• Serve and return stats by surface</li>
            <li>• Record vs left-handed players or big servers</li>
            <li>• Tournament winners, seeds, qualifiers, and recent form</li>
            <li>• How favourites or underdogs do at a tournament (ROI, last 4 years)</li>
          </ul>
          <p className="text-sm text-slate-500 mt-4">
            Any tips or views from Roger are based solely on our stats and data. Roger doesn&apos;t speculate beyond what the numbers show.
          </p>

          <h2 className="text-xl font-semibold text-slate-100 mt-10 mb-4">Try asking (click to get an answer)</h2>
          <div className="space-y-2">
            {SUGGESTED.map((q) => (
              <button
                key={q}
                onClick={() => openChatWithMessage?.(q)}
                className="block w-full text-left text-sm px-4 py-3 rounded-lg border border-slate-800/60 text-slate-300 hover:bg-slate-800/40 hover:border-emerald-500/30 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>

          <p className="text-sm text-slate-500 mt-10">
            Roger v1.0. We&apos;re iterating. Feedback, improvements, or bug reports?{" "}
            <Link href="/contact" className="text-emerald-400 hover:text-emerald-300 underline">
              Contact us
            </Link>
            .
          </p>
        </div>
      </section>

      <Footer />
    </div>
  );
}
