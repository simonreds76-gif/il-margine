type SignedBoostMeterProps = {
  value: number;
  range?: number;
};

export function SignedBoostMeter({ value, range = 30 }: SignedBoostMeterProps) {
  const clamped = Math.max(-range, Math.min(range, value));
  const valuePosition = Math.max(0, Math.min(100, ((clamped + range) / (range * 2)) * 100));
  const neutralPosition = 50;
  const fillLeft = Math.min(neutralPosition, valuePosition);
  const fillWidth = Math.max(3, Math.abs(valuePosition - neutralPosition));
  const positive = clamped >= 0;
  const stateLabel = positive ? "Boost" : "Drag";

  return (
    <div className="relative h-12 w-full min-w-[130px]" aria-label={`Fixture swing ${value}%`}>
      <div
        className={`absolute top-0 -translate-x-1/2 rounded-full border px-1.5 py-0.5 text-[8px] font-black uppercase tracking-[0.12em] ${
          positive
            ? "border-sky-300/35 bg-sky-400/10 text-sky-100"
            : "border-rose-300/35 bg-rose-400/10 text-rose-100"
        }`}
        style={{ left: `${valuePosition}%` }}
      >
        {stateLabel}
      </div>

      <div className="absolute left-0 right-0 top-5 h-2.5 overflow-hidden rounded-full bg-gradient-to-r from-rose-950/80 via-slate-800 to-cyan-950/90 ring-1 ring-slate-700/70">
        <div
          className={`absolute inset-y-0 left-0 rounded-full ${
            positive
              ? "bg-gradient-to-r from-slate-700 via-sky-500/70 to-sky-300 shadow-[0_0_18px_rgba(56,189,248,0.5)]"
              : "bg-gradient-to-r from-rose-400 to-slate-700 shadow-[0_0_14px_rgba(251,113,133,0.45)]"
          }`}
          style={{ left: `${fillLeft}%`, width: `${fillWidth}%` }}
        />
        <div className="absolute inset-y-0 left-1/2 w-px bg-slate-300/35" />
      </div>

      <div
        className={`absolute top-[17px] h-4 w-4 -translate-x-1/2 rounded-full border ${
          positive
            ? "border-sky-50 bg-sky-300 shadow-[0_0_20px_rgba(56,189,248,0.95)]"
            : "border-rose-100/80 bg-rose-300 shadow-[0_0_16px_rgba(251,113,133,0.75)]"
        }`}
        style={{ left: `${valuePosition}%` }}
      />
      <div
        className={`absolute top-[33px] h-0 w-0 -translate-x-1/2 border-x-[5px] border-t-[7px] border-x-transparent ${
          positive ? "border-t-sky-300" : "border-t-rose-300"
        }`}
        style={{ left: `${valuePosition}%` }}
      />

      <div className="absolute bottom-0 left-0 right-0 grid grid-cols-3 text-[9px] font-semibold uppercase tracking-[0.12em]">
        <span className="text-rose-300/45">Drag</span>
        <span className="text-center text-slate-500">Neutral</span>
        <span className="text-right text-sky-300/75">Boost</span>
      </div>
    </div>
  );
}
