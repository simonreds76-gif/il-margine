import type {
  MarginSegment,
  MarginSegmentOperator,
} from "@/lib/bookmakers/margin-index";

export const MEANINGFUL_GAP_PP = 0.5;

export type MarginSortKey =
  | "name"
  | "margin"
  | "gapBest"
  | "gapMedian"
  | "medianDistance"
  | "samples";

export type SortDirection = "asc" | "desc";

export type DerivedMarginOperator = MarginSegmentOperator & {
  displayRank: number;
  tied: boolean;
  gapToBest: number;
  gapToMedian: number;
  scalePct: number;
};

export type SegmentStats = {
  rows: DerivedMarginOperator[];
  cheapest: DerivedMarginOperator;
  dearest: DerivedMarginOperator;
  median: number;
  spread: number;
  medianTickPct: number | null;
};

function roundedKey(value: number) {
  return value.toFixed(2);
}

function median(values: number[]) {
  const middle = Math.floor(values.length / 2);
  if (values.length % 2 === 1) return values[middle];
  return (values[middle - 1] + values[middle]) / 2;
}

export function deriveSegmentStats(segment: MarginSegment): SegmentStats | null {
  if (segment.operators.length === 0) return null;

  const sorted = [...segment.operators].sort(
    (left, right) =>
      left.normalized_hold_pct - right.normalized_hold_pct ||
      left.name.localeCompare(right.name),
  );
  const values = sorted.map((operator) => operator.normalized_hold_pct);
  const minimum = values[0];
  const maximum = values[values.length - 1];
  const medianValue = median(values);
  const spread = maximum - minimum;
  const uniqueValues = Array.from(new Set(values.map(roundedKey)));
  const counts = values.reduce<Map<string, number>>((result, value) => {
    const key = roundedKey(value);
    result.set(key, (result.get(key) ?? 0) + 1);
    return result;
  }, new Map());

  const rows = sorted.map((operator) => {
    const key = roundedKey(operator.normalized_hold_pct);
    const relative = spread === 0
      ? 50
      : ((operator.normalized_hold_pct - minimum) / spread) * 100;
    return {
      ...operator,
      displayRank: uniqueValues.indexOf(key) + 1,
      tied: (counts.get(key) ?? 0) > 1,
      gapToBest: operator.normalized_hold_pct - minimum,
      gapToMedian: operator.normalized_hold_pct - medianValue,
      scalePct: spread === 0 ? 50 : Math.min(100, Math.max(2, relative)),
    };
  });

  return {
    rows,
    cheapest: rows[0],
    dearest: rows[rows.length - 1],
    median: medianValue,
    spread,
    medianTickPct: spread === 0
      ? null
      : ((medianValue - minimum) / spread) * 100,
  };
}

export function sortMarginRows(
  rows: DerivedMarginOperator[],
  key: MarginSortKey,
  direction: SortDirection,
) {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    let comparison = 0;
    if (key === "name") comparison = left.name.localeCompare(right.name);
    if (key === "margin") comparison = left.normalized_hold_pct - right.normalized_hold_pct;
    if (key === "gapBest") comparison = left.gapToBest - right.gapToBest;
    if (key === "gapMedian") comparison = left.gapToMedian - right.gapToMedian;
    if (key === "medianDistance") comparison = Math.abs(left.gapToMedian) - Math.abs(right.gapToMedian);
    if (key === "samples") comparison = left.samples - right.samples;
    return (
      comparison * multiplier ||
      left.normalized_hold_pct - right.normalized_hold_pct ||
      left.name.localeCompare(right.name)
    );
  });
}

export function formatMargin(value: number) {
  return `${value.toFixed(2)}%`;
}

export function formatGap(value: number) {
  if (Math.abs(value) < 0.005) return "0.00pp";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}pp`;
}
