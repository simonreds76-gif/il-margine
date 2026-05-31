"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { track } from "@/lib/analytics";

const MODAL_STORAGE_KEY = "ilm_wc_telegram_modal_closed_v1";
const BAR_STORAGE_KEY = "ilm_wc_telegram_bar_closed_v1";
const COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000;

function recentlyClosed(key: string): boolean {
  if (typeof window === "undefined") return true;
  const raw = window.localStorage.getItem(key);
  if (!raw) return false;
  const lastClosed = Number(raw);
  return Number.isFinite(lastClosed) && Date.now() - lastClosed < COOLDOWN_MS;
}

function rememberClosed(key: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, String(Date.now()));
}

function TelegramCta({
  source,
  children,
  className,
}: {
  source: string;
  children: React.ReactNode;
  className: string;
}) {
  return (
    <Link
      href={`/go/world-cup-telegram?source=${encodeURIComponent(source)}`}
      onClick={() => track("world_cup_telegram_cta_click", { source })}
      className={className}
    >
      {children}
    </Link>
  );
}

export default function WorldCupTelegramOverlay() {
  const pathname = usePathname();
  const [showModal, setShowModal] = useState(false);
  const [showBar, setShowBar] = useState(false);

  useEffect(() => {
    setShowBar(!recentlyClosed(BAR_STORAGE_KEY));

    if (recentlyClosed(MODAL_STORAGE_KEY)) {
      return;
    }

    let triggered = false;
    const openModal = (trigger: string) => {
      if (triggered || recentlyClosed(MODAL_STORAGE_KEY)) return;
      triggered = true;
      track("world_cup_telegram_modal_view", { trigger, path: pathname });
      setShowModal(true);
    };

    const onScroll = () => {
      const doc = document.documentElement;
      const maxScroll = doc.scrollHeight - window.innerHeight;
      if (maxScroll <= 0) return;
      if (window.scrollY / maxScroll >= 0.45) {
        openModal("scroll_45");
      }
    };

    const onMouseLeave = (event: MouseEvent) => {
      if (event.clientY <= 0) {
        openModal("exit_intent");
      }
    };

    const timer = window.setTimeout(() => openModal("time_18s"), 18000);
    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("mouseleave", onMouseLeave);

    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("mouseleave", onMouseLeave);
    };
  }, [pathname]);

  const closeModal = () => {
    rememberClosed(MODAL_STORAGE_KEY);
    setShowModal(false);
  };

  const closeBar = () => {
    rememberClosed(BAR_STORAGE_KEY);
    setShowBar(false);
  };

  return (
    <>
      {showBar ? (
        <div className="fixed inset-x-3 bottom-3 z-[70] mx-auto max-w-4xl rounded-2xl border border-emerald-400/25 bg-slate-950/95 p-3 shadow-[0_22px_80px_rgba(0,0,0,0.45)] backdrop-blur sm:bottom-4 sm:p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-100">Free World Cup picks on Telegram</div>
              <div className="mt-1 text-xs leading-5 text-slate-400">
                Goalscorer angles, player props, penalty-taker updates and late team-news spots.
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <TelegramCta
                source="sticky_bar"
                className="rounded-full bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
              >
                Join Free
              </TelegramCta>
              <button
                type="button"
                onClick={closeBar}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-700 text-slate-400 transition hover:border-slate-500 hover:text-slate-100"
                aria-label="Close Telegram prompt"
              >
                x
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showModal ? (
        <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/62 px-3 pb-4 pt-10 backdrop-blur-sm sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-labelledby="world-cup-telegram-title">
          <button type="button" className="absolute inset-0 cursor-default" aria-label="Close Telegram prompt" onClick={closeModal} />
          <div className="relative w-full max-w-lg overflow-hidden rounded-[28px] border border-emerald-400/25 bg-[linear-gradient(150deg,rgba(6,18,15,0.98),rgba(10,13,22,0.98))] p-5 shadow-[0_30px_100px_rgba(0,0,0,0.58)] sm:p-6">
            <button
              type="button"
              onClick={closeModal}
              className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300 transition hover:bg-white/10 hover:text-white"
              aria-label="Close"
            >
              x
            </button>
            <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-emerald-400/12 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-20 left-10 h-44 w-44 rounded-full bg-amber-400/10 blur-3xl" />
            <div className="relative">
              <div className="inline-flex rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-200">
                Telegram channel
              </div>
              <h2 id="world-cup-telegram-title" className="mt-4 text-3xl font-semibold tracking-tight text-slate-100">
                Free World Cup 2026 picks.
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-300">
                Join the Il Margine Telegram for goalscorer angles, player props, penalty-taker swings and big-market value spots through the tournament.
              </p>
              <div className="mt-5 grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">Goalscorer angles</div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">Player props</div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">Penalty updates</div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">Late team news</div>
              </div>
              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <TelegramCta
                  source="modal"
                  className="inline-flex items-center justify-center rounded-full bg-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
                >
                  Join Free on Telegram
                </TelegramCta>
                <Link
                  href="/world-cup-2026-free-picks"
                  onClick={() => track("world_cup_telegram_landing_click", { source: "modal" })}
                  className="inline-flex items-center justify-center rounded-full border border-slate-700 px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white"
                >
                  See what is inside
                </Link>
              </div>
              <p className="mt-4 text-xs leading-5 text-slate-500">
                Free during the tournament. No lottery acca spam.
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
