import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

type ActivePick = {
  id: string;
  dateLabel: string;
  matchLabel: string;
  tournament: string;
  market: string;
  selection: string;
  odds: number;
  bookmaker: { name: string };
  stake: number;
};

type RecentSelection = {
  id: string;
  dateLabel: string;
  matchLabel: string;
  market: string;
  selection: string;
  odds: number;
  bookmaker: { name: string };
  stake: number;
  result: "won" | "lost" | "void";
  pnl: number;
};

const activePicks: ActivePick[] = [
  {
    id: "a1",
    dateLabel: "Wed 29 Apr",
    matchLabel: "Alcaraz vs Sinner",
    tournament: "ATP Madrid - R16",
    market: "MATCH WINNER",
    selection: "Alcaraz to win in 2 sets",
    odds: 2.1,
    bookmaker: { name: "bet365" },
    stake: 25,
  },
  {
    id: "a2",
    dateLabel: "Wed 29 Apr",
    matchLabel: "Djokovic vs Rune",
    tournament: "ATP Madrid - R16",
    market: "MATCH WINNER",
    selection: "Djokovic ML",
    odds: 1.55,
    bookmaker: { name: "Pinnacle" },
    stake: 50,
  },
  {
    id: "a3",
    dateLabel: "Thu 30 Apr",
    matchLabel: "Man City vs Liverpool",
    tournament: "EPL",
    market: "ANYTIME GOALSCORER",
    selection: "Haaland to score anytime",
    odds: 1.85,
    bookmaker: { name: "William Hill" },
    stake: 30,
  },
  {
    id: "a4",
    dateLabel: "Thu 30 Apr",
    matchLabel: "Tsitsipas vs Rublev",
    tournament: "ATP Madrid - QF",
    market: "TOTAL GAMES",
    selection: "Over 22.5 games",
    odds: 1.95,
    bookmaker: { name: "Bet Victor" },
    stake: 40,
  },
];

const recentSelections: RecentSelection[] = [
  {
    id: "r1",
    dateLabel: "Mon 27 Apr",
    matchLabel: "Sabalenka vs Swiatek",
    market: "MATCH WINNER",
    selection: "Sabalenka ML",
    odds: 2.3,
    bookmaker: { name: "bet365" },
    stake: 25,
    result: "won",
    pnl: 32.5,
  },
  {
    id: "r2",
    dateLabel: "Sun 26 Apr",
    matchLabel: "Zverev vs Medvedev",
    market: "SET BETTING",
    selection: "Zverev to win in 2",
    odds: 2.5,
    bookmaker: { name: "Pinnacle" },
    stake: 20,
    result: "lost",
    pnl: -20,
  },
  {
    id: "r3",
    dateLabel: "Sun 26 Apr",
    matchLabel: "Real Madrid vs Barcelona",
    market: "ANYTIME GOALSCORER",
    selection: "Bellingham to score anytime",
    odds: 3.1,
    bookmaker: { name: "Sky Bet" },
    stake: 15,
    result: "won",
    pnl: 31.5,
  },
  {
    id: "r4",
    dateLabel: "Sat 25 Apr",
    matchLabel: "Fritz vs Shelton",
    market: "TOTAL GAMES",
    selection: "Over 21.5 games",
    odds: 1.8,
    bookmaker: { name: "Paddy Power" },
    stake: 30,
    result: "won",
    pnl: 24,
  },
  {
    id: "r5",
    dateLabel: "Fri 24 Apr",
    matchLabel: "De Minaur vs Korda",
    market: "MATCH WINNER",
    selection: "De Minaur ML",
    odds: 1.65,
    bookmaker: { name: "William Hill" },
    stake: 40,
    result: "lost",
    pnl: -40,
  },
  {
    id: "r6",
    dateLabel: "Fri 24 Apr",
    matchLabel: "Berrettini vs Hurkacz",
    market: "MATCH WINNER",
    selection: "Berrettini ML",
    odds: 2.05,
    bookmaker: { name: "bet365" },
    stake: 25,
    result: "void",
    pnl: 0,
  },
];

function MarketBadge({ label }: { label: string }) {
  return (
    <span className="inline-block rounded border border-slate-700/40 bg-slate-800/60 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-slate-400">
      {label}
    </span>
  );
}

function ResultBadge({
  status,
  size = "md",
}: {
  status: RecentSelection["result"];
  size?: "sm" | "md";
}) {
  const styles = {
    won: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    lost: "border-rose-500/30 bg-rose-500/10 text-rose-300",
    void: "border-slate-500/30 bg-slate-500/10 text-slate-300",
  };
  const sizing = size === "md" ? "px-2.5 py-1 text-xs" : "px-2 py-0.5 text-[11px]";

  return (
    <span
      className={`inline-flex items-center rounded-md border font-semibold uppercase tracking-wide ${sizing} ${styles[status]}`}
    >
      {status.toUpperCase()}
    </span>
  );
}

