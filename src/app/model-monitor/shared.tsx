import type { ReactNode } from "react";
import Link from "next/link";
import Image from "next/image";
import teamLogoManifest from "../../../data/goalscorer/team-logo-map.json";

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

type TeamLogoRow = {
  logo_path?: string;
};

type LogoManifest = {
  leagues?: Record<
    string,
    {
      teams?: Record<string, TeamLogoRow>;
    }
  >;
};

const LOGO_MANIFEST = teamLogoManifest as LogoManifest;

const LEAGUE_META: Record<string, { label: string; logoPath: string }> = {
  epl: { label: "Premier League", logoPath: "/league-logos/epl.png" },
  "premier league": { label: "Premier League", logoPath: "/league-logos/epl.png" },
  "serie-a": { label: "Serie A", logoPath: "/league-logos/serie-a.png" },
  "serie a": { label: "Serie A", logoPath: "/league-logos/serie-a.png" },
  bundesliga: { label: "Bundesliga", logoPath: "/league-logos/bundesliga.png" },
  "la-liga": { label: "La Liga", logoPath: "/league-logos/la-liga.png" },
  "la liga": { label: "La Liga", logoPath: "/league-logos/la-liga.png" },
  "ligue-1": { label: "Ligue 1", logoPath: "/league-logos/ligue-1.png" },
  "ligue 1": { label: "Ligue 1", logoPath: "/league-logos/ligue-1.png" },
};

const TEAM_NAME_ALIASES: Record<string, string> = {
  "fc st pauli": "st pauli",
  "ca osasuna": "osasuna",
  "athletic bilbao": "athletic club",
  "rb leipzig": "rasenballsport leipzig",
  "tsg hoffenheim": "hoffenheim",
  "borussia monchengladbach": "borussia m gladbach",
  "brighton and hove albion": "brighton",
  "brighton hove albion": "brighton",
  "afc bournemouth": "bournemouth",
  "1 fc koln": "fc cologne",
  "1 fc cologne": "fc cologne",
  "fc koln": "fc cologne",
  "1 fc heidenheim": "fc heidenheim",
  heidenheim: "fc heidenheim",
  "fsv mainz 05": "mainz 05",
  "sc freiburg": "freiburg",
  "vfl wolfsburg": "wolfsburg",
  "leeds united": "leeds",
  "tottenham hotspur": "tottenham",
  "west ham united": "west ham",
  wolves: "wolverhampton",
  wolverhampton: "wolverhampton wanderers",
  "getafe cf": "getafe",
  "levante ud": "levante",
  "as monaco": "monaco",
  "rc lens": "lens",
  "acf fiorentina": "fiorentina",
  "as roma": "roma",
  "atalanta bc": "atalanta",
  "hellas verona": "verona",
  "lazio rome": "lazio",
  "parma calcio 1913": "parma",
  "parma calcio": "parma calcio 1913",
  parma: "parma calcio 1913",
  internazionale: "inter",
  "inter milano": "inter",
  "inter milan": "inter",
  "deportivo alaves": "alaves",
  "real sociedad": "sociedad",
  "real sociedad san sebastian": "sociedad",
  "juventus turin": "juventus",
  "espanyol barcelona": "espanyol",
};

function repairMojibake(value: string): string {
  if (!value) return value;
  const normalized = value.normalize("NFC");
  if (!/[\u00C3\u00C2\u00E2]/.test(normalized)) return normalized;
  try {
    const repaired = Buffer.from(normalized, "latin1").toString("utf8").normalize("NFC");
    const mojibakeCount = (text: string) => (text.match(/[\u00C3\u00C2\u00E2\uFFFD]/g) ?? []).length;
    return mojibakeCount(repaired) < mojibakeCount(normalized) ? repaired : normalized;
  } catch {
    return normalized;
  }
}

