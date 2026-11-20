export type MarketIcon = "winner" | "totals" | "spreads";

/** Records without a market are match-winner records; an unknown market gets no symbol rather than a guessed one. */
export const marketIcon = (market?: string | null): MarketIcon | null =>
  market == null || market === "winner" ? "winner" : market === "totals" ? "totals" : market === "spreads" ? "spreads" : null;

/**
 * The three market symbols share one grammar with the chart marks. A bar is a side or a line:
 * winner is two sides with the solid dot on the selection, totals is one line with over and under,
 * handicap is two sides with the dotted run one of them has to make up.
 * `x`, `y` and `color` place the same drawing inside the exported chart, where CSS colour does not exist.
 */
export function DeskIcon({ name, size = 20, x, y, color }: {
  name: "drop"|"replay"|"record"|"download"|MarketIcon; size?: number; x?: number; y?: number; color?: string;
}) {
  const paths={
    drop:<><path d="M3 6h6v5h6v6h5"/><circle cx="20" cy="17" r="2" fill="currentColor"/></>,
    replay:<><path d="M3.5 10a8.5 8.5 0 1 1 1.2 7.1M3.5 4.5V10H9"/><path d="m10 8 6 4-6 4z" strokeLinejoin="round"/></>,
    record:<><rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M7 8h9M7 12h3m3 2 2 2 4-5"/></>,
    download:<><path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/></>,
    winner:<><path d="M3 7.5h9.5M3 16.5h9.5"/><circle cx="18" cy="7.5" r="2.75" fill="currentColor"/><circle cx="18" cy="16.5" r="2.75"/></>,
    totals:<><path d="M3 12h18"/><path d="m8 7.5 4-4 4 4M8 16.5l4 4 4-4"/></>,
    spreads:<><path d="M3 7.5h18M3 16.5h8.5"/><path d="M15 16.5h.01M18 16.5h.01M21 16.5h.01"/></>,
  };
  return <svg x={x} y={y} width={size} height={size} viewBox="0 0 24 24" color={color} aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