function PnL({ value }: { value: number }) {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const formatted = `${sign}${Math.abs(value).toFixed(2)}u`;
  const color = value > 0 ? "text-emerald-400" : value < 0 ? "text-rose-400" : "text-slate-400";

  return <span className={`font-mono text-sm font-semibold tabular-nums ${color}`}>{formatted}</span>;
}

function BookmakerLogo({
  name,
  size = "md",
}: {
  name: string;
  size?: "sm" | "md";
}) {
  const brandStyles: Record<string, string> = {
    bet365: "text-yellow-300",
    Pinnacle: "text-red-400",
    "William Hill": "text-sky-300",
    "Bet Victor": "text-amber-300",
    "Sky Bet": "text-sky-400",
    "Paddy Power": "text-emerald-400",
  };
  const sizeClasses = size === "md" ? "h-6 max-w-[96px] px-2 text-xs" : "h-5 max-w-[60px] px-1.5 text-[11px]";
  const color = brandStyles[name] || "text-slate-200";

  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-md border border-slate-700/40 font-semibold tracking-tight ${sizeClasses} ${color}`}
    >
      {name}
    </span>
  );
}

function BetMobileMeta({
  bet,
  variant,
}: {
  bet: ActivePick | RecentSelection;
  variant: "active" | "settled";
}) {
  const settledBet = variant === "settled" ? (bet as RecentSelection) : null;

  return (
    <div className="space-y-2.5 rounded-xl border border-slate-800/70 bg-[#0c0f14] p-4">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <span className="tabular-nums">{bet.dateLabel}</span>
        {"tournament" in bet && bet.tournament ? (
          <>
            <span className="text-slate-700">-</span>
            <span className="text-slate-400">{bet.tournament}</span>
          </>
        ) : null}
        <span className="ml-auto">
          {variant === "active" ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/[0.06] px-2 py-0.5 text-[11px] font-medium text-emerald-300">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
              LIVE
            </span>
          ) : settledBet ? (
            <ResultBadge status={settledBet.result} size="sm" />
          ) : null}
        </span>
      </div>

      <div className="text-sm text-slate-400">{bet.matchLabel}</div>

      <div>
        <div className="mb-1">
          <MarketBadge label={bet.market} />
        </div>
        <div className="text-base font-medium leading-snug text-slate-100">{bet.selection}</div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 pt-1 text-xs tabular-nums text-slate-400">
        <span className="font-mono font-semibold text-slate-200">{bet.odds.toFixed(2)}</span>
        <span className="text-slate-700">-</span>
        <BookmakerLogo name={bet.bookmaker.name} size="sm" />
        <span className="text-slate-700">-</span>
        <span>Stake {bet.stake}u</span>
        {settledBet ? (
          <span className="ml-auto">
            <PnL value={settledBet.pnl} />
          </span>
        ) : null}
      </div>
    </div>
  );
}

function ActivePicksDesktop() {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
      <header className="flex items-center justify-between border-b border-slate-800/80 px-5 py-3.5">
        <h2 className="text-sm font-medium text-slate-100">Active picks</h2>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/[0.06] px-2.5 py-1 text-xs font-medium text-emerald-300">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          {activePicks.length} live
        </span>
      </header>

      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-800/80 text-[11px] font-medium uppercase tracking-wider text-slate-500">
            <th className="px-4 py-2.5 text-left font-medium">Date</th>
            <th className="px-4 py-2.5 text-left font-medium">Match</th>
            <th className="px-4 py-2.5 text-left font-medium">Selection</th>
            <th className="px-4 py-2.5 text-left font-medium">Odds</th>
            <th className="px-4 py-2.5 text-left font-medium">Bookmaker</th>
            <th className="px-4 py-2.5 text-right font-medium">Stake</th>
          </tr>
        </thead>
        <tbody>
          {activePicks.map((bet) => (
            <tr key={bet.id} className="border-b border-slate-800/60 transition-colors last:border-0 hover:bg-slate-800/30">
              <td className="whitespace-nowrap px-4 py-4 align-top text-xs tabular-nums text-slate-500">
                {bet.dateLabel}
              </td>
              <td className="px-4 py-4 align-top text-sm text-slate-300">
                {bet.matchLabel}
                <div className="mt-0.5 text-xs text-slate-500">{bet.tournament}</div>
              </td>
              <td className="px-4 py-4 align-top">
                <div className="mb-1">
                  <MarketBadge label={bet.market} />
                </div>
                <div className="text-base font-medium text-slate-100">{bet.selection}</div>
              </td>
              <td className="px-4 py-4 align-top font-mono text-base font-semibold tabular-nums text-slate-100">
                {bet.odds.toFixed(2)}
              </td>
              <td className="px-4 py-4 align-top">
                <BookmakerLogo name={bet.bookmaker.name} size="md" />
              </td>
              <td className="px-4 py-4 text-right align-top text-sm tabular-nums text-slate-300">{bet.stake}u</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function RecentSelectionsDesktop() {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
      <header className="flex items-center justify-between border-b border-slate-800/80 px-5 py-3.5">
        <h2 className="text-sm font-medium text-slate-100">Recent selections</h2>
        <a href="#" className="text-xs text-slate-400 transition-colors hover:text-slate-200">
          View full track record -&gt;
        </a>
      </header>

      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-800/80 text-[11px] font-medium uppercase tracking-wider text-slate-500">
            <th className="px-4 py-2.5 text-left font-medium">Date</th>
            <th className="px-4 py-2.5 text-left font-medium">Match</th>
            <th className="px-4 py-2.5 text-left font-medium">Selection</th>
            <th className="px-4 py-2.5 text-left font-medium">Odds</th>
            <th className="px-4 py-2.5 text-left font-medium">Bookmaker</th>
            <th className="px-4 py-2.5 text-right font-medium">Stake</th>
            <th className="py-2.5 pl-6 pr-4 text-left font-medium">Result</th>
            <th className="px-4 py-2.5 text-right font-medium">P&amp;L</th>
          </tr>
        </thead>
        <tbody>
          {recentSelections.map((bet) => (
            <tr key={bet.id} className="border-b border-slate-800/60 transition-colors last:border-0 hover:bg-slate-800/30">
              <td className="whitespace-nowrap px-4 py-3 align-top text-xs tabular-nums text-slate-500">
                {bet.dateLabel}
              </td>
              <td className="px-4 py-3 align-top text-[13px] text-slate-400">{bet.matchLabel}</td>
              <td className="px-4 py-3 align-top">
                <div className="mb-1">
                  <MarketBadge label={bet.market} />
                </div>
                <div className="text-sm text-slate-200">{bet.selection}</div>
              </td>
              <td className="px-4 py-3 align-top font-mono text-sm tabular-nums text-slate-200">{bet.odds.toFixed(2)}</td>
              <td className="px-4 py-3 align-top">
                <BookmakerLogo name={bet.bookmaker.name} size="md" />
              </td>
              <td className="px-4 py-3 text-right align-top text-sm tabular-nums text-slate-400">{bet.stake}u</td>
              <td className="py-3 pl-6 pr-4 align-top">
                <ResultBadge status={bet.result} />
              </td>
              <td className="px-4 py-3 text-right align-top">
                <PnL value={bet.pnl} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function SectionLabel({ children }: { children: string }) {
  return <div className="mb-3 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-500">{children}</div>;
}

export default function HomepageTableMock() {
  if (process.env.NODE_ENV === "production") {
    notFound();
  }

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <div className="border-b border-slate-800/80 bg-slate-900/30">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-3 text-xs sm:flex-row sm:items-center sm:justify-between">
          <span className="inline-flex items-center gap-2 text-slate-400">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-400" />
            <span className="font-medium uppercase tracking-wider text-amber-300/90">Mock preview</span>
            <span className="text-slate-600">-</span>
            <span>fake data - not production</span>
          </span>
          <span className="font-mono text-slate-500">il margine - homepage tables v4.1</span>
        </div>
      </div>

      <div className="mx-auto max-w-6xl space-y-14 px-6 py-10 md:py-14">
        <div className="hidden md:block">
          <SectionLabel>Desktop view</SectionLabel>
          <div className="space-y-6">
            <ActivePicksDesktop />
            <RecentSelectionsDesktop />
          </div>
        </div>

        <div>
          <SectionLabel>Mobile view, about 380px</SectionLabel>
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="max-w-[380px]">
              <div className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
                <header className="flex items-center justify-between border-b border-slate-800/80 px-4 py-3">
                  <h3 className="text-sm font-medium text-slate-100">Active picks</h3>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/[0.06] px-2 py-0.5 text-[11px] font-medium text-emerald-300">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                    {activePicks.length} live
                  </span>
                </header>
                <div className="space-y-2 p-3">
                  {activePicks.map((bet) => (
                    <BetMobileMeta key={bet.id} bet={bet} variant="active" />
                  ))}
                </div>
              </div>
            </div>

            <div className="max-w-[380px]">
              <div className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
                <header className="flex items-center justify-between border-b border-slate-800/80 px-4 py-3">
                  <h3 className="text-sm font-medium text-slate-100">Recent selections</h3>
                  <a href="#" className="text-[11px] text-slate-400 transition-colors hover:text-slate-200">
                    View all -&gt;
                  </a>
                </header>
                <div className="space-y-2 p-3">
                  {recentSelections.map((bet) => (
                    <BetMobileMeta key={bet.id} bet={bet} variant="settled" />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-800/60 pt-6 text-xs leading-relaxed text-slate-500">
          <p className="mb-1">
            Bookmaker names render as branded wordmarks in this mock. Production resolves to image assets first; this
            wordmark style is fallback-only design guidance.
          </p>
          <p>All bet data, prices, and outcomes shown are illustrative and unrelated to live Il Margine signals.</p>
        </div>
      </div>
    </div>
  );
}
