"use client";

import { useMemo, useState } from "react";
import BookmakerLogo from "@/components/BookmakerLogo";
import MarketBadge from "@/components/MarketBadge";
import TrackedLink from "@/components/TrackedLink";
import type { Bet, Bookmaker } from "@/lib/supabase";
import { formatOdds, formatStake } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";
import { track } from "@/lib/analytics";

type EdgeBet = Bet & {
  bookmaker?: Bookmaker | Bookmaker[] | null;
};

type Filter = "all" | "props" | "tennis";

type TodaysEdgeProps = {
  picks: EdgeBet[];
  lastSettled?: EdgeBet | null;
  last7Profit?: number | null;
};

const londonDate = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  day: "numeric",
  month: "short",
});

const londonTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function dateChip(value: string | null): string {
  if (!value) return "Date TBC";
  const date = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return "Date TBC";
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
  const days = Math.round((target.getTime() - today.getTime()) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return londonDate.format(date);
}

function publishedTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Published"
    : `Posted ${londonDate.format(date)} · ${londonTime.format(date)}`;
}

function laneLabel(market: string): string {
  return market === "props" ? "Football props" : "Tennis";
}

function selectVisiblePicks(picks: EdgeBet[], filter: Filter): EdgeBet[] {
  const filtered = picks.filter((pick) => filter === "all" || pick.market === filter);
  if (filter !== "all") return filtered.slice(0, 4);

  const eventCounts = new Map<string, number>();
  const balanced = filtered.filter((pick) => {
    const count = eventCounts.get(pick.event) ?? 0;
    if (count >= 3) return false;
    eventCounts.set(pick.event, count + 1);
    return true;
  });
  const visible = balanced.slice(0, 4);

  if (picks.some((pick) => pick.market === "tennis") && !visible.some((pick) => pick.market === "tennis")) {
    const tennisPick = picks.find((pick) => pick.market === "tennis");
    if (tennisPick) {
      if (visible.length === 4) visible[3] = tennisPick;
      else visible.push(tennisPick);
    }
  }

  return visible;
}

