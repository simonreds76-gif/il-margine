import { BookmakerLogo } from "@/components/fair-odds-lab/BookmakerLogo";

type OddsComparisonBarProps = {
  modelOdds: number;
  bookOdds: number;
  bookName: string;
  gapPp: number;
  modelProb?: number;
  marketProb?: number;
  size?: "large" | "compact";
};

function formatOdds(value: number) {
  return value.toFixed(2);
}

export function OddsComparisonBar({
  modelOdds,
  bookOdds,
  bookName,
  gapPp,
  modelProb,
  marketProb,
  size = "large",
}: OddsComparisonBarProps) {
  const compact = size === "compact";
  const ticks = [25, 50, 75];
  const modelPosition = Math.max(0, Math.min(100, modelProb ?? 100 / modelOdds));
  const marketPosition = Math.max(0, Math.min(100, marketProb ?? 100 / bookOdds));
  const gapStart = Math.min(modelPosition, marketPosition);
  const gapWidth = Math.abs(modelPosition - marketPosition);
  const positiveGap = modelPosition >= marketPosition;

  return (
    <div
      className={
        compact
          ? "overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-950/75 p-3"
          : "overflow-hidden rounded-[1.75rem] border border-emerald-300/25 bg-slate-950/70 p-4 shadow-[0_0_40px_rgba(16,185,129,0.08)] sm:p-5"
      }
    >
      <div className={`grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-end ${compact ? "gap-2" : "gap-3"}`}>
        <div className="min-w-0">
          <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
            Il Margine
          </div>
          <div
            className={
              compact
                ? "mt-1 font-mono text-xl font-black text-emerald-200 sm:text-2xl"
                : "mt-1 font-mono text-4xl font-black tracking-tight text-emerald-200 sm:text-5xl"
            }
          >
            {formatOdds(modelOdds)}
          </div>
        </div>
        <div className="relative mb-1 shrink-0 px-1 text-center">
          <div className="absolute left-1/2 top-1/2 h-10 w-px -translate-x-1/2 -translate-y-1/2 rotate-[22deg] bg-emerald-300/70 shadow-[0_0_12px_rgba(52,211,153,0.85)]" />
          <div className="relative text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
            vs
          </div>
          <div
            className={
              compact
                ? "mt-1 font-mono text-sm font-bold text-amber-300"
                : "mt-1 font-mono text-2xl font-black text-amber-300 sm:text-3xl"
            }
          >
            +{gapPp.toFixed(1)}pp
          </div>
        </div>
        <div className="min-w-0 text-right">
          <div className="flex min-w-0 items-center justify-end gap-2 text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            <span className="truncate">{compact ? "Best" : bookName}</span>
            <BookmakerLogo name={bookName} />
          </div>
          <div
            className={
              compact
                ? "mt-1 font-mono text-xl font-black text-slate-100 sm:text-2xl"
                : "mt-1 font-mono text-4xl font-black tracking-tight text-slate-100 sm:text-5xl"
            }
          >
            {formatOdds(bookOdds)}
          </div>
        </div>
      </div>

      <div className={compact ? "mt-3" : "mt-5"}>
        <div className="relative h-4 overflow-hidden rounded-full border border-slate-700/60 bg-slate-900">
          <div className="absolute inset-y-0 left-0 right-0 bg-slate-800/85" />
          <div
            className={`absolute inset-y-0 rounded-full ${
              positiveGap ? "bg-amber-300" : "bg-rose-400"
            }`}
            style={{ left: `${gapStart}%`, width: `${Math.max(2, gapWidth)}%` }}
          />
          <div
            className="absolute inset-y-[-5px] w-px bg-slate-300 shadow-[0_0_10px_rgba(203,213,225,0.45)]"
            style={{ left: `${marketPosition}%` }}
          />
          <div
            className="absolute inset-y-[-5px] w-px bg-emerald-200 shadow-[0_0_14px_rgba(52,211,153,0.95)]"
            style={{ left: `${modelPosition}%` }}
          />
          <div
            className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-slate-100/70 bg-slate-300 shadow-[0_0_12px_rgba(203,213,225,0.45)]"
            style={{ left: `${marketPosition}%` }}
          />
          <div
            className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border border-emerald-100/80 bg-emerald-300 shadow-[0_0_18px_rgba(52,211,153,0.95)]"
            style={{ left: `${modelPosition}%` }}
          />
          <div className="absolute inset-y-1 left-2 right-2 rounded-full border border-white/5" />
        </div>
        <div className="relative mt-2 h-2">
          {ticks.map((tick) => (
            <span
              key={tick}
              className="absolute top-0 h-2 w-px bg-slate-600/35"
              style={{ left: `${tick}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