function cleanText(value?: string | null): string {
  return repairMojibake(
    (value ?? "")
      .trim()
      .replace(/&#0*39;|&#x27;|&apos;/gi, "'")
      .replace(/&amp;/gi, "&")
      .replace(/&quot;/gi, '"')
      .replace(/&nbsp;/gi, " "),
  ).replace(/\s+/g, " ");
}

function normalizeKey(value?: string | null): string {
  return cleanText(value)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase();
}

function simplifyClubKey(value: string): string {
  return value
    .replace(/\b(?:ac|afc|as|bc|ca|cf|cfc|fc|rc|rcd|sc|ssc|us)\b/g, " ")
    .replace(/\bcalcio\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function canonicalizeTeamKey(value?: string | null): string {
  const normalized = normalizeKey(value);
  if (!normalized) return "";
  const aliased = TEAM_NAME_ALIASES[normalized] ?? normalized;
  const simplified = simplifyClubKey(aliased);
  return TEAM_NAME_ALIASES[simplified] ?? simplified;
}

export function resolveLeagueKey(value?: string | null): string | null {
  const normalized = normalizeKey(value);
  if (!normalized) return null;
  if (normalized === "premier league") return "epl";
  if (normalized === "serie a") return "serie-a";
  if (normalized === "la liga") return "la-liga";
  if (normalized === "ligue 1") return "ligue-1";
  if (normalized in LEAGUE_META) {
    return normalized === "premier league" ? "epl" : normalized;
  }
  return normalized;
}

function resolveLeagueMeta(value?: string | null) {
  const key = resolveLeagueKey(value);
  if (!key) return null;
  return LEAGUE_META[key] ?? null;
}

export function findTeamLogoPath(leagueValue: string | null | undefined, teamValue: string | null | undefined): string {
  const leagueKey = resolveLeagueKey(leagueValue);
  const team = cleanText(teamValue);
  if (!leagueKey || !team) return "";
  const teams = LOGO_MANIFEST.leagues?.[leagueKey]?.teams ?? {};
  if (teams[team]?.logo_path) return cleanText(teams[team].logo_path);
  const canonicalTeam = canonicalizeTeamKey(team);
  const matched = Object.entries(teams).find(([name]) => {
    return canonicalizeTeamKey(name) === canonicalTeam;
  });
  return matched?.[1]?.logo_path ? cleanText(matched[1].logo_path) : "";
}

function TeamLogo({
  league,
  team,
  size = 18,
  initials,
}: {
  league?: string | null;
  team?: string | null;
  size?: number;
  initials?: string;
}) {
  const logoPath = findTeamLogoPath(league, team);
  const fallback =
    initials ||
    cleanText(team)
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") ||
    "?";
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-slate-700/70 bg-slate-900/80 text-[10px] font-semibold uppercase text-slate-300"
      style={{ width: size, height: size }}
    >
      {logoPath ? (
        <Image src={logoPath} alt={cleanText(team) || "team"} width={size} height={size} className="h-full w-full object-contain" />
      ) : (
        fallback.slice(0, 2)
      )}
    </span>
  );
}

export function LeagueLabel({
  league,
  label,
  className,
  iconSize = 18,
}: {
  league?: string | null;
  label?: string | null;
  className?: string;
  iconSize?: number;
}) {
  const meta = resolveLeagueMeta(league || label);
  const text = cleanText(label) || meta?.label || cleanText(league) || "League";
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      {meta ? (
        <span className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-700/70 bg-white/95 p-1">
          <Image src={meta.logoPath} alt={`${text} logo`} width={iconSize} height={iconSize} className="object-contain" />
        </span>
      ) : null}
      <span>{text}</span>
    </span>
  );
}

export function TeamLabel({
  league,
  team,
  detail,
  className,
  teamClassName,
  detailClassName,
  iconSize = 20,
}: {
  league?: string | null;
  team?: string | null;
  detail?: string | null;
  className?: string;
  teamClassName?: string;
  detailClassName?: string;
  iconSize?: number;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <TeamLogo league={league} team={team} size={iconSize} />
      <span className="min-w-0">
        <span className={cn("block truncate", teamClassName)}>{cleanText(team) || "-"}</span>
        {detail ? <span className={cn("block truncate", detailClassName)}>{detail}</span> : null}
      </span>
    </span>
  );
}

export function MatchLabel({
  league,
  homeTeam,
  awayTeam,
  className,
  textClassName,
  iconSize = 18,
  separator = "vs",
}: {
  league?: string | null;
  homeTeam?: string | null;
  awayTeam?: string | null;
  className?: string;
  textClassName?: string;
  iconSize?: number;
  separator?: string;
}) {
  return (
    <span className={cn("inline-flex min-w-0 max-w-full items-center gap-2", className)}>
      <TeamLogo league={league} team={homeTeam} size={iconSize} />
      <span className={cn("min-w-0 flex-1 truncate", textClassName)}>
        {cleanText(homeTeam) || "?"} {separator} {cleanText(awayTeam) || "?"}
      </span>
      <TeamLogo league={league} team={awayTeam} size={iconSize} />
    </span>
  );
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
  current: "tennis" | "tennis-props" | "goalscorer" | "lineups" | "assist-value" | "team-shots" | "corners";
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
      <Link href="/model-monitor/tennis-props" className={cn(base, current === "tennis-props" && active)}>
        Aces / DFs
      </Link>
      <Link href="/model-monitor/goalscorer" className={cn(base, current === "goalscorer" && active)}>
        Goalscorer
      </Link>
      <Link href="/model-monitor/goalscorer/lineups" className={cn(base, current === "lineups" && active)}>
        Lineups
      </Link>
      <Link href="/model-monitor/assist-value" className={cn(base, current === "assist-value" && active)}>
        Assist Value
      </Link>
      <Link href="/model-monitor/team-shots" className={cn(base, current === "team-shots" && active)}>
        Shots / Fouls
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
  title: ReactNode;
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
  id,
  title,
  subtitle,
  collapsible = false,
  defaultOpen = true,
  children,
}: {
  id?: string;
  title: ReactNode;
  subtitle?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const shell =
    "min-w-0 rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] shadow-[0_8px_32px_rgba(0,0,0,0.28)]";

  if (collapsible) {
    return (
      <details id={id} open={defaultOpen} className={cn("group scroll-mt-6", shell)}>
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
    <section id={id} className={cn(shell, "scroll-mt-6 p-5")}>
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
