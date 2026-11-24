"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import styles from "./board.module.css";

const minute = 60_000;

export function RefreshBoard({ seen, loadedAt, liveDay, failed }: {
  seen: number | null;
  loadedAt: number;
  liveDay?: string;
  failed: boolean;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [lastCheck, setLastCheck] = useState<{ seen: number | null; loadedAt: number } | null>(null);
  const [cooling, setCooling] = useState(false);
  const nextClick = useRef(0);
  const rolledDay = useRef<string | null>(null);
  const [expiredScan, setExpiredScan] = useState<number | null>(null);

  useEffect(() => {
    if (!cooling) return;
    const timer = window.setTimeout(() => setCooling(false), Math.max(0, nextClick.current - Date.now()));
    return () => window.clearTimeout(timer);
  }, [cooling]);

  // Only the UTC date change can refresh an unattended visible board. Returning
  // from sleep also checks the date; the age indicator itself never fetches.
  useEffect(() => {
    if (!liveDay) return;
    const midnight = Date.parse(liveDay + "T00:00:00Z") + 86_400_000;
    const expires = seen === null ? Infinity : seen + 40 * minute;
    const wall = Date.now(), mono = performance.now();
    let timer: number | undefined;
    function check() {
      window.clearTimeout(timer);
      if (document.visibilityState !== "visible") return;
      const now = loadedAt + Math.max(0, Date.now() - wall, performance.now() - mono);
      if (now >= expires) setExpiredScan(seen);
      if (now >= midnight) {
        if (rolledDay.current !== liveDay) {
          const wait = nextClick.current - Date.now();
          if (wait > 0) { timer = window.setTimeout(check, wait + 25); return; }
          rolledDay.current = liveDay ?? null;
          startTransition(() => router.refresh());
        }
        return;
      }
      timer = window.setTimeout(check, Math.min(midnight, expires > now ? expires : Infinity) - now + 25);
    }
    check();
    document.addEventListener("visibilitychange", check);
    window.addEventListener("pageshow", check);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", check);
      window.removeEventListener("pageshow", check);
    };
  }, [liveDay, seen, loadedAt, router]);

  function refresh() {
    if (pending || Date.now() < nextClick.current) return;
    nextClick.current = Date.now() + minute;
    setLastCheck({ seen, loadedAt });
    setCooling(true);
    startTransition(() => router.refresh());
  }

  const stale = liveDay && seen !== null && (loadedAt >= seen + 40 * minute || expiredScan === seen);
  const checked = lastCheck && !pending && loadedAt !== lastCheck.loadedAt;
  const shown = seen === null ? "" : new Date(seen).toISOString();
  return <div className={styles.scanBar}>
    <p className={styles.fresh} data-late={stale || failed ? "true" : undefined} role="status">
      {failed ? "Couldn’t load the saved scan." : shown
        ? <>Latest scan <time dateTime={shown}>{shown.slice(0, 16).replace("T", " ")} UTC</time>{stale ? " · over 40 minutes ago" : ""}</>
        : "No scan available."}
      {checked && !failed && seen !== null && <span> · {seen === lastCheck.seen ? "No newer scan" : "Updated"}</span>}
    </p>
    <button className={styles.refreshButton} type="button" disabled={pending || cooling}
      title={cooling && !pending ? "Available again one minute after your last check" : "Load the latest saved board"}
      onClick={refresh}>
      <svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M20 4v6h-6M19.3 9a8 8 0 1 0 .1 6"/></svg>
      {pending ? "Checking…" : "Refresh"}
    </button>
  </div>;
}
