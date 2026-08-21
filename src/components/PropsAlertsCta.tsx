"use client";

import TrackedLink from "@/components/TrackedLink";

type PropsAlertsCtaProps = {
  source: string;
  variant?: "card" | "pill";
  className?: string;
};

export default function PropsAlertsCta({
  source,
  variant = "card",
  className = "",
}: PropsAlertsCtaProps) {
  const href = `/go/telegram?source=${encodeURIComponent(source)}`;

  if (variant === "pill") {
    return (
      <TrackedLink
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        eventName="player_props_telegram_click"
        eventParams={{ source }}
        className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-sky-300/30 bg-[#0b1720]/95 px-4 py-2 text-sm font-semibold text-sky-100 shadow-xl shadow-black/25 backdrop-blur transition hover:border-sky-300/55 hover:bg-sky-400/15 ${className}`}
      >
        <TelegramIcon />
        Free props alerts
      </TrackedLink>
    );
  }

  return (
    <div className={`overflow-hidden rounded-2xl border border-sky-400/20 bg-[linear-gradient(135deg,rgba(56,189,248,0.10),rgba(8,15,24,0.92)_55%)] p-5 sm:p-6 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 flex-[1_1_22rem] items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-sky-400/25 bg-sky-400/10 text-sky-300">
            <TelegramIcon className="h-6 w-6" />
          </div>
          <div className="min-w-0">
            <h2 className="font-semibold leading-6 text-slate-100">Get football player-prop alerts</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-400">
              Selected free Telegram alerts include the posted odds, stake and a link to the full pick.
            </p>
          </div>
        </div>
        <TrackedLink
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          eventName="player_props_telegram_click"
          eventParams={{ source }}
          className="inline-flex min-h-11 w-full max-w-full shrink-0 items-center justify-center rounded-xl border border-sky-300/30 bg-sky-400/12 px-5 py-3 text-sm font-semibold text-sky-100 transition hover:border-sky-300/50 hover:bg-sky-400/20 sm:w-auto"
        >
          Join free alerts
        </TrackedLink>
      </div>
    </div>
  );
}

function TelegramIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="currentColor">
      <path d="M21.8 3.6 18.6 20c-.2 1.2-.9 1.5-1.9.9l-4.9-3.6-2.4 2.3c-.3.3-.5.5-1 .5l.4-5 9-8.1c.4-.4-.1-.6-.6-.2L6.1 13.8l-4.8-1.5c-1-.3-1-1 .2-1.5L20.3 3.5c.9-.3 1.7.2 1.5 1.1Z" />
    </svg>
  );
}
