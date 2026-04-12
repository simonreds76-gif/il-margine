import type { ReactNode } from "react";
import Link from "next/link";

export const MODEL_MONITOR_ENABLED =
  process.env.NODE_ENV !== "production" ||
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.MODEL_MONITOR_PUBLIC === "true" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "true" ||
  process.env.VERCEL_ENV === "preview";

export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return new Date(`${value}T00:00:00Z`);
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateLabel(value?: string | null): string {
  const date = parseDate(value);
  if (!date) return "-";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "Europe/London",
  }).format(date);
}

export function formatDateTimeLabel(value?: string | null): string {
  const date = parseDate(value);
  if (!date) return "-";
  const hasTime = Boolean(value && value.includes("T"));
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(hasTime ? { hour: "2-digit", minute: "2-digit" } : {}),
    timeZone: "Europe/London",
  }).format(date);
}

export function formatPct(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatOdds(value?: number | null, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return value.toFixed(digits);
}

export function formatUnits(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return `${value.toFixed(digits)}u`;
}

export function toneClass(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "text-slate-400";
  if (value > 0) return "text-emerald-400";
  if (value < 0) return "text-rose-400";
  return "text-slate-400";
}

export function actionTone(action?: string | null): string {
  const normalized = (action || "").toLowerCase();
  if (normalized.includes("surface") || normalized.includes("public"))
    return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (normalized.includes("shadow"))
    return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  if (normalized.includes("suppress") || normalized.includes("quarantine"))
    return "bg-rose-500/10 text-rose-300 border-rose-500/20";
  return "bg-slate-800/60 text-slate-400 border-slate-700/50";
}

export function statusTone(status?: string | null): string {
  const normalized = (status || "").toLowerCase();
  if (normalized.includes("won"))       return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (normalized.includes("lost"))      return "bg-rose-500/10 text-rose-300 border-rose-500/20";
  if (normalized.includes("void") || normalized.includes("push"))
    return "bg-slate-700/40 text-slate-400 border-slate-600/40";
  if (normalized.includes("done"))      return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (normalized.includes("dismissed")) return "bg-slate-700/40 text-slate-400 border-slate-600/40";
  if (normalized.includes("confirmed")) return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (normalized.includes("expected"))  return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  if (normalized.includes("quarantined")) return "bg-rose-500/10 text-rose-300 border-rose-500/20";
  if (normalized.includes("no feed") || normalized.includes("missing"))
    return "bg-slate-700/40 text-slate-400 border-slate-600/40";
  return "bg-cyan-500/10 text-cyan-300 border-cyan-500/20";
}

// ─── Internal icon ───────────────────────────────────────────────────────────

function ChevronDown() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

// ─── Atoms ──────────────────────────────────────────────────────────────────

export function StatusPill({ label, tone }: { label: string; tone: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]",
        tone,
      )}
    >
      {label}
    </span>
  );
}

/**
 * Phase separator — a thin rule + label used to divide phase groups inside
 * penalty review cards. An optional `aside` string appears right-aligned.
 */
export function PhaseLabel({ label, aside }: { label: string; aside?: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="shrink-0 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
        {label}
      </span>
      <div className="h-px flex-1 bg-slate-800" />
      {aside ? (
        <span className="shrink-0 text-[11px] tabular-nums text-slate-500">{aside}</span>
      ) : null}
    </div>
  );
}

// ─── Navigation ─────────────────────────────────────────────────────────────

