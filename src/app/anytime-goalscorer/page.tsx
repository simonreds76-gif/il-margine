"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
export default function AnytimeGoalscorer() {

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Nav */}
            {/* Navigation is now in GlobalNav component in layout.tsx */}


      {/* Hero */}
      <section className="pt-6 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-4">
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">Home</Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-emerald-400">Anytime Goalscorer</span>
          </div>
          
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4 sm:mb-6">Anytime Goalscorer Betting Tips</h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-3xl leading-relaxed">
            Anytime goalscorer betting tips with analytical breakdowns based on roles, xG data and match context.
          </p>
        </div>
      </section>

      {/* Coming Soon */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-12 text-center">
            <p className="text-slate-400 text-lg">Coming soon. Check back for anytime goalscorer betting tips.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
