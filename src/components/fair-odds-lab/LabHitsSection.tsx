import teamKitColors from "../../../data/goalscorer/team-kit-colors.json";
import teamLogoManifest from "../../../data/goalscorer/team-logo-map.json";
import { AbstractJersey } from "./AbstractJersey";
import { BookmakerLogo } from "./BookmakerLogo";
import { LogoBadge } from "./LogoBadge";
import type { LabHighlight, Signal } from "./types";
const asText = (v: unknown) => typeof v === "string" ? v : "";
const formatOdds = (v: number) => v.toFixed(2);
const LOGO_MANIFEST = teamLogoManifest as { leagues?: Record<string, { teams?: Record<string, { logo_path?: string; team_key?: string }> }> };
type TeamStyle = {
  primary: string;
  secondary: string;
  pattern: NonNullable<Signal["teamShirtPattern"]>;
};
const TEAM_KIT_COLORS = teamKitColors as Record<string, TeamStyle>;

const TEAM_NAME_ALIASES: Record<string, string> = {
  "rb leipzig": "rasenballsport leipzig",
  "fc cologne": "cologne",
  "1 fc koln": "cologne",
  "fc koln": "cologne",
  "1 fc cologne": "cologne",
  "tottenham hotspur": "tottenham",
  "west ham united": "west ham",
  wolves: "wolverhampton wanderers",
  wolverhampton: "wolverhampton wanderers",
  "brighton and hove albion": "brighton",
  "brighton hove albion": "brighton",
  "afc bournemouth": "bournemouth",
  "borussia monchengladbach": "borussia m gladbach",
  "as roma": "roma",
  "acf fiorentina": "fiorentina",
  "inter milan": "inter",
  "inter milano": "inter",
  internazionale: "inter",
  "athletic bilbao": "athletic club",
  "real sociedad": "sociedad",
  "real sociedad san sebastian": "sociedad",
  "as monaco": "monaco",
  "ogc nice": "nice",
  "olympique gymnaste club nice": "nice",
  "rc lens": "lens",
};

const TEAM_STYLE_OVERRIDES: Record<string, { primary: string; secondary: string; pattern: Signal["teamShirtPattern"] }> = {
  "arsenal": { primary: "#b91c1c", secondary: "#f8fafc", pattern: "sash" },
  "aston villa": { primary: "#7f1d1d", secondary: "#38bdf8", pattern: "solid" },
  "bournemouth": { primary: "#dc2626", secondary: "#111827", pattern: "vertical-stripes" },
  "brentford": { primary: "#f8fafc", secondary: "#dc2626", pattern: "vertical-stripes" },
  "brighton": { primary: "#2563eb", secondary: "#f8fafc", pattern: "vertical-stripes" },
  "burnley": { primary: "#7f1d1d", secondary: "#38bdf8", pattern: "solid" },
  "chelsea": { primary: "#1d4ed8", secondary: "#f8fafc", pattern: "solid" },
  "crystal palace": { primary: "#1d4ed8", secondary: "#dc2626", pattern: "vertical-stripes" },
  "everton": { primary: "#1d4ed8", secondary: "#f8fafc", pattern: "solid" },
  "liverpool": { primary: "#dc2626", secondary: "#f8fafc", pattern: "solid" },
  "manchester city": { primary: "#7dd3fc", secondary: "#f8fafc", pattern: "solid" },
  "manchester united": { primary: "#dc2626", secondary: "#111827", pattern: "solid" },
  "newcastle united": { primary: "#f8fafc", secondary: "#111827", pattern: "vertical-stripes" },
  "tottenham": { primary: "#f8fafc", secondary: "#1e3a8a", pattern: "solid" },
  "west ham": { primary: "#7f1d1d", secondary: "#38bdf8", pattern: "solid" },
  "wolverhampton wanderers": { primary: "#f59e0b", secondary: "#111827", pattern: "solid" },
  "bayer leverkusen": { primary: "#111827", secondary: "#dc2626", pattern: "vertical-stripes" },
  "rasenballsport leipzig": { primary: "#f8fafc", secondary: "#dc2626", pattern: "sash" },
  "cologne": { primary: "#f8fafc", secondary: "#dc2626", pattern: "solid" },
  "borussia dortmund": { primary: "#facc15", secondary: "#111827", pattern: "solid" },
  "union berlin": { primary: "#b91c1c", secondary: "#facc15", pattern: "solid" },
  "bayern munich": { primary: "#dc2626", secondary: "#f8fafc", pattern: "solid" },
  "pisa": { primary: "#0f172a", secondary: "#1d4ed8", pattern: "halves" },
  "lecce": { primary: "#facc15", secondary: "#dc2626", pattern: "vertical-stripes" },
  "napoli": { primary: "#0ea5e9", secondary: "#f8fafc", pattern: "solid" },
  "como": { primary: "#1d4ed8", secondary: "#f8fafc", pattern: "solid" },
  "juventus": { primary: "#f8fafc", secondary: "#111827", pattern: "vertical-stripes" },
  "inter": { primary: "#1d4ed8", secondary: "#111827", pattern: "vertical-stripes" },
  "milan": { primary: "#dc2626", secondary: "#111827", pattern: "vertical-stripes" },
  "roma": { primary: "#7f1d1d", secondary: "#f59e0b", pattern: "solid" },
  "lazio": { primary: "#7dd3fc", secondary: "#f8fafc", pattern: "solid" },
  "fiorentina": { primary: "#7e22ce", secondary: "#f8fafc", pattern: "solid" },
  "atalanta": { primary: "#1d4ed8", secondary: "#111827", pattern: "vertical-stripes" },
  "barcelona": { primary: "#1e3a8a", secondary: "#b91c1c", pattern: "vertical-stripes" },
  "real madrid": { primary: "#f8fafc", secondary: "#facc15", pattern: "solid" },
  "atletico madrid": { primary: "#f8fafc", secondary: "#dc2626", pattern: "vertical-stripes" },
  "sociedad": { primary: "#f8fafc", secondary: "#2563eb", pattern: "vertical-stripes" },
  "athletic club": { primary: "#f8fafc", secondary: "#dc2626", pattern: "vertical-stripes" },
  "monaco": { primary: "#f8fafc", secondary: "#dc2626", pattern: "sash" },
  "psg": { primary: "#1e3a8a", secondary: "#dc2626", pattern: "solid" },
  "marseille": { primary: "#f8fafc", secondary: "#0ea5e9", pattern: "solid" },
  "lyon": { primary: "#f8fafc", secondary: "#dc2626", pattern: "sash" },
  "lille": { primary: "#dc2626", secondary: "#1e3a8a", pattern: "solid" },
  "lens": { primary: "#dc2626", secondary: "#facc15", pattern: "vertical-stripes" },
};

