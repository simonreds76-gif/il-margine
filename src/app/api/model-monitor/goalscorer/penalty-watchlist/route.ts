import { NextResponse } from "next/server";
import { revalidatePath } from "next/cache";

import {
  clubPenaltySlug,
  normalizeClubPenaltyKey,
  readClubPenaltyData,
} from "@/lib/club-penalty-takers";
import { readGoalscorerMonitorSnapshot } from "@/lib/goalscorer-monitor-snapshot";
import { readPenaltyReviewState, setPenaltyReviewResolution } from "@/lib/goalscorer-penalty-review-state";

const REVIEW_STATUSES = new Set(["accepted", "ignored", "deferred", "applied", "active"]);

function dateStamp(value?: string): number {
  if (!value) return Number.NaN;
  return Date.parse(`${value.slice(0, 10)}T12:00:00Z`);
}

async function validateAppliedTicket(id: string) {
  const [snapshot, leagues] = await Promise.all([
    readGoalscorerMonitorSnapshot(),
    readClubPenaltyData(),
  ]);
  const eventRow = snapshot?.penalty_watchlist.rows.find((candidate) => candidate.row_id === id);
  const sourceRow = snapshot?.preseason_role_review?.rows.find((candidate) => candidate.row_id === id);
  if (!eventRow && !sourceRow) {
    throw new Error("Ticket is no longer present in the current review snapshot");
  }

  const normalizedLeague = normalizeClubPenaltyKey(eventRow?.league ?? sourceRow?.league ?? "");
  const league = leagues.find(
    (candidate) =>
      normalizeClubPenaltyKey(candidate.key) === normalizedLeague ||
      normalizeClubPenaltyKey(candidate.label) === normalizedLeague,
  );
  const normalizedTeam = normalizeClubPenaltyKey(
    eventRow?.public_team || eventRow?.team || sourceRow?.team || "",
  );
  const team = league?.teams.find(
    (candidate) => normalizeClubPenaltyKey(candidate.team) === normalizedTeam,
  );
  if (!league || !team) {
    throw new Error(
      `Cannot map ${eventRow?.team || sourceRow?.team || "ticket team"} to a current club hierarchy`,
    );
  }

  if (sourceRow) {
    const proposedPrimary = normalizeClubPenaltyKey(sourceRow.proposed_primary ?? "");
    if (!proposedPrimary || normalizeClubPenaltyKey(team.primary) !== proposedPrimary) {
      throw new Error(
        `${sourceRow.proposed_primary || "The proposed primary"} is not ${team.team}'s published primary yet`,
      );
    }
  } else if (eventRow) {
    const actualTaker = normalizeClubPenaltyKey(eventRow.actual_taker ?? "");
    const hierarchy = [team.primary, team.secondary, team.tertiary].map(normalizeClubPenaltyKey);
    if (!actualTaker || !hierarchy.includes(actualTaker)) {
      throw new Error(
        `${eventRow.actual_taker || "The observed taker"} is not in ${team.team}'s published hierarchy yet`,
      );
    }
  }

  const evidenceDate = (eventRow?.date || sourceRow?.generated_at || "").slice(0, 10);
  const eventStamp = dateStamp(evidenceDate);
  const verifiedStamp = dateStamp(team.lastUpdated);
  const publicStamp = dateStamp(team.publicUpdatedAt);
  if (
    Number.isFinite(eventStamp) &&
    (!Number.isFinite(verifiedStamp) ||
      verifiedStamp < eventStamp ||
      !Number.isFinite(publicStamp) ||
      publicStamp < eventStamp)
  ) {
    throw new Error(
      `${team.team}'s verification and public update dates must be ${evidenceDate} or later`,
    );
  }

  revalidatePath("/penalty-takers");
  revalidatePath(`/penalty-takers/${league.key}`);
  revalidatePath(`/penalty-takers/${league.key}/${clubPenaltySlug(team.team)}`);
  return {
    team: team.team,
    league: league.label,
    public_path: team.relativeUrl,
  };
}

export async function GET() {
  try {
    const [snapshot, state] = await Promise.all([
      readGoalscorerMonitorSnapshot(),
      readPenaltyReviewState(),
    ]);

    if (!snapshot) {
      return NextResponse.json({ ok: false, error: "Goalscorer monitor snapshot unavailable" }, { status: 503 });
    }

    const rows = snapshot.penalty_watchlist.rows.map((row) => ({
      ...row,
      resolution_status: state[row.row_id]?.status ?? null,
      resolution_updated_at: state[row.row_id]?.updated_at ?? null,
    }));

    return NextResponse.json({
      ok: true,
      schema_version: snapshot.schema_version,
      generated_at: snapshot.generated_at,
      penalty_watchlist_generated_at: snapshot.penalty_watchlist.generated_at,
      row_count: rows.length,
      rows,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as {
      id?: string;
      status?: "accepted" | "ignored" | "deferred" | "applied" | "active";
    };

    const id = typeof payload.id === "string" ? payload.id : "";
    const status = payload.status;

    if (!id.trim()) {
      return NextResponse.json({ ok: false, error: "Missing row id" }, { status: 400 });
    }
    if (!status || !REVIEW_STATUSES.has(status)) {
      return NextResponse.json({ ok: false, error: "Invalid status" }, { status: 400 });
    }

    const validation = status === "applied" ? await validateAppliedTicket(id) : null;
    await setPenaltyReviewResolution(id, status);
    return NextResponse.json({ ok: true, validation });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    const status = message.includes("published hierarchy") || message.includes("published primary") || message.includes("verification") || message.includes("Cannot map")
      ? 409
      : 500;
    return NextResponse.json({ ok: false, error: message }, { status });
  }
}

