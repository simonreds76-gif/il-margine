type PriceGapMeterProps = {
  value: number;
};

export function PriceGapMeter({ value }: PriceGapMeterProps) {
  const min = -10;
  const max = 20;
  const clamped = Math.max(min, Math.min(max, value));
  const zeroPosition = ((0 - min) / (max - min)) * 100;
  const valuePosition = ((clamped - min) / (max - min)) * 100;
  const left = Math.min(zeroPosition, valuePosition);
  const width = Math.abs(valuePosition - zeroPosition);
  const positive = clamped >= 0;

  return (
    <div className="mt-2 h-7 min-w-[148px] max-w-full overflow-visible px-1">
      <div className="relative mx-2 h-1.5 rounded-full bg-slate-800">
        <div
          className={`absolute top-0 h-1.5 rounded-full ${
            positive ? "bg-amber-300" : "bg-rose-400"
          }`}
          style={{ left: `${left}%`, width: `${width}%` }}
        />
        <div
          className="absolute -top-1 h-3.5 w-px bg-slate-500"
          style={{ left: `${zeroPosition}%` }}
        />
        <div
          className={`absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ${
            positive ? "bg-amber-200 shadow-[0_0_10px_rgba(252,211,77,0.8)]" : "bg-rose-300"
          }`}
          style={{ left: `${valuePosition}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[8px] font-semibold uppercase tracking-[0.1em] text-slate-500">
        <span>-10pp</span>
        <span>0</span>
        <span>+20pp</span>
      </div>
    </div>
  );
}
