type MinutesMeterProps = {
  minutes?: number;
};

export function MinutesMeter({ minutes = 0 }: MinutesMeterProps) {
  const clamped = Math.max(0, Math.min(90, minutes));
  const percentage = (clamped / 90) * 100;
  const fullRoleThreshold = (70 / 90) * 100;
  const strongRole = clamped >= 70;

  return (
    <div className="relative h-9 w-full min-w-[130px]">
      <div className="absolute left-0 right-0 top-3 h-1.5 rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full ${strongRole ? "bg-sky-300 shadow-[0_0_10px_rgba(125,211,252,0.35)]" : "bg-amber-300"}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div
        className="absolute top-1 h-5 w-px -translate-x-1/2 bg-slate-300/70"
        style={{ left: `${fullRoleThreshold}%` }}
      />
      <div className="absolute bottom-0 left-0 right-0 flex justify-between text-[9px] font-medium uppercase tracking-[0.12em] text-slate-600">
        <span>0</span>
        <span>70 min role</span>
        <span>90</span>
      </div>
    </div>
  );
}
