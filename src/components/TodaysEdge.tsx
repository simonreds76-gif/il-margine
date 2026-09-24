"use client";

import SportIcon from "@/components/SportIcon";
import MarketBadge from "@/components/MarketBadge";
import { useMemo, useState } from "react";
import BookmakerLogo from "@/components/BookmakerLogo";
import styles from "./TodaysEdge.module.css";
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

function selectVisiblePicks(picks: EdgeBet[], filter: Filter): EdgeBet[] {
  const filtered = picks.filter((pick) => filter === "all" || pick.market === filter);
  if (filter !== "all") return filtered.slice(0, 3);

  const eventCounts = new Map<string, number>();
  const balanced = filtered.filter((pick) => {
    const count = eventCounts.get(pick.event) ?? 0;
    if (count >= 3) return false;
    eventCounts.set(pick.event, count + 1);
    return true;
  });
  const visible = balanced.slice(0, 3);

  if (picks.some((pick) => pick.market === "tennis") && !visible.some((pick) => pick.market === "tennis")) {
    const tennisPick = picks.find((pick) => pick.market === "tennis");
    if (tennisPick) {
      if (visible.length === 3) visible[2] = tennisPick;
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
    <section aria-labelledby="todays-edge-heading" className={styles.edge}>
      <header className={styles.heading}>
        <div>
          <p className={styles.eyebrow}>Published selections</p>
          <h2 id="todays-edge-heading">Today&apos;s Edge</h2>
          <span className={styles.active}><span aria-hidden="true" />{picks.length} active {picks.length === 1 ? "pick" : "picks"}</span>
        </div>
        <div className={styles.profit}>
          <span>Last 7 days</span>
          <strong className={last7Profit != null && last7Profit < 0 ? styles.negative : ""}>
            {last7Profit == null ? "—" : `${last7Profit >= 0 ? "+" : ""}${last7Profit.toFixed(2)}u`}
          </strong>
          <small>Settled profit</small>
        </div>
      </header>

      <div className={styles.filters} role="group" aria-label="Filter active picks">
        {([
          ["all", "All picks"], ["props", "Football"], ["tennis", "Tennis"],
        ] as const).map(([id, label]) => (
          <button key={id} type="button" aria-pressed={filter === id}
            aria-label={`${label}, ${counts[id]} active ${counts[id] === 1 ? "pick" : "picks"}`}
            onClick={() => setActiveFilter(id)}>
            <SportIcon sport={id === "props" ? "football" : id === "tennis" ? "tennis" : "all"} className={styles.filterIcon} />
            <span>{label}</span>
            <small>{counts[id] ? `${counts[id]} ${counts[id] === 1 ? "pick" : "picks"}` : "No active picks"}</small>
          </button>
        ))}
      </div>

      <div aria-live="polite" aria-atomic="true">
        {visible.length > 0 ? (
          <div className={styles.picks}>
            {visible.map((pick) => (
              <TrackedLink key={pick.id} href={publicTipPath(pick)}
                eventName="homepage_to_pick_click"
                eventParams={{ bet_id: pick.id, market: pick.market, source: "todays_edge" }}
                className={styles.pick}>
                <div className={styles.pickHeading}>
                  <span className={styles.sportBadge}>
                    <MarketBadge market={pick.market} category={pick.category} event={pick.event} showLabel compact />
                    <span className={styles.date}>· {dateChip(pick.match_date)}</span>
                  </span>
                  <span className={styles.open} aria-hidden="true">↗</span>
                </div>
                <h3>{pick.event}</h3>
                <p className={styles.selection}>{pick.player ? `${pick.player} · ` : ""}{pick.selection}</p>
                <div className={styles.priceRow}>
                  <div><small>Recorded odds</small><strong>{formatOdds(pick.odds)}</strong></div>
                  <div className={styles.stake}><small>Stake</small><strong>{formatStake(pick.stake)}<span>u</span></strong></div>
                  <div className={styles.bookmaker}><BookmakerLogo bookmaker={pick.bookmaker} size="sm" noLink /></div>
                </div>
                <div className={styles.pickFooter}><time dateTime={pick.posted_at}>{publishedTime(pick.posted_at)}</time><span>View tip →</span></div>
              </TrackedLink>
            ))}
          </div>
        ) : (
          <div className={styles.empty}>
            <SportIcon sport={filter === "props" ? "football" : filter === "tennis" ? "tennis" : "all"} className="h-10 w-10" />
            <p>{filter === "all" ? "No active selections" : `No active ${filter === "props" ? "football" : "tennis"} picks`}</p>
            <span>New selections appear here when published. You can still browse past picks and results.</span>
          </div>
        )}
      </div>

      <footer className={styles.footer}>
        <TrackedLink href={fullCardHref}
          eventName={fullCardHref === "/track-record" ? "track_record_click" : "today_edge_open_full_card"}
          eventParams={{ source: "todays_edge", filter }} className={styles.fullCard}>
          {fullCardHref === "/track-record" ? "See the public record" : filter === "props" ? "All football picks" : filter === "tennis" ? "All tennis picks" : "Open full card"}<span aria-hidden="true">→</span>
        </TrackedLink>
        {lastSettled ? <p className={styles.lastSettled}><span>Last settled</span> {lastSettled.event} <b className={Number(lastSettled.profit_loss) < 0 ? styles.negative : ""}>{Number(lastSettled.profit_loss) >= 0 ? "+" : ""}{Number(lastSettled.profit_loss || 0).toFixed(2)}u</b></p> : null}
      </footer>
    </section>
  );
}
