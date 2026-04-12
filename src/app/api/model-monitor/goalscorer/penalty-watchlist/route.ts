import { NextResponse } from "next/server";

import { readGoalscorerMonitorSnapshot } from "@/lib/goalscorer-monitor-snapshot";
import { readPenaltyReviewState, setPenaltyReviewResolution } from "@/lib/goalscorer-penalty-review-state";

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
      status?: "dismissed" | "done" | "active";
    };

    const id = typeof payload.id === "string" ? payload.id : "";
    const status = payload.status;

    if (!id.trim()) {
      return NextResponse.json({ ok: false, error: "Missing row id" }, { status: 400 });
    }
    if (status !== "dismissed" && status !== "done" && status !== "active") {
      return NextResponse.json({ ok: false, error: "Invalid status" }, { status: 400 });
    }

    await setPenaltyReviewResolution(id, status);
    return NextResponse.json({ ok: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

