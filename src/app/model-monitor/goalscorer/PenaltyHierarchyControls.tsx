"use client";

import Link from "next/link";
import { useState } from "react";

type Order = { primary: string; secondary: string; tertiary: string };
type Club = { id: string; league: string; club: string; current: Order; proposed: Order | null; entry_hash: string; status: string; reasons: string[]; confidence: string; control: { locked?: boolean; override?: Order | null }; evidence: Array<{ id: string; event_date: string; taker: string; primary?: string; primary_on_pitch?: boolean | null; source_url?: string; observed_at?: string }> };
type Audit = { id: string; at: string; action: string; club_id: string; reason: string; before_hierarchy: Order; after_hierarchy: Order };
type Report = { revision: number; generated_at: string; summary: Record<string, number>; clubs: Club[]; audit: Audit[] };
const EMPTY: Order = { primary: "", secondary: "", tertiary: "" };

async function requestReview(command?: Record<string, unknown>) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 35_000);
  try {
    const response = await fetch("/api/admin/penalty-hierarchy", command
      ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(command), signal: controller.signal }
      : { cache: "no-store", signal: controller.signal });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || (command ? "Save was not confirmed" : "Review unavailable"));
    return payload.report as Report;
  } catch (error) {
    if (controller.signal.aborted) throw new Error(command
      ? "No successful save was confirmed. Reload the review before retrying; the server may have completed the change."
      : "The review request timed out. Reload to try again.");
    throw error;
  } finally { window.clearTimeout(timeout); }
}

export function PenaltyHierarchyControls() {
  const [report, setReport] = useState<Report | null>(null);
  const [selected, setSelected] = useState("");
  const [order, setOrder] = useState<Order>(EMPTY);
  const [reason, setReason] = useState("");
  const [source, setSource] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const club = report?.clubs.find((row) => row.id === selected);
  const audit = report?.audit.filter((row) => row.club_id === selected).slice(-5).reverse() ?? [];
  function accept(next: Report, preferred = selected) {
    setReport(next);
    const row = next.clubs.find((candidate) => candidate.id === preferred) ?? next.clubs[0];
    setSelected(row?.id ?? "");
    setOrder(row?.current ?? EMPTY);
  }
  async function load() {
    setBusy(true);
    setMessage("");
    try {
      accept(await requestReview());
    } catch (error) { setMessage(error instanceof Error ? error.message : "Review unavailable"); }
    finally { setBusy(false); }
  }
  async function save(action: string, transactionId?: string) {
    if (!club || !report) return;
    setBusy(true);
    setMessage("");
    try {
      const next = await requestReview({ action, id: club.id, expected_revision: report.revision, expected_entry_hash: club.entry_hash, reason,
        hierarchy: order, sources: source ? [{ label: "Editorial verification", url: source }] : [], transaction_id: transactionId });
      accept(next, club.id);
      setMessage("Saved to the local repository with an audit record. Public deployment is a separate step.");
      setReason("");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Save was not confirmed"); }
    finally { setBusy(false); }
  }
  const button = "min-h-11 rounded-lg border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-40";
  const field = "min-h-11 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-2 text-sm disabled:opacity-60";
  return <section className="rounded-2xl border border-[var(--border)] p-5" aria-labelledby="hierarchy-controls-title">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 id="hierarchy-controls-title" className="text-lg font-semibold">Penalty hierarchy review</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Review evidence, preserve an editorial override, or undo a change. Controls require the local admin session.</p></div>
      <button className={button} onClick={load} disabled={busy}>{busy ? "Working…" : report ? "Reload review" : "Open review controls"}</button>
    </div>
    <p role="status" className="mt-3 text-sm">{message}</p>
    {!report && <Link href="/admin" className="text-sm underline">Admin sign in</Link>}
    {report && <div className="mt-4 space-y-4">
      <p className="text-xs text-[var(--muted)]">Review generated {report.generated_at} · Revision {report.revision} · {Object.entries(report.summary).map(([key, value]) => `${value} ${key}`).join(" · ")}</p>
      <label className="block text-sm">Club<select className={field} value={selected} disabled={busy} onChange={(event) => {
        setSelected(event.target.value); setOrder(report.clubs.find((row) => row.id === event.target.value)?.current ?? EMPTY); setReason(""); setSource("");
      }}>{report.clubs.map((row) => <option key={row.id} value={row.id}>{row.club} ({row.league}) — {row.status}</option>)}</select></label>
      {club && <>
        <p className="text-sm">{club.reasons.join(" ")}</p>
        <p className="text-xs">{club.control.locked ? "Automation locked." : "Automation unlocked."} {club.control.override ? "A manual override also remains active until released." : ""}</p>
        {club.proposed && <p className="text-sm">Supported candidate: {Object.values(club.proposed).filter(Boolean).join(" → ")}. Review mode has preserved the published order.</p>}
        <div className="grid gap-3 sm:grid-cols-3">{(["primary", "secondary", "tertiary"] as const).map((slot) => <label key={slot} className="block text-sm capitalize">{slot}<input className={field} value={order[slot]} maxLength={120} disabled={busy} onChange={(event) => setOrder({ ...order, [slot]: event.target.value })} /></label>)}</div>
        <label className="block text-sm">Reason for the change<textarea className={field} value={reason} minLength={5} maxLength={1200} disabled={busy} onChange={(event) => setReason(event.target.value)} /></label>
        <label className="block text-sm">Supporting source URL (required for an override)<input className={field} type="url" placeholder="https://…" value={source} disabled={busy} onChange={(event) => setSource(event.target.value)} /></label>
        <div className="flex flex-wrap gap-2">
          <button className={button} disabled={busy || reason.trim().length < 5 || !source.startsWith("https://")} onClick={() => save("override")}>Save override and lock</button>
          <button className={button} disabled={busy || reason.trim().length < 5} onClick={() => save(club.control.locked ? "unlock" : "lock")}>{club.control.locked ? "Unlock only" : "Lock current order"}</button>
          <button className={button} disabled={busy || reason.trim().length < 5 || (!club.control.override && !club.control.locked)} onClick={() => save("release")}>Release override and lock</button>
        </div>
        <details><summary className="cursor-pointer text-sm">Recent penalty evidence ({club.evidence.length})</summary><ul className="mt-2 space-y-2 text-sm">{club.evidence.map((event) => <li key={event.id}>{event.event_date}: {event.taker}. Incumbent on pitch: {event.primary_on_pitch === true ? "confirmed" : event.primary_on_pitch === false ? "no" : "unknown"}. {event.source_url?.startsWith("https://") && <a href={event.source_url} target="_blank" rel="noopener noreferrer" className="underline">Match source</a>}<span className="block text-xs text-[var(--muted)]">Observed {event.observed_at || "unknown"}</span></li>)}</ul></details>
        <details><summary className="cursor-pointer text-sm">Recent audit trail ({audit.length})</summary><ul className="mt-2 space-y-3 text-sm">{audit.map((event) => <li key={event.id}><p>{event.at} · {event.action}: {event.reason}</p><p className="text-xs">{Object.values(event.before_hierarchy).filter(Boolean).join(" → ")} → {Object.values(event.after_hierarchy).filter(Boolean).join(" → ")}</p><button className={button} disabled={busy || reason.trim().length < 5} onClick={() => save("revert", event.id)}>Revert this transaction and lock</button></li>)}</ul></details>
      </>}
    </div>}
  </section>;
}
