type StatusStepsProps = {
  status: string;
};

const STEPS = ["Doubtful", "Projected", "Confirmed"];

function activeStep(status: string) {
  const normalized = status.trim().toLowerCase();

  if (normalized.includes("confirm")) return 2;
  if (normalized.includes("project") || normalized.includes("starter")) return 1;
  return 0;
}

export function StatusSteps({ status }: StatusStepsProps) {
  const active = activeStep(status);

  return (
    <div className="min-w-[150px]">
      <div className="grid grid-cols-3 items-center gap-1">
        {STEPS.map((step, index) => (
          <div key={step} className="flex items-center">
            <span
              className={`rounded-full border ${
                index === active
                  ? "h-4 w-4 border-emerald-100 bg-emerald-300 shadow-[0_0_0_4px_rgba(52,211,153,0.12),0_0_18px_rgba(52,211,153,0.85)]"
                  : index < active
                    ? "h-2.5 w-2.5 border-slate-600 bg-slate-700"
                    : "h-2.5 w-2.5 border-slate-700 bg-transparent"
              }`}
            />
            {index < STEPS.length - 1 ? (
              <span
                className={`h-px flex-1 ${
                  index < active ? "bg-slate-600" : "bg-slate-800"
                }`}
              />
            ) : null}
          </div>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-3 gap-1 text-center text-[8px] font-semibold uppercase tracking-[0.1em] text-slate-600">
        {STEPS.map((step, index) => (
          <span key={step} className={index === active ? "text-emerald-300" : ""}>
            {step}
          </span>
        ))}
      </div>
    </div>
  );
}
