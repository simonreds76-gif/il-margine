type PriceGapMeterProps = {
  value: number;
};

export function PriceGapMeter({ value }: PriceGapMeterProps) {
  const min = -10;
  const max = 15;
  const clamped = Math.max(min, Math.min(max, value));
  const zeroPosition = ((0 - min) / (max - min)) * 100;
  const valuePosition = ((clamped - min) / (max - min)) * 100;
  const left = Math.min(zeroPosition, valuePosition);
  const width = Math.abs(valuePosition - zeroPosition);
  const positive = clamped >= 0;

  return (
    <div className="mt-2 h-6 min-w-[120px]">
      <div className="relative h-1.5 rounded-full bg-slate-800">
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
      </div>
      <div className="mt-1 flex justify-between text-[8px] font-semibold uppercase tracking-[0.1em] text-slate-600">
        <span>-10pp</span>
        <span>0</span>
        <span>+15pp</span>
      </div>
    </div>
  );
}
