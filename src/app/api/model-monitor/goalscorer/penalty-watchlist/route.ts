import { NextResponse } from "next/server";

import { setPenaltyReviewResolution } from "@/lib/goalscorer-penalty-review-state";

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
