type PublicRecordMetricGridProps = {
  activeName: string;
  totalBets: number;
  totalStake: number;
  totalProfit: number;
  roi: number;
  winRate: number;
  avgOdds: number;
  hasArchiveBaseline?: boolean;
};

function units(value: number, signed = false): string {
  const prefix = signed && value > 0 ? "+" : "";
  return `${prefix}${value.toLocaleString("en-GB", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  })}u`;
}

function percent(value: number, signed = false): string {
  const prefix = signed && value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(1)}%`;
}

function resultTone(value: number): string {
  if (value > 0) return "text-emerald-300";
  if (value < 0) return "text-rose-300";
  return "text-slate-200";
}

export default function PublicRecordMetricGrid({
  activeName,
  totalBets,
  totalStake,
  totalProfit,
  roi,
  winRate,
  avgOdds,
  hasArchiveBaseline = false,
}: PublicRecordMetricGridProps) {
  const hasRecord = totalBets > 0;
  const metrics = [
    { label: "Settled bets", value: hasRecord ? totalBets.toLocaleString("en-GB") : "-" },
    { label: "Total staked", value: hasRecord ? units(totalStake) : "-" },
    {
      label: "Profit / loss",
      value: hasRecord ? units(totalProfit, true) : "-",
      tone: hasRecord ? resultTone(totalProfit) : undefined,
    },
    {
      label: "ROI",
      value: hasRecord ? percent(roi, true) : "-",
      tone: hasRecord ? resultTone(roi) : undefined,
    },
    { label: "Win rate", value: hasRecord ? percent(winRate) : "-" },
    { label: "Average odds", value: hasRecord && avgOdds > 0 ? avgOdds.toFixed(2) : "-" },
  ];

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/35">
      <div className="flex flex-col gap-2 border-b border-slate-800 px-4 py-4 sm:flex-row sm:items-end sm:justify-between sm:px-5">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-emerald-400">Selected record</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-100">{activeName}</h3>
        </div>
        <p className="text-xs text-slate-500">Settled stakes only</p>
      </div>

      <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="border-b border-r border-slate-800/80 px-4 py-4 last:border-r-0 sm:px-5 lg:border-b-0"
          >
            <dt className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{metric.label}</dt>
            <dd className={`mt-2 font-mono text-xl font-semibold tabular-nums ${metric.tone ?? "text-slate-100"}`}>
              {metric.value}
            </dd>
          </div>
        ))}
      </dl>

      <p className="border-t border-slate-800/80 px-4 py-3 text-[11px] leading-5 text-slate-500 sm:px-5">
        ROI = profit divided by total units staked.
        {hasArchiveBaseline
          ? " Pre-ledger archive records use their documented 1u-equivalent baseline; newer selections use recorded stakes."
          : " All figures use recorded settled stakes."}
      </p>
    </div>
  );
}