export function MonitorNav({
  current,
}: {
  current: "tennis" | "goalscorer" | "lineups" | "team-shots" | "corners";
}) {
  const base =
    "inline-flex items-center rounded-full border border-slate-700/70 bg-slate-900/70 px-3 py-1.5 text-sm text-slate-400 transition-colors hover:border-slate-600 hover:text-slate-200";
  const active =
    "border-emerald-500/30 bg-emerald-500/8 text-emerald-200 hover:border-emerald-500/40 hover:text-emerald-100";
  return (
    <nav className="flex flex-wrap items-center gap-2">
      <Link href="/model-monitor" className={cn(base, current === "tennis" && active)}>
        Tennis
      </Link>
      <Link href="/model-monitor/goalscorer" className={cn(base, current === "goalscorer" && active)}>
        Goalscorer
      </Link>
      <Link href="/model-monitor/goalscorer/lineups" className={cn(base, current === "lineups" && active)}>
        Lineups
      </Link>
      <Link href="/model-monitor/team-shots" className={cn(base, current === "team-shots" && active)}>
        Team Shots
      </Link>
      <Link href="/model-monitor/corners" className={cn(base, current === "corners" && active)}>
        Corners
      </Link>
    </nav>
  );
}

// ─── Layout blocks ──────────────────────────────────────────────────────────

export function HeroCard({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(135deg,rgba(15,23,42,0.97),rgba(10,14,23,0.95))] px-6 py-6 sm:px-8 sm:py-8">
      <div className="mb-3 inline-flex items-center rounded-full border border-emerald-500/20 bg-emerald-500/8 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
        {eyebrow}
      </div>
      <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">{title}</h1>
      <div className="mt-3 text-sm leading-relaxed">{children}</div>
    </section>
  );
}

/**
 * SectionCard — titled content block.
 *
 * Set `collapsible` to wrap content in a `<details>` / `<summary>` pair.
 * Set `defaultOpen={false}` to render collapsed. Both props are backward-
 * compatible: existing callers without them get a plain non-collapsible card.
 */
export function SectionCard({
  title,
  subtitle,
  collapsible = false,
  defaultOpen = true,
  children,
}: {
  title: string;
  subtitle?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const shell =
    "rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] shadow-[0_8px_32px_rgba(0,0,0,0.28)]";

  if (collapsible) {
    return (
      <details open={defaultOpen} className={cn("group", shell)}>
        <summary className="flex cursor-pointer select-none list-none items-center justify-between gap-4 rounded-2xl px-5 py-4 transition-colors hover:bg-white/[0.02] marker:hidden group-open:rounded-b-none">
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-slate-100">{title}</h2>
            {subtitle ? (
              <p className="mt-0.5 truncate text-xs text-slate-500">{subtitle}</p>
            ) : null}
          </div>
          <span className="flex shrink-0 items-center justify-center rounded-full border border-slate-700/50 bg-slate-900/50 p-1 text-slate-500 transition-transform duration-200 group-open:rotate-180">
            <ChevronDown />
          </span>
        </summary>
        <div className="border-t border-slate-800/70 px-5 pb-5 pt-4">{children}</div>
      </details>
    );
  }

  return (
    <section className={cn(shell, "p-5")}>
      <div className="mb-4">
        <h2 className="text-[15px] font-semibold text-slate-100">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

/**
 * StatCard — labelled value block.
 *
 * Use `compact` inside dense grids such as penalty card phase sections or
 * lineup player rows where the default size would dominate the layout.
 */
export function StatCard({
  label,
  value,
  tone,
  detail,
  compact = false,
}: {
  label: string;
  value: string;
  tone?: string;
  detail?: string;
  compact?: boolean;
}) {
  if (compact) {
    return (
      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2.5 py-2">
        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">{label}</div>
        <div className={cn("mt-1 text-sm font-semibold leading-snug", tone ?? "text-slate-200")}>{value}</div>
        {detail ? <div className="mt-0.5 text-[10px] text-slate-500">{detail}</div> : null}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-950/40 px-3 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={cn("mt-2 text-lg font-semibold leading-snug", tone ?? "text-slate-100")}>{value}</div>
      {detail ? <div className="mt-1 text-xs text-slate-500">{detail}</div> : null}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-700/50 bg-slate-950/20 px-4 py-6 text-center text-sm text-slate-500">
      {message}
    </div>
  );
}
