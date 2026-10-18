export type SkylineVariant = "baseline" | "delivery" | "height" | "combined";
export type SkylineRow = {
  key: string; player: string; match: string; kickoff: string; lineup: string;
  odds: number; price_at: string; captured_at: string; expected_minutes: number;
  predictions: Partial<Record<SkylineVariant, number>>;
  selections: Partial<Record<SkylineVariant, boolean>>;
  status: string; headed_sot: number | null;
};
export type SkylineStats = {
  selections: number; settled: number; wins: number; losses: number; void: number;
  pending: number; overdue: number; settled_stake: number; profit: number;
  roi: number | null; fixtures: number; accuracy_n: number;
  brier: number | null; log_loss: number | null;
};
export type SkylineResearch = {
  note: string; height_limit: string; decision: string;
  periods: Record<string, {
    start: string; end: string; common_rows: number;
    models: Record<SkylineVariant, { n: number; fixtures: number; hits: number; brier: number; log_loss: number }>;
    paired_log_loss_delta_95pct: Record<SkylineVariant, [number, number]>;
  }>;
};
export type SkylineReport = {
  name: string; version: string; generated_at: string; status: string; primary: SkylineVariant;
  forecasts: number; paired_settled_fixtures: number; paired_stats: Record<SkylineVariant, SkylineStats>; stats: Record<SkylineVariant, SkylineStats>;
  board: SkylineRow[]; ledger: SkylineRow[]; ledger_total: number;
  research: SkylineResearch; settlement_policy: string;
  paired_forward_count: number; exclusions: Record<string, number>;
};