function normalizeTeamKey(value: unknown): string {
  const normalized = asText(value)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  const aliased = TEAM_NAME_ALIASES[normalized] ?? normalized;
  const simplified = aliased
    .replace(/\b(?:ac|afc|as|bc|ca|cf|cfc|fc|rc|rcd|sc|ssc|us)\b/g, " ")
    .replace(/\bcalcio\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return TEAM_NAME_ALIASES[simplified] ?? simplified;
}

function resolveTeamLogoPath(leagueSlug: string, team: string): string {
  const teams = LOGO_MANIFEST.leagues?.[leagueSlug]?.teams ?? {};
  if (teams[team]?.logo_path) return asText(teams[team].logo_path);
  const target = normalizeTeamKey(team);
  const matched = Object.entries(teams).find(([name, row]) => {
    return normalizeTeamKey(name) === target || normalizeTeamKey(row.team_key) === target;
  });
  return matched?.[1].logo_path ? asText(matched[1].logo_path) : "";
}

function resolveTeamStyle(team: string) {
  const key = normalizeTeamKey(team);
  return TEAM_KIT_COLORS[key] ?? TEAM_STYLE_OVERRIDES[key] ?? null;
}

function formatHighlightDate(value: string) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return value || "Recent";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    timeZone: "Europe/London",
  }).format(timestamp);
}

function formatTicketDate(value: string) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return value || "Recent";
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    timeZone: "Europe/London",
  }).format(timestamp);
}

function splitMatchTeams(match: string) {
  const parts = match.split(/\s+(?:vs|v)\s+/i).map((part) => part.trim()).filter(Boolean);
  return {
    home: parts[0] ?? "",
    away: parts[1] ?? "",
  };
}

function teamsMatch(a: string | undefined, b: string | undefined) {
  const left = normalizeTeamKey(a);
  const right = normalizeTeamKey(b);
  return Boolean(left && right && (left === right || left.includes(right) || right.includes(left)));
}

function resolveHighlightTeams(highlight: LabHighlight) {
  const { home, away } = splitMatchTeams(highlight.match);
  const team = highlight.team || home;
  const opponent = teamsMatch(team, home) ? away : teamsMatch(team, away) ? home : away || home;
  return {
    team,
    opponent,
    home,
    away,
  };
}

