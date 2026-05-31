"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
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
              <div className="text-sm font-semibold text-slate-100">Join the free WC Telegram page</div>
              <div className="mt-1 text-xs leading-5 text-slate-400">
                Model-driven World Cup picks, props, goalscorer angles and penalty-taker updates.
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <TelegramCta
                source="sticky_bar"
                className="inline-flex items-center gap-2 rounded-full bg-[#2AABEE] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#229ED9]"
              >
                <TelegramIcon className="h-4 w-4" />
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
        <div
          className="fixed inset-0 z-[80] flex items-end justify-center bg-black/68 px-3 pb-4 pt-10 backdrop-blur-sm sm:items-center sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="world-cup-telegram-title"
          onClick={closeModal}
        >
          <div
            className="relative w-full max-w-[580px] overflow-hidden rounded-[30px] border border-emerald-400/25 bg-[linear-gradient(150deg,rgba(5,16,14,0.98),rgba(9,12,20,0.98))] p-5 shadow-[0_30px_100px_rgba(0,0,0,0.58)] sm:p-6"
            onClick={(event) => event.stopPropagation()}
          >
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
              <div className="grid gap-5 sm:grid-cols-[120px,1fr] sm:items-center">
                <div className="mx-auto w-28 rounded-[24px] border border-emerald-400/25 bg-slate-950/70 p-2 shadow-[0_16px_48px_rgba(0,0,0,0.35)] sm:mx-0">
                  <Image
                    src="/brand/world-cup-2026-free-picks.png"
                    alt="Il Margine World Cup 2026 free picks"
                    width={1024}
                    height={1024}
                    sizes="112px"
                    className="h-auto w-full rounded-[18px]"
                  />
                </div>
                <div>
                  <div className="inline-flex rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-200">
                    Free Telegram channel
                  </div>
                  <h2 id="world-cup-telegram-title" className="mt-3 text-3xl font-semibold tracking-tight text-slate-100">
                    Join our World Cup picks page.
                  </h2>
                  <p className="mt-3 text-sm leading-7 text-slate-300">
                    Model-driven picks throughout the tournament: goalscorers, player props, penalty-taker swings and big-market value spots.
                  </p>
                </div>
              </div>
              <div className="mt-5 grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">Goalscorer angles</div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">Player props</div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">Penalty updates</div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">Market notes</div>
              </div>
              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <TelegramCta
                  source="modal"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-[#2AABEE] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#229ED9]"
                >
                  <TelegramIcon className="h-4 w-4" />
                  Join Free on Telegram
                </TelegramCta>
                <Link
                  href="/world-cup-2026-free-picks"
                  onClick={() => {
                    rememberClosed(MODAL_STORAGE_KEY);
                    setShowModal(false);
                    track("world_cup_telegram_landing_click", { source: "modal" });
                  }}
                  className="inline-flex items-center justify-center rounded-full border border-slate-700 px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white"
                >
                  See what is inside
                </Link>
              </div>
              <p className="mt-4 text-xs leading-5 text-slate-500">
                Free throughout the tournament. Fast posts when prices, team news or player roles move.
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
