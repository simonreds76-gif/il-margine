import { notFound } from "next/navigation";
import { readTeamShotsLiveJson } from "@/lib/team-shots-live-files";
import {
  cleanText,
  cn,
  FootballLaneNav,
  formatDateTimeLabel,
  HeroCard,
  MODEL_MONITOR_ENABLED,
  MonitorNav,
  StatusPill,
} from "../shared";

export const dynamic = "force-dynamic";

type ModelReport = {
  generated_at?: string;
  sample_matches?: number;
  decision?: {
    status?: string;
    count_gate_pass?: boolean;
    market_gate_pass?: boolean;
    settlement_gate_pass?: boolean;
    signals_authorized?: boolean;
    gates?: Record<string, boolean>;
  };
};

type AgreementReport = {
  generated_at?: string;
  status?: string;
  settlement_source_authorized?: boolean;
  requirements?: {
    minimum_comparable_team_values?: number;
    minimum_within_one_pct?: number;
  };
  api_football?: SourceAgreement;
  fotmob?: SourceAgreement;
};

type SourceAgreement = {
  comparable_team_values?: number;
  within_one_pct?: number;
  exact_pct?: number;
  mae?: number | null;
  passed?: boolean;
};

type MarketProbe = {
  generated_at?: string;
  status?: string;
  bookmaker?: string;
  events_probed?: number;
  requests_used?: number;
  decision?: string;
  labels?: { paired_foul_lines?: unknown[] };
};

function label(value?: string | null): string {
  return cleanText(value).replaceAll("_", " ");
}