export default function TodaysEdge({ picks, lastSettled = null, last7Profit = null }: TodaysEdgeProps) {
  const [filter, setFilter] = useState<Filter>("all");
  const counts = useMemo(
    () => ({
      all: picks.length,
      props: picks.filter((pick) => pick.market === "props").length,
      tennis: picks.filter((pick) => pick.market === "tennis").length,
    }),
    [picks],
  );
  const visible = useMemo(() => selectVisiblePicks(picks, filter), [filter, picks]);
  const fullCardHref =
    filter === "props" || (filter === "all" && counts.props > 0)
      ? "/player-props#picks"
      : filter === "tennis" || counts.tennis > 0
        ? "/tennis-tips#picks"
        : "/track-record";

  const setActiveFilter = (next: Filter) => {
    setFilter(next);
    track("today_edge_filter_used", { filter: next, count: counts[next] });
  };

  return (
    <section
      aria-labelledby="todays-edge-heading"
      className="relative overflow-hidden rounded-2xl border border-[rgba(87,209,150,0.24)] bg-[linear-gradient(145deg,rgba(12,23,24,0.98),rgba(8,11,17,0.98)_58%)] shadow-2xl shadow-black/35"
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-300/45 to-transparent" />
      <div className="p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-emerald-300/90">
              Posted prices
            </p>
            <h2 id="todays-edge-heading" className="mt-1 text-xl font-semibold text-white">
              Today&apos;s Edge
            </h2>
          </div>
          <span className={`rounded-full border px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.12em] ${
            picks.length > 0
              ? "border-emerald-300/25 bg-emerald-400/10 text-emerald-200"
              : "border-slate-700 bg-slate-900/70 text-slate-400"
          }`}>
            {picks.length > 0 ? `${picks.length} active` : "No active picks"}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl border border-white/[0.06] bg-black/20 p-2">
          <EdgeMetric label="Props" value={counts.props.toString()} />
          <EdgeMetric label="Tennis" value={counts.tennis.toString()} />
          <EdgeMetric
            label="7-day P/L"
            value={last7Profit == null ? "—" : `${last7Profit >= 0 ? "+" : ""}${last7Profit.toFixed(2)}u`}
            positive={last7Profit != null ? last7Profit >= 0 : undefined}
          />
        </div>

        <div className="mt-4 flex gap-2 overflow-x-auto pb-1" role="group" aria-label="Filter active picks">
          {([
            ["all", "All"],
            ["props", "Football props"],
            ["tennis", "Tennis"],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              type="button"
              disabled={id !== "all" && counts[id] === 0}
              aria-pressed={filter === id}
              onClick={() => setActiveFilter(id)}
              className={`min-h-11 shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                filter === id
                  ? "border-emerald-300/35 bg-emerald-400/12 text-emerald-100"
                  : "border-slate-700/70 bg-slate-900/55 text-slate-300 hover:border-slate-600 hover:text-slate-100 disabled:cursor-not-allowed disabled:border-slate-700/70 disabled:bg-slate-900/30 disabled:text-slate-400 disabled:hover:border-slate-700/70 disabled:hover:text-slate-400"
              }`}
            >
              {label} {counts[id]}
            </button>
          ))}
        </div>

        {visible.length > 0 ? (
          <div className="mt-3 divide-y divide-slate-800/80 overflow-hidden rounded-xl border border-slate-800/80 bg-[#090d12]/75">
            {visible.map((pick) => (
              <TrackedLink
                key={pick.id}
                href={publicTipPath(pick)}
                eventName="homepage_to_pick_click"
                eventParams={{ bet_id: pick.id, market: pick.market, source: "todays_edge" }}
                className="group block px-4 py-3.5 transition hover:bg-slate-800/35"
              >
                <div className="flex items-center justify-between gap-3 font-mono text-[11px] uppercase tracking-[0.1em] text-slate-400">
                  <div className="flex min-w-0 items-center gap-2">
                    <MarketBadge
                      market={pick.market}
                      category={pick.category}
                      event={pick.event}
                      compact
                      className="rounded-md border border-white/[0.06] bg-black/20 px-0.5"
                    />
                    <span className="truncate">{laneLabel(pick.market)} · {dateChip(pick.match_date)}</span>
                  </div>
                  <span className="shrink-0 whitespace-nowrap text-right">{publishedTime(pick.posted_at)}</span>
                </div>
                <div className="mt-2 text-sm font-semibold leading-snug text-slate-100 group-hover:text-emerald-100">
                  {pick.event}
                </div>
                <div className="mt-1 text-sm leading-snug text-slate-300">
                  {pick.player ? `${pick.player} · ` : ""}{pick.selection}
                </div>
                <div className="mt-3 flex items-center gap-3">
                  <span className="font-mono text-xl font-black tabular-nums text-white">{formatOdds(pick.odds)}</span>
                  <span className="rounded-md border border-slate-700/70 bg-slate-900/70 px-2 py-1 font-mono text-xs text-emerald-200">
                    {formatStake(pick.stake)}u
                  </span>
                  <div className="ml-auto max-w-20 overflow-hidden opacity-70 grayscale-[35%] transition group-hover:opacity-100 group-hover:grayscale-0">
                    <BookmakerLogo bookmaker={pick.bookmaker} size="sm" noLink />
                  </div>
                </div>
              </TrackedLink>
            ))}
          </div>
        ) : (
          <div className="mt-4 rounded-xl border border-dashed border-slate-700/80 bg-slate-950/35 p-5">
            <p className="font-semibold text-slate-200">
              {picks.length === 0 ? "Nothing is priced badly enough right now." : `No ${filter === "props" ? "football props" : "tennis picks"} active.`}
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              We post when the number is wrong, not to fill a daily quota.
            </p>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <TrackedLink
            href={fullCardHref}
            eventName={visible.length > 0 ? "today_edge_open_full_card" : "track_record_click"}
            eventParams={{ source: "todays_edge", filter }}
            className="text-sm font-semibold text-emerald-300 transition hover:text-emerald-200"
          >
            {visible.length > 0 ? "Open full card" : "See the public record"} →
          </TrackedLink>
          {lastSettled ? (
            <span className="min-w-0 truncate text-xs text-slate-400">
              Last settled: {lastSettled.event} · {Number(lastSettled.profit_loss) >= 0 ? "+" : ""}
              {Number(lastSettled.profit_loss || 0).toFixed(2)}u
            </span>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function EdgeMetric({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div className="rounded-lg px-2 py-2 text-center">
      <div className="font-mono text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400 sm:text-[11px] sm:tracking-[0.12em]">{label}</div>
      <div className={`mt-1 font-mono text-sm font-black tabular-nums ${
        positive === undefined ? "text-slate-100" : positive ? "text-emerald-300" : "text-rose-300"
      }`}>
        {value}
      </div>
    </div>
  );
}