function HitTicket({ highlight }: { highlight: LabHighlight }) {
  const teams = resolveHighlightTeams(highlight);
  const style = resolveTeamStyle(teams.team);
  const teamLogoPath = resolveTeamLogoPath(highlight.league ?? "", teams.team);
  const opponentLogoPath = resolveTeamLogoPath(highlight.league ?? "", teams.opponent);
  const leagueLogoPath = highlight.league ? `/league-logos/${highlight.league}.png` : "";
  const stateLabel = highlight.superSubWin ? "Super Sub hit" : highlight.goalsScored > 1 ? `Scored x${highlight.goalsScored}` : "Scored";
  const stateClass = highlight.superSubWin
    ? "border-cyan-300/30 bg-cyan-300/10 text-cyan-100"
    : "border-emerald-300/30 bg-emerald-300/10 text-emerald-100";

  return (
    <article className="group relative overflow-hidden rounded-[1.5rem] border border-slate-800/80 bg-[#090e15] p-4 transition duration-300 hover:-translate-y-1 hover:border-emerald-400/35 hover:shadow-[0_24px_60px_rgba(16,185,129,0.12)]">
      <div className="pointer-events-none absolute -right-14 -top-14 h-32 w-32 rounded-full bg-emerald-300/[0.08] blur-2xl transition group-hover:bg-emerald-300/[0.14]" />
      <div className="relative flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
          <LogoBadge
            src={leagueLogoPath}
            alt={`${highlight.competition} logo`}
            fallback={highlight.competition}
            size={24}
            shape="rounded"
            className="bg-white/95 p-1"
          />
          <span className="truncate">{highlight.competition}</span>
        </div>
        <span className="shrink-0 font-mono text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
          {formatTicketDate(highlight.date)}
        </span>
      </div>

      <div className="relative mt-4 border-t border-dashed border-slate-700/50 pt-4">
        <div className="flex gap-4">
          <div className="w-[72px] shrink-0">
            <AbstractJersey
              teamLogoPath={teamLogoPath}
              teamPrimaryColor={style?.primary ?? "#10b981"}
              teamSecondaryColor={style?.secondary ?? "#0f172a"}
              shirtPattern={style?.pattern ?? "solid"}
              accentEmerald={false}
            />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="break-words text-2xl font-black leading-tight tracking-tight text-slate-50">
              {highlight.player}
            </h3>
            <div className="mt-1 text-sm font-semibold text-slate-500">
              {teams.team}
            </div>
            <div className="mt-3 flex min-w-0 items-center gap-2 rounded-xl border border-slate-800/80 bg-slate-950/55 px-3 py-2">
              <LogoBadge
                src={teamLogoPath}
                alt={`${teams.team} logo`}
                fallback={teams.team}
                size={24}
              />
              <span className="min-w-0 truncate text-xs font-semibold text-slate-300">
                {teams.team}
              </span>
              <span className="shrink-0 text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
                vs
              </span>
              <LogoBadge
                src={opponentLogoPath}
                alt={`${teams.opponent} logo`}
                fallback={teams.opponent}
                size={24}
              />
              <span className="min-w-0 truncate text-xs font-semibold text-slate-300">
                {teams.opponent}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-950/70">
          <div className="p-3">
            <div className="text-[9px] font-black uppercase tracking-[0.14em] text-emerald-200/80">
              Fair
            </div>
            <div className="mt-1 font-mono text-2xl font-black text-emerald-100">
              {formatOdds(highlight.fairOdds)}
            </div>
          </div>
          <div className="border-l border-slate-800/80 p-3">
            <div className="text-[9px] font-black uppercase tracking-[0.14em] text-slate-500">
              Reference
            </div>
            <div className="mt-1 flex min-w-0 flex-col items-start gap-1 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
              <span className="font-mono text-2xl font-black text-slate-100">
                {formatOdds(highlight.bestOdds)}
              </span>
              <BookmakerLogo name={highlight.bestBookmaker} size="xs" className="sm:h-6 sm:min-w-12 sm:max-w-none sm:px-2.5" />
            </div>
          </div>
          <div className="border-l border-amber-300/20 bg-amber-300/[0.065] p-3">
            <div className="text-[9px] font-black uppercase tracking-[0.14em] text-amber-100/80">
              Gap
            </div>
            <div className="mt-1 font-mono text-2xl font-black text-amber-100">
              +{highlight.priceGapPp.toFixed(1)}
            </div>
            <div className="text-[9px] font-black uppercase tracking-[0.14em] text-amber-100/60">
              pp
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-3 border-t border-dashed border-slate-700/45 pt-4">
          <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-black uppercase tracking-[0.14em] ${stateClass}`}>
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-white/10">
              &#10003;
            </span>
            {stateLabel}
          </span>
          <span className="font-mono text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
            Recorded · {formatHighlightDate(highlight.date)}
          </span>
        </div>

        <div className="mt-3 text-xs leading-5 text-slate-500">
          Reference: {highlight.bestBookmaker} · Lab vs market gap.
        </div>
      </div>
    </article>
  );
}

export function LabHitsSection({ highlights }: { highlights: LabHighlight[] }) {
  if (!highlights.length) return null;
  const visibleHighlights = highlights.slice(0, 6);

  return (
    <section id="lab-hits" className="mt-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.22em] text-emerald-300">
            Lab hits
          </div>
          <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-50">
            The price stood out. The player scored.
          </h2>
        </div>

      </div>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
        Selected recorded positive-EV comparisons where the named player scored.
        Winning examples only; not the complete performance record.
      </p>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibleHighlights.map((highlight) => (
          <HitTicket key={highlight.id} highlight={highlight} />
        ))}
      </div>
    </section>
  );
}

