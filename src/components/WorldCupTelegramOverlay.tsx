"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { track } from "@/lib/analytics";

const BAR_STORAGE_KEY = "ilm_wc_archive_bar_closed_v1";
const COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000;

function recentlyClosed(): boolean {
  if (typeof window === "undefined") return true;
  const raw = window.localStorage.getItem(BAR_STORAGE_KEY);
  if (!raw) return false;
  const lastClosed = Number(raw);
  return Number.isFinite(lastClosed) && Date.now() - lastClosed < COOLDOWN_MS;
}

function rememberClosed() {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(BAR_STORAGE_KEY, String(Date.now()));
}

function TelegramIcon({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M21.6 4.1 18.2 20c-.2 1.1-.9 1.4-1.8.9l-5.1-3.8-2.5 2.4c-.3.3-.5.5-1 .5l.4-5.2 9.5-8.6c.4-.4-.1-.6-.6-.2L5.3 13.4.2 11.8c-1.1-.3-1.1-1.1.2-1.6L20.3 2.6c.9-.4 1.7.2 1.3 1.5Z"
      />
    </svg>
  );
}

export default function WorldCupTelegramOverlay() {
  const [showBar, setShowBar] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setShowBar(!recentlyClosed()), 0);
    return () => window.clearTimeout(timer);
  }, []);

  if (!showBar) return null;

  return (
    <div className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-[70] mx-auto max-w-4xl rounded-2xl border border-emerald-400/25 bg-slate-950/95 p-3 shadow-[0_22px_80px_rgba(0,0,0,0.45)] backdrop-blur sm:bottom-4 sm:p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-100">World Cup 2026: every pick stays on the record</div>
          <div className="mt-1 text-xs leading-5 text-slate-400">
            The channel continues with ATP tennis and football player props. Join free.
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Link
            href="/go/telegram?source=wc_sticky_post"
            prefetch={false}
            onClick={() => track("world_cup_telegram_cta_click", { source: "wc_sticky_post" })}
            className="inline-flex items-center gap-2 rounded-full bg-[#2AABEE] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#229ED9]"
          >
            <TelegramIcon className="h-4 w-4" />
            Join Free
          </Link>
          <button
            type="button"
            onClick={() => {
              rememberClosed();
              setShowBar(false);
            }}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-700 text-slate-400 transition hover:border-slate-500 hover:text-slate-100"
            aria-label="Close Telegram prompt"
          >
            x
          </button>
        </div>
      </div>
    </div>
  );
}
