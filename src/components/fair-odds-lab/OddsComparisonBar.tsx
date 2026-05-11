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

function formatGap(value: number) {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(1)} pp`;
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
  const minGap = -10;
  const maxGap = 20;
  const clampedGap = Math.max(minGap, Math.min(maxGap, gapPp));
  const zeroPosition = ((0 - minGap) / (maxGap - minGap)) * 100;
  const valuePosition = ((clampedGap - minGap) / (maxGap - minGap)) * 100;
  const fillLeft = Math.min(zeroPosition, valuePosition);
  const fillWidth = Math.abs(valuePosition - zeroPosition);
  const positiveGap = clampedGap >= 0;
  const modelChance = modelProb ?? 100 / modelOdds;
  const marketChance = marketProb ?? 100 / bookOdds;

  return (
    <div
      className={
        compact
          ? "overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-950/75 p-3"
          : "overflow-hidden rounded-[1.75rem] border border-emerald-300/25 bg-slate-950/70 p-4 shadow-[0_0_40px_rgba(16,185,129,0.08)] sm:p-5"
      }
    >
      <div
        className={`grid grid-cols-[minmax(74px,1fr)_minmax(88px,auto)_minmax(74px,1fr)] items-end ${
          compact ? "gap-2" : "gap-3 sm:grid-cols-[minmax(92px,1fr)_minmax(116px,auto)_minmax(92px,1fr)]"
        }`}
      >
        <div className="min-w-0">
          <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
            Il Margine
          </div>
          <div
            className={
              compact
                ? "mt-1 font-mono text-xl font-black text-emerald-200 sm:text-2xl"
                : "mt-1 font-mono text-3xl font-black tracking-tight text-emerald-200 sm:text-5xl"
            }
          >
            {formatOdds(modelOdds)}
          </div>
        </div>
        <div className="relative mb-0 shrink-0 text-center">
          <div className="text-[9px] font-black uppercase tracking-[0.2em] text-slate-400">
            {compact ? "gap" : "price gap"}
          </div>
          <div
            className={
              compact
                ? "mt-1 whitespace-nowrap font-mono text-sm font-bold text-amber-300"
                : "mt-1 whitespace-nowrap font-mono text-xl font-black text-amber-300 sm:text-3xl"
            }
          >
            {formatGap(gapPp)}
          </div>
          {!compact ? (
            <div className="mt-0.5 whitespace-nowrap text-[9px] font-medium normal-case tracking-normal text-slate-500">
              percentage points vs market
            </div>
          ) : null}
        </div>
        <div className="min-w-0 text-right">
          <div className="truncate text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Reference
            {!compact ? (
              <span className="ml-1 normal-case tracking-normal text-slate-600">{bookName}</span>
            ) : null}
          </div>
          <div
            className={
              compact
                ? "mt-1 font-mono text-xl font-black text-slate-100 sm:text-2xl"
                : "mt-1 font-mono text-3xl font-black tracking-tight text-slate-100 sm:text-5xl"
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
            style={{ left: `${fillLeft}%`, width: `${Math.max(2, fillWidth)}%` }}
          />
          <div
            className="absolute inset-y-[-5px] w-px bg-slate-300/80 shadow-[0_0_10px_rgba(203,213,225,0.45)]"
            style={{ left: `${zeroPosition}%` }}
          />
          <div
            className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border border-emerald-100/80 bg-emerald-300 shadow-[0_0_18px_rgba(52,211,153,0.95)]"
            style={{ left: `${valuePosition}%` }}
          />
          <div className="absolute inset-y-1 left-2 right-2 rounded-full border border-white/5" />
        </div>
        {!compact ? (
          <div className="mt-2 flex justify-between text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-600">
            <span>-10pp</span>
            <span>0</span>
            <span>+20pp</span>
          </div>
        ) : null}
        <div className="sr-only">
          Model chance {modelChance.toFixed(1)}%; market implied chance {marketChance.toFixed(1)}%.
        </div>
      </div>
    </div>
  );
}
