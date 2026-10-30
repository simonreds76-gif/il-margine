"use client";

import SportIcon from "@/components/SportIcon";
import MarketBadge from "@/components/MarketBadge";
import { useEffect, useMemo, useState } from "react";
import BookmakerLogo from "@/components/BookmakerLogo";
import styles from "./TodaysEdge.module.css";
import TrackedLink from "@/components/TrackedLink";
import type { Bet, Bookmaker } from "@/lib/supabase";
import { formatOdds, formatStake } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";
import { track } from "@/lib/analytics";
import TipPortraits from "@/components/TipPortraits";
import type { TipPortrait } from "@/lib/tip-artwork-types";

type EdgeBet = Bet & {
  bookmaker?: Bookmaker | Bookmaker[] | null;
  artwork?: TipPortrait[];
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
  timeZoneName: "short",
});

const publishedDate = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London", day: "numeric", month: "short", year: "numeric",
});

function dateChip(value: string | null, today: string | null): string {
  if (!value) return "Date TBC";
  const date = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return "Date TBC";
  if (!today) return londonDate.format(date);
  const days = Math.round((date.getTime() - Date.parse(`${today}T12:00:00Z`)) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return londonDate.format(date);
}

function publishedTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Published"
    : `Posted ${publishedDate.format(date)} · ${londonTime.format(date)}`;
}

function selectVisiblePicks(picks: EdgeBet[], filter: Filter, today: string | null): EdgeBet[] {
  const filtered = picks
    .filter((pick) => (filter === "all" || pick.market === filter)
      && (!today || !pick.match_date || pick.match_date >= today))
    .sort((a, b) => (a.match_date || "9999").localeCompare(b.match_date || "9999")
      || b.posted_at.localeCompare(a.posted_at)
      || String(b.id).localeCompare(String(a.id)));
  const visible = filtered.slice(0, 3);
  // Keep sport variety only within the same day, never at today's expense.
  if (filter === "all" && !visible.some((pick) => pick.market === "tennis")) {
    const tennis = filtered.find((pick) => pick.market === "tennis");
    if (tennis && visible.length === 3 && tennis.match_date === visible[2].match_date) {
      visible[2] = tennis;
    }
  }
  return visible;
}

export default function TodaysEdge({ picks, lastSettled = null, last7Profit = null }: TodaysEdgeProps) {
  const [filter, setFilter] = useState<Filter>("all");
  // Cached HTML and the first client render use the same absolute date.
  // Relative labels then follow the London calendar, including overnight tabs.
  const [today, setToday] = useState<string | null>(null);
  useEffect(() => {
    const updateDay = () => setToday(new Intl.DateTimeFormat("en-CA", {
      timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit",
    }).format(new Date()));
    const initial = window.setTimeout(updateDay, 0);
    const timer = window.setInterval(updateDay, 60_000);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, []);
  const counts = useMemo(
    () => ({
      all: picks.length,
      props: picks.filter((pick) => pick.market === "props").length,
      tennis: picks.filter((pick) => pick.market === "tennis").length,
    }),
    [picks],
  );
  const visible = useMemo(() => selectVisiblePicks(picks, filter, today), [filter, picks, today]);
  const cardRoutes = filter === "all" && counts.props > 0 && counts.tennis > 0
    ? [
        { href: "/player-props#picks", label: `Football picks (${counts.props})`, filter: "props" },
        { href: "/tennis-tips#picks", label: `Tennis picks (${counts.tennis})`, filter: "tennis" },
      ]
    : filter === "props" || (filter === "all" && counts.props > 0)
      ? [{ href: "/player-props#picks", label: "All football picks", filter: "props" }]
      : filter === "tennis" || counts.tennis > 0
        ? [{ href: "/tennis-tips#picks", label: "All tennis picks", filter: "tennis" }]
        : [{ href: "/track-record", label: "See the public record", filter: "all" }];

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
          {picks.length > 0 && <span className={styles.active}><span aria-hidden="true" />{picks.length} active {picks.length === 1 ? "pick" : "picks"}</span>}
        </div>
        <div className={styles.profit}>
          <span>Last 7 days</span>
          <strong className={last7Profit != null && last7Profit < 0 ? styles.negative : ""}>
            {last7Profit == null ? "—" : `${last7Profit >= 0 ? "+" : ""}${last7Profit.toFixed(2)}u`}
          </strong>
          <small>Settled profit</small>
        </div>
      </header>

      {picks.length > 0 && <div className={styles.filters} role="group" aria-label="Filter active picks">
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
      </div>}

      <div aria-live="polite" aria-atomic="true">
        {visible.length > 0 ? (
          <div className={styles.picks}>
            {visible.map((pick) => (
              <TrackedLink key={pick.id} href={publicTipPath(pick)}
                prefetch={false}
                eventName="homepage_to_pick_click"
                eventParams={{ bet_id: pick.id, market: pick.market, source: "todays_edge" }}
                className={styles.pick}>
                <div className={styles.pickHeading}>
                  <span className={styles.sportBadge}>
                    <MarketBadge market={pick.market} category={pick.category} event={pick.event} showLabel compact />
                    <span className={styles.date}>· {dateChip(pick.match_date, today)}</span>
                  </span>
                  <span className={styles.open} aria-hidden="true">↗</span>
                </div>
                <div className={styles.identityRow}>
                  <TipPortraits portraits={pick.artwork} />
                  <div className={styles.pickText}>
                    <h3>{pick.event}</h3>
                    <p className={styles.selection}>{pick.player ? `${pick.player.trim()} · ` : ""}{pick.selection}</p>
                  </div>
                </div>
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
            <p>{picks.length === 0 || filter === "all" ? "No active selections right now" : `No active ${filter === "props" ? "football" : "tennis"} picks`}</p>
            <span>New picks appear here when published. Explore the latest results below.</span>
          </div>
        )}
      </div>

      <footer className={styles.footer}>
        <div className={cardRoutes.length > 1 ? styles.cardRoutes : undefined}>
          {cardRoutes.map((route) => <TrackedLink key={route.href} href={route.href}
            eventName={route.href === "/track-record" ? "track_record_click" : "today_edge_open_full_card"}
            eventParams={{ source: "todays_edge", filter: route.filter }} className={styles.fullCard}>
            {route.label}<span aria-hidden="true">&#8594;</span>
          </TrackedLink>)}
        </div>
        {lastSettled ? <p className={styles.lastSettled}><span>Last settled</span> {lastSettled.event} <b className={Number(lastSettled.profit_loss) < 0 ? styles.negative : ""}>{Number(lastSettled.profit_loss) >= 0 ? "+" : ""}{Number(lastSettled.profit_loss || 0).toFixed(2)}u</b></p> : null}
      </footer>
    </section>
  );
}
