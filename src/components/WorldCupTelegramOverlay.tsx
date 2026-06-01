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
      if (window.matchMedia("(pointer: coarse)").matches) return;
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

  useEffect(() => {
    if (!showModal || typeof window === "undefined") return;

    const scrollY = window.scrollY;
    const previousStyles = {
      overflow: document.body.style.overflow,
      position: document.body.style.position,
      top: document.body.style.top,
      width: document.body.style.width,
    };

    document.body.style.overflow = "hidden";
    document.body.style.position = "fixed";
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = "100%";

    return () => {
      document.body.style.overflow = previousStyles.overflow;
      document.body.style.position = previousStyles.position;
      document.body.style.top = previousStyles.top;
      document.body.style.width = previousStyles.width;
      window.scrollTo(0, scrollY);
    };
  }, [showModal]);

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
        <div className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-[70] mx-auto max-w-4xl rounded-2xl border border-emerald-400/25 bg-slate-950/95 p-3 shadow-[0_22px_80px_rgba(0,0,0,0.45)] backdrop-blur sm:bottom-4 sm:p-4">
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
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/68 p-3 backdrop-blur-sm sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="world-cup-telegram-title"
          onClick={closeModal}
        >
          <div
            className="relative max-h-[calc(100dvh-1.5rem)] w-full max-w-[580px] overflow-y-auto overscroll-contain rounded-[26px] border border-emerald-400/25 bg-[linear-gradient(150deg,rgba(5,16,14,0.98),rgba(9,12,20,0.98))] p-4 shadow-[0_30px_100px_rgba(0,0,0,0.58)] sm:max-h-[calc(100vh-3rem)] sm:rounded-[30px] sm:p-6"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              onClick={closeModal}
              className="absolute right-3 top-3 z-30 flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-slate-950/70 text-slate-200 shadow-lg shadow-black/25 transition hover:bg-white/10 hover:text-white sm:right-4 sm:top-4"
              aria-label="Close"
            >
              x
            </button>
            <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-emerald-400/12 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-20 left-10 h-44 w-44 rounded-full bg-amber-400/10 blur-3xl" />
            <div className="relative z-10">
              <div className="grid grid-cols-[76px,1fr] items-center gap-3 sm:grid-cols-[120px,1fr] sm:gap-5">
                <div className="w-16 rounded-[18px] border border-emerald-400/25 bg-slate-950/70 p-1.5 shadow-[0_16px_48px_rgba(0,0,0,0.35)] sm:w-28 sm:rounded-[24px] sm:p-2">
                  <Image
                    src="/brand/world-cup-2026-free-picks.png"
                    alt="Il Margine World Cup 2026 free picks"
                    width={1024}
                    height={1024}
                    sizes="112px"
                    className="h-auto w-full rounded-[13px] sm:rounded-[18px]"
                  />
                </div>
                <div className="pr-10 sm:pr-11">
                  <div className="inline-flex rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-200">
                    Free Telegram channel
                  </div>
                  <h2 id="world-cup-telegram-title" className="mt-2 text-2xl font-semibold leading-tight tracking-tight text-slate-100 sm:mt-3 sm:text-3xl">
                    Join our World Cup picks page.
                  </h2>
                  <p className="mt-2 text-[13px] leading-6 text-slate-300 sm:mt-3 sm:text-sm sm:leading-7">
                    Model-driven picks throughout the tournament: goalscorers, player props, penalty-taker swings and big-market value spots.
                  </p>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-300 sm:mt-5 sm:text-sm">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-2.5 sm:p-3">Goalscorer angles</div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-2.5 sm:p-3">Player props</div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-2.5 sm:p-3">Penalty updates</div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-2.5 sm:p-3">Market notes</div>
              </div>
              <p className="mt-4 text-xs leading-5 text-slate-500">
                Free throughout the tournament. Fast posts when prices, team news or player roles move.
              </p>
              <div className="sticky bottom-0 z-20 -mx-4 mt-4 flex flex-col gap-2 border-t border-slate-800/80 bg-[linear-gradient(180deg,rgba(5,16,14,0.78),rgba(5,16,14,0.98)_28%)] px-4 pb-1 pt-3 backdrop-blur sm:static sm:mx-0 sm:mt-6 sm:flex-row sm:border-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-0">
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
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
