"use client";

import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { SCAN_VALIDITY_MINUTES, SCAN_VALIDITY_MS } from "./desk";
import styles from "./board.module.css";

const minute = 60_000;
export const DESK_REFRESH_EVENT = "desk:manual-refresh";
export const DESK_REFRESH_STATE_EVENT = "desk:refresh-state";

export function RefreshBoard({ seen, loadedAt, liveDay, isToday, failed, jumpHref }: {
  seen: number | null;
  loadedAt: number;
  liveDay?: string;
  isToday?: boolean;
  failed: boolean;
  jumpHref?: string;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [lastCheck, setLastCheck] = useState<{ seen: number | null; loadedAt: number } | null>(null);
  const [cooling, setCooling] = useState(false);
  const nextClick = useRef(0);
  const rolledDay = useRef<string | null>(null);
  const [expiredScan, setExpiredScan] = useState<number | null>(null);
  const currentBoard = isToday ?? Boolean(liveDay);

  useEffect(() => {
    if (!cooling) return;
    const timer = window.setTimeout(() => setCooling(false), Math.max(0, nextClick.current - Date.now()));
    return () => window.clearTimeout(timer);
  }, [cooling]);

  // Only the UTC date change can refresh an unattended visible board. Returning
  // from sleep also checks the date; the age indicator itself never fetches.
  useEffect(() => {
    if (!currentBoard && !liveDay) return;
    const midnight = liveDay ? Date.parse(liveDay + "T00:00:00Z") + 86_400_000 : Infinity;
    const expires = currentBoard && seen !== null ? seen + SCAN_VALIDITY_MS : Infinity;
    const wall = Date.now(), mono = performance.now();
    let timer: number | undefined;
    function check() {
      window.clearTimeout(timer);
      if (document.visibilityState !== "visible") return;
      const serverTime = loadedAt + Math.max(0, Date.now() - wall, performance.now() - mono);
      const now = Math.max(Date.now(), serverTime);
      if (now >= expires && seen !== null) setExpiredScan(seen);
      if (liveDay && serverTime >= midnight) {
        if (rolledDay.current !== liveDay) {
          const wait = nextClick.current - Date.now();
          if (wait > 0) { timer = window.setTimeout(check, wait + 25); return; }
          rolledDay.current = liveDay;
          startTransition(() => router.refresh());
        }
        return;
      }
      const untilExpiry = expires > now ? expires - now : Infinity;
      const untilMidnight = liveDay && midnight > serverTime ? midnight - serverTime : Infinity;
      const nextDelay = Math.min(untilExpiry, untilMidnight);
      if (Number.isFinite(nextDelay)) timer = window.setTimeout(check, Math.max(50, nextDelay + 25));
    }
    check();
    document.addEventListener("visibilitychange", check);
    window.addEventListener("pageshow", check);
    window.addEventListener("focus", check);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", check);
      window.removeEventListener("pageshow", check);
      window.removeEventListener("focus", check);
    };
  }, [currentBoard, liveDay, seen, loadedAt, router]);

  const refresh = useCallback(() => {
    if (pending || Date.now() < nextClick.current) return;
    nextClick.current = Date.now() + minute;
    setLastCheck({ seen, loadedAt });
    setCooling(true);
    startTransition(() => router.refresh());
  }, [pending, seen, loadedAt, router]);

  useEffect(() => {
    const onRequest = () => refresh();
    window.addEventListener(DESK_REFRESH_EVENT, onRequest);
    return () => window.removeEventListener(DESK_REFRESH_EVENT, onRequest);
  }, [refresh]);

  useEffect(() => {
    window.dispatchEvent(new CustomEvent(DESK_REFRESH_STATE_EVENT, { detail: { pending, cooling } }));
  }, [pending, cooling]);

  const stale = currentBoard && !failed && seen !== null && (loadedAt >= seen + SCAN_VALIDITY_MS || expiredScan === seen);
  const checked = lastCheck && !pending && loadedAt !== lastCheck.loadedAt;
  const shown = seen === null ? "" : new Date(seen).toISOString();
  const state = failed ? "failed" : seen === null ? "empty" : stale ? "late" : "fresh";
  return <div className={styles.scanBar}>
    <p className={styles.fresh} data-state={state} data-late={stale || failed ? "true" : undefined} role="status">
      {failed ? "Couldn’t load the saved board · scan check failed." : shown
        ? <>Latest scan <time dateTime={shown}><span className={currentBoard ? styles.scanDay : undefined}>{shown.slice(0, 10)} </span>{shown.slice(11, 16)} UTC</time>{stale ? ` · over ${SCAN_VALIDITY_MINUTES} minutes ago — pre-match listings paused` : ""}</>
        : (currentBoard ? "No saved scan recorded yet today." : "No saved scan recorded for this date.")}
      {checked && !failed && seen !== null && <span> · {seen === lastCheck.seen ? "No newer scan" : "Updated"}</span>}
    </p>
    <div className={styles.scanActions}>
      {jumpHref && <a className={styles.upcomingJump} href={jumpHref}>Upcoming<span className={styles.jumpWord}> matches</span> <span aria-hidden="true">↓</span></a>}
      <button id="desk-refresh-button" className={styles.refreshButton} type="button" disabled={pending || cooling}
        title={cooling && !pending ? "Available again one minute after your last check" : "Load the latest saved board"}
        onClick={refresh}>
        <svg aria-hidden="true" focusable="false" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M20 4v6h-6M19.3 9a8 8 0 1 0 .1 6"/></svg>
        {pending ? "Checking…" : "Refresh"}
      </button>
    </div>
  </div>;
}