function GateRow({ name, current, required, passed }: { name: string; current: string; required: string; passed: boolean }) {
  return (
    <div className="grid gap-2 border-t border-slate-800/80 px-4 py-3 first:border-t-0 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-center">
      <div className="font-medium text-slate-200">{name}</div>
      <div className="text-xs text-slate-400"><span className="text-slate-600 sm:hidden">Current: </span>{current}</div>
      <div className="text-xs text-slate-400"><span className="text-slate-600 sm:hidden">Required: </span>{required}</div>
      <StatusPill label={passed ? "Pass" : "Blocked"} tone={passed ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200" : "border-amber-400/25 bg-amber-400/10 text-amber-200"} />
    </div>
  );
}

function SourceCard({ name, source, requiredN, requiredAgreement }: { name: string; source?: SourceAgreement; requiredN: number; requiredAgreement: number }) {
  const n = source?.comparable_team_values ?? 0;
  const agreement = source?.within_one_pct ?? 0;
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/45 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold text-slate-100">{name}</h3>
        <StatusPill label={source?.passed ? "Pass" : "Collecting"} tone={source?.passed ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200" : "border-amber-400/25 bg-amber-400/10 text-amber-200"} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-slate-900/70 p-3"><div className="text-[11px] uppercase tracking-[0.12em] text-slate-500">Team values</div><div className="mt-1 font-mono text-lg text-white">{n}/{requiredN}</div></div>
        <div className="rounded-lg bg-slate-900/70 p-3"><div className="text-[11px] uppercase tracking-[0.12em] text-slate-500">Within one</div><div className={cn("mt-1 font-mono text-lg", n >= requiredN && agreement >= requiredAgreement ? "text-emerald-300" : "text-amber-200")}>{agreement.toFixed(1)}%</div></div>
      </div>
    </div>
  );
}

export default async function TeamFoulsMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [f1, f2, agreement, market] = await Promise.all([
    readTeamShotsLiveJson<ModelReport>("data/football-form/team-fouls-v1-fold-report.json"),
    readTeamShotsLiveJson<ModelReport>("data/football-form/team-fouls-f2-fold-report.json"),
    readTeamShotsLiveJson<AgreementReport>("data/football-form/team-fouls-definition-agreement.json"),
    readTeamShotsLiveJson<MarketProbe>("data/football-form/football-foul-market-probe.json"),
  ]);

  const requiredN = agreement?.requirements?.minimum_comparable_team_values ?? 200;
  const requiredAgreement = agreement?.requirements?.minimum_within_one_pct ?? 97;
  const f2Gates = f2?.decision?.gates ?? {};
  const pairedMarketLines = market?.labels?.paired_foul_lines?.length ?? 0;
  const hasPricedMarket = pairedMarketLines > 0;

  return (
    <div className="min-h-screen bg-[#080d16] px-3 py-6 text-slate-200 sm:px-6 sm:py-10">
      <main className="mx-auto flex max-w-7xl flex-col gap-4">
        <MonitorNav current="team-fouls" />
        <FootballLaneNav current="team-fouls" />
        <HeroCard title="Team Fouls F2" eyebrow="Research gate progress">
          <span className="text-slate-300">{hasPricedMarket ? `${pairedMarketLines} paired foul lines were captured, but no research selection has passed every gate.` : "No paired foul market has been captured, so no signal ledger exists."}</span>{" "}
          <span className="text-slate-500">This page shows exactly what is validated and what still blocks prospective tracking.</span>
        </HeroCard>

        <section className="overflow-hidden rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.98),rgba(8,12,20,0.98))]">
          <div className="border-b border-slate-800 px-4 py-4 sm:px-5">
            <div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-semibold text-white">F2 decision board</h2><StatusPill label="Gate stage" tone="border-violet-400/30 bg-violet-400/10 text-violet-200" /><StatusPill label="Signals blocked" tone="border-rose-400/30 bg-rose-400/10 text-rose-200" /></div>
            <p className="mt-2 text-sm leading-6 text-slate-400">Count modelling, settlement definition and a paired two-way price feed must all pass before a selection can enter prospective P/L.</p>
          </div>

          <div className="grid grid-cols-2 gap-2 p-4 sm:grid-cols-4 sm:p-5">
            <div className="rounded-xl border border-slate-800 bg-slate-950/55 p-3"><div className="text-[11px] uppercase tracking-[0.12em] text-slate-500">F1 status</div><div className="mt-1 text-sm font-semibold text-amber-200">{label(f1?.decision?.status || "not run")}</div></div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/55 p-3"><div className="text-[11px] uppercase tracking-[0.12em] text-slate-500">F2 status</div><div className="mt-1 text-sm font-semibold text-amber-200">{label(f2?.decision?.status || "not run")}</div></div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/55 p-3"><div className="text-[11px] uppercase tracking-[0.12em] text-slate-500">Tracked</div><div className="mt-1 font-mono text-lg font-semibold text-white">0</div><div className="mt-1 text-[11px] text-slate-500">{hasPricedMarket ? "gates still block registration" : "no price-backed ledger"}</div></div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/55 p-3"><div className="text-[11px] uppercase tracking-[0.12em] text-slate-500">Updated</div><div className="mt-1 text-sm font-semibold text-white">{formatDateTimeLabel(f2?.generated_at || agreement?.generated_at)}</div></div>
          </div>

          <div className="border-t border-slate-800 px-4 py-4 sm:px-5">
            <h3 className="mb-3 text-base font-semibold text-white">Promotion gates</h3>
            <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950/35">
              <div className="hidden grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] gap-2 bg-slate-950/80 px-4 py-2 text-[11px] uppercase tracking-[0.12em] text-slate-500 sm:grid"><span>Gate</span><span>Current</span><span>Required</span><span>Status</span></div>
              <GateRow name="F2 count model" current={label(f2?.decision?.status || "not run")} required="registered fold gates pass" passed={Boolean(f2?.decision?.count_gate_pass)} />
              <GateRow name="FotMob agreement" current={`${agreement?.fotmob?.comparable_team_values ?? 0} values / ${(agreement?.fotmob?.within_one_pct ?? 0).toFixed(1)}%`} required={`${requiredN} values / ${requiredAgreement}%`} passed={Boolean(agreement?.fotmob?.passed)} />
              <GateRow name="API-Football agreement" current={`${agreement?.api_football?.comparable_team_values ?? 0} values / ${(agreement?.api_football?.within_one_pct ?? 0).toFixed(1)}%`} required={`${requiredN} values / ${requiredAgreement}%`} passed={Boolean(agreement?.api_football?.passed)} />
              <GateRow name="Paired market prices" current={`${market?.events_probed ?? 0} events probed / ${pairedMarketLines} paired lines`} required="real two-way O/U prices" passed={Boolean(f2?.decision?.market_gate_pass)} />
              <GateRow name="Settlement definition" current={agreement?.settlement_source_authorized ? "authorized" : "not authorized"} required="two independent sources pass" passed={Boolean(f2?.decision?.settlement_gate_pass)} />
            </div>
          </div>

          <div className="border-t border-slate-800 px-4 py-4 sm:px-5">
            <h3 className="mb-3 text-base font-semibold text-white">Independent source agreement</h3>
            <div className="grid gap-3 sm:grid-cols-2"><SourceCard name="FotMob" source={agreement?.fotmob} requiredN={requiredN} requiredAgreement={requiredAgreement} /><SourceCard name="API-Football" source={agreement?.api_football} requiredN={requiredN} requiredAgreement={requiredAgreement} /></div>
          </div>

          <div className="border-t border-slate-800 px-4 py-4 sm:px-5">
            <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-4 text-sm leading-6 text-slate-300"><strong className="text-amber-200">No betting table while registration is blocked.</strong> {cleanText(market?.decision) || "A paired team-fouls O/U price feed is still missing."}<div className="mt-1 text-xs text-slate-500">Latest market probe: {formatDateTimeLabel(market?.generated_at)} / {market?.requests_used ?? 0} requests</div></div>
          </div>

          <details className="border-t border-slate-800 px-4 py-4 sm:px-5">
            <summary className="cursor-pointer text-sm font-semibold text-slate-300">Technical F2 gate detail</summary>
            <div className="mt-3 flex flex-wrap gap-2">{Object.entries(f2Gates).map(([gate, passed]) => <StatusPill key={gate} label={`${label(gate)} ${passed ? "pass" : "fail"}`} tone={passed ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200" : "border-slate-700 bg-slate-900 text-slate-400"} />)}</div>
          </details>
        </section>
      </main>
    </div>
  );
}
