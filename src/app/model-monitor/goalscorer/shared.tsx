import type { ReactNode } from "react";
import Link from "next/link";

export const MODEL_MONITOR_ENABLED =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.MODEL_MONITOR_PUBLIC === "true" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "true" ||
  process.env.VERCEL_ENV === "preview";

function cn(...parts: Array<string | false | null | undefined>) {
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
  if (value === null || value === undefined || !Number.isFinite(value)) return "text-slate-200";
  if (value > 0) return "text-emerald-300";
  if (value < 0) return "text-rose-300";
  return "text-slate-200";
}

export function actionTone(action?: string | null): string {
  const normalized = (action || "").toLowerCase();
  if (normalized.includes("surface") || normalized.includes("public")) return "bg-emerald-500/12 text-emerald-200 border-emerald-500/25";
  if (normalized.includes("shadow")) return "bg-amber-500/12 text-amber-200 border-amber-500/25";
  if (normalized.includes("suppress") || normalized.includes("quarantine")) return "bg-rose-500/12 text-rose-200 border-rose-500/25";
  return "bg-slate-900/70 text-slate-300 border-slate-700/80";
}

export function statusTone(status?: string | null): string {
  const normalized = (status || "").toLowerCase();
  if (normalized.includes("confirmed")) return "bg-emerald-500/12 text-emerald-200 border-emerald-500/25";
  if (normalized.includes("expected")) return "bg-amber-500/12 text-amber-200 border-amber-500/25";
  if (normalized.includes("quarantined")) return "bg-rose-500/12 text-rose-200 border-rose-500/25";
  if (normalized.includes("no feed") || normalized.includes("missing")) return "bg-slate-900/70 text-slate-300 border-slate-700/80";
  return "bg-cyan-500/12 text-cyan-200 border-cyan-500/25";
}

export function StatusPill({ label, tone }: { label: string; tone: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]", tone)}>
      {label}
    </span>
  );
}

export function MonitorNav({ current }: { current: "goalscorer" | "lineups" }) {
  const base = "inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-200";
  const active = "border-emerald-500/30 bg-emerald-500/10 text-emerald-100";
  return (
    <nav className="mb-8 flex flex-wrap items-center gap-3">
      <Link href="/model-monitor" className={base}>Tennis</Link>
      <Link href="/model-monitor/goalscorer" className={cn(base, current === "goalscorer" && active)}>Goalscorer</Link>
      <Link href="/model-monitor/goalscorer/lineups" className={cn(base, current === "lineups" && active)}>Lineups</Link>
      <Link href="/model-monitor/team-shots" className={base}>Team Shots</Link>
      <Link href="/model-monitor/corners" className={base}>Corners</Link>
    </nav>
  );
}

export function HeroCard({ title, eyebrow, children }: { title: string; eyebrow: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-[linear-gradient(135deg,rgba(15,23,42,0.96),rgba(10,14,23,0.92))] px-6 py-7 shadow-[0_30px_90px_rgba(2,6,23,0.45)] sm:px-8">
      <div className="mb-3 inline-flex items-center rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-emerald-200">
        {eyebrow}
      </div>
      <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">{title}</h1>
      <div className="mt-4 text-sm text-slate-300">{children}</div>
    </section>
  );
}

export function SectionCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(17,24,39,0.96),rgba(10,14,23,0.92))] p-5 shadow-[0_20px_60px_rgba(2,6,23,0.35)]">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-slate-400">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

export function StatCard({ label, value, tone, detail }: { label: string; value: string; tone?: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 px-3 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={cn("mt-2 text-lg font-semibold text-slate-100", tone)}>{value}</div>
      {detail ? <div className="mt-1 text-xs text-slate-500">{detail}</div> : null}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-700/80 bg-slate-950/35 px-4 py-5 text-sm text-slate-400">
      {message}
    </div>
  );
}

