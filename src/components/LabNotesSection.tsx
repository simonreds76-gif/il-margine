"use client";

import Link from "next/link";
import type { Resource } from "@/lib/resources";

function formatLabNoteDate(datePublished?: string) {
  if (!datePublished) {
    return "Latest";
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${datePublished}T12:00:00Z`));
}

function LabNoteCard({ note }: { note: Resource }) {
  return (
    <Link
      href={note.href}
      className="group block h-full rounded-xl border border-slate-800/60 bg-[#0c0f14] p-5 transition-colors hover:border-emerald-500/30 hover:bg-slate-900/60"
    >
      <div className="flex flex-wrap items-center gap-3">
        <time dateTime={note.datePublished} className="font-mono text-xs text-slate-400">
          {formatLabNoteDate(note.datePublished)}
        </time>
        <span className="rounded-full border border-slate-600/60 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.16em] text-slate-300">
          {note.tag ?? note.category}
        </span>
      </div>
      <h3 className="mt-3 text-lg font-semibold leading-snug text-slate-100 transition-colors group-hover:text-emerald-300">
        {note.title}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-400 transition-colors group-hover:text-slate-300">
        {note.excerpt ?? note.description}
      </p>
    </Link>
  );
}

export default function LabNotesSection({
  notes,
  currentlyWatching,
}: {
  notes: Resource[];
  currentlyWatching?: string | null;
}) {
  if (notes.length === 0) {
    return null;
  }

  return (
    <section className="border-b border-slate-800/30 py-16 md:py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <span className="mb-2 block font-mono text-xs font-bold uppercase tracking-[0.18em] text-emerald-400/95">
          From the lab
        </span>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Lab Notes</h2>
          <Link href="/resources" className="text-sm font-medium text-emerald-300/90 transition-colors hover:text-emerald-200">
            All notes -&gt;
          </Link>
        </div>
        {currentlyWatching ? (
          <p className="mt-4 text-sm leading-relaxed text-slate-400">
            <span className="mr-2 font-mono text-xs uppercase tracking-wider text-emerald-300/90">
              Currently watching:
            </span>
            <span className="italic">{currentlyWatching}</span>
          </p>
        ) : null}
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {notes.map((note) => (
            <LabNoteCard key={note.href} note={note} />
          ))}
        </div>
      </div>
    </section>
  );
}
