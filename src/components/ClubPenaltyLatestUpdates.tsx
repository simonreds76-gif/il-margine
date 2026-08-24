import Link from "next/link";
import type { ClubPenaltyNewsItem } from "@/lib/club-penalty-takers";

type Props = {
  items: ClubPenaltyNewsItem[];
  eyebrow?: string;
  title?: string;
  description?: string;
};

function ClubCrest({ item }: { item: ClubPenaltyNewsItem }) {
  return (
    <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-white/10 bg-white shadow-[0_8px_24px_rgba(0,0,0,0.2)]">
      {item.logoPath ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.logoPath} alt={`${item.team} crest`} className="h-8 w-8 object-contain" />
      ) : (
        <span className="font-mono text-[10px] font-bold text-slate-700">{item.initials}</span>
      )}
    </span>
  );
}

export default function ClubPenaltyLatestUpdates({
  items,
  eyebrow = "Live penalty evidence",
  title = "Latest penalty taker updates",
  description = "Competitive penalties reviewed by Il Margine. Each update links to the club's current hierarchy and full evidence file.",
}: Props) {
  if (!items.length) return null;

  return (
    <section id="latest-penalty-taker-updates" className="rounded-[30px] border border-emerald-400/18 bg-[linear-gradient(145deg,rgba(6,22,20,0.9),rgba(9,15,26,0.96))] p-5 shadow-[0_22px_70px_rgba(0,0,0,0.24)] sm:p-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-3xl">
          <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-emerald-400">{eyebrow}</div>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
        </div>
        <span className="w-fit rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.16em] text-emerald-100">
          {items.length} fresh {items.length === 1 ? "update" : "updates"}
        </span>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {items.map((item) => (
          <Link
            key={`${item.relativeUrl}-${item.id}`}
            href={item.relativeUrl}
            className="group relative overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-950/65 p-4 transition hover:-translate-y-0.5 hover:border-emerald-400/35 hover:bg-slate-950"
          >
            <div className="flex items-start gap-3">
              <ClubCrest item={item} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 font-mono text-[9px] uppercase tracking-[0.14em]">
                  <span className="text-emerald-300">{item.dateLabel}</span>
                  <span className="text-slate-600">/</span>
                  <span className="text-slate-400">{item.leagueLabel}</span>
                </div>
                <h3 className="mt-1.5 text-base font-semibold leading-6 text-slate-100 transition group-hover:text-emerald-200">{item.headline}</h3>
              </div>
            </div>
            {item.match ? <p className="mt-3 text-xs font-medium text-slate-300">{item.match}</p> : null}
            <p className="mt-2 text-sm leading-6 text-slate-400">{item.summary}</p>
            <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-800 pt-3 text-xs">
              <span className="truncate text-slate-500">Current first choice: <strong className="font-medium text-slate-200">{item.primary}</strong></span>
              <span className="shrink-0 font-semibold text-emerald-300">Full file -&gt;</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
