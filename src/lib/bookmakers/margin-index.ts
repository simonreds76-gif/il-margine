export type MarginSegmentOperator = {
  rank: number;
  name: string;
  raw_overround_pct: number;
  normalized_hold_pct: number;
  samples: number;
};

export type MarginSegment = {
  sport: string;
  sport_slug: string;
  market_family: string;
  events: number;
  observations: number;
  status: "PASS" | "PASS_LIMITED" | "THIN_SAMPLE" | string;
  operators: MarginSegmentOperator[];
};

export type NotMeasuredMarket = {
  sport_slug: "football" | "tennis";
  label: string;
  reason: string;
};

export type BookmakerMarginIndex = {
  generated_at: string | null;
  status: string;
  capture_mode?: string;
  summary: {
    operators: number;
    diagnostic_operators?: number;
    sports?: string[];
    events: number;
    market_families: string[];
    observations: number;
  };
  segments?: MarginSegment[];
  coverage?: {
    target_operators: number;
    discovered_operators: number;
    payload_operators: number;
    qualified_operators: number;
    payload_operator_names?: string[];
    qualified_operator_names?: string[];
    not_discovered?: string[];
  };
};

export const NOT_MEASURED_MARKETS: NotMeasuredMarket[] = [
  { sport_slug: "football", label: "Goalscorer", reason: "Anytime goalscorer selections overlap, so they do not form a complete outcome set." },
  { sport_slug: "tennis", label: "Set markets", reason: "Not measured in this snapshot." },
  { sport_slug: "tennis", label: "Breaks", reason: "The current data source does not expose this market." },
  { sport_slug: "tennis", label: "Most aces 1X2", reason: "The current data source does not expose a complete market." },
];

export function capturedLabel(value: string | null) {
  if (!value) return "No verified capture yet";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(new Date(value));
}

export function confidenceLabel(events: number) {
  if (events < 4) return { label: "Thin", className: "border-slate-700 bg-slate-900 text-slate-400" };
  if (events < 10) return { label: "Limited", className: "border-amber-400/25 bg-amber-400/[0.08] text-amber-200" };
  if (events < 25) return { label: "Fair", className: "border-sky-400/25 bg-sky-400/[0.08] text-sky-200" };
  return { label: "Good", className: "border-emerald-400/25 bg-emerald-400/[0.08] text-emerald-200" };
}

