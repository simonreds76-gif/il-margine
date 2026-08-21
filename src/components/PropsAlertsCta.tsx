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
        prefetch={false}
        target="_blank"
        rel="noopener noreferrer"
        eventName="player_props_telegram_click"
        eventParams={{ source }}
        className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[var(--brand-green)] px-6 py-3 text-base font-semibold text-[#050807] transition-all hover:brightness-110 hover:shadow-[0_0_40px_rgba(87,209,150,0.22)] ${className}`}
      >
        <TelegramIcon />
        Football player-prop alerts
      </TrackedLink>
    );
  }

  return (
    <div className={`overflow-hidden rounded-2xl border border-[rgba(87,209,150,0.22)] bg-[linear-gradient(135deg,rgba(87,209,150,0.10),rgba(9,13,19,0.94)_55%)] p-5 sm:p-6 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 flex-[1_1_22rem] items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[rgba(87,209,150,0.25)] bg-[rgba(87,209,150,0.08)] text-[#229ED9]">
            <TelegramIcon className="h-6 w-6" />
          </div>
          <div className="min-w-0">
            <h2 className="font-semibold leading-6 text-slate-100">Football player-prop alerts, free on Telegram</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-400">
              Selected football player-prop picks, sent when we post them with the odds, stake and a link to the full pick. Tennis picks and the full public record stay on the site.
            </p>
          </div>
        </div>
        <TrackedLink
          href={href}
          prefetch={false}
          target="_blank"
          rel="noopener noreferrer"
          eventName="player_props_telegram_click"
          eventParams={{ source }}
          className="inline-flex min-h-11 w-full max-w-full shrink-0 items-center justify-center rounded-xl bg-[var(--brand-green)] px-5 py-3 text-sm font-semibold text-[#050807] transition hover:brightness-110 sm:w-auto"
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
