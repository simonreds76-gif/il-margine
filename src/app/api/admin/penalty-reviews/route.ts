import { NextResponse } from "next/server";
import { revalidatePath, revalidateTag } from "next/cache";
import { randomUUID } from "node:crypto";
import { isAdminSession } from "@/lib/admin-auth";
import { penaltyAdminReport } from "@/lib/penalty-admin-reader";
import { readPenaltyEditorial, savePenaltyEditorial, PENALTY_EDITORIAL_TAG } from "@/lib/penalty-editorial-store";
import { editorialChange } from "@/lib/penalty-editorial";
import { CLUB_PENALTY_SEASON } from "@/lib/club-penalty-takers";
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
const json = (body: unknown, status = 200) => NextResponse.json(body, {status, headers: {"Cache-Control": "private, no-store"}});
export async function GET() {
  if (!await isAdminSession()) return json({error: "Sign in to Admin."}, 401);
  try {return json({ok: true, report: await penaltyAdminReport()});}
  catch {return json({error: "Review data is unavailable. Reload to try again; no saved decisions were changed."}, 503);}
}
export async function POST(request: Request) {
  if (!await isAdminSession()) return json({error: "Sign in to Admin."}, 401);
  if (request.headers.get("origin") !== new URL(request.url).origin) return json({error: "Same-origin Admin request required."}, 403);
  try {
    const raw = await request.text();
    if (raw.length > 8000) return json({error: "Request too large."}, 413);
    const c = JSON.parse(raw);
    if (!c || !["done", "defer", "reopen", "save"].includes(c.action) || !Number.isInteger(c.revision) || typeof c.ticket !== "string" || typeof c.club !== "string" || c.ticket.length > 600 || c.club.length > 180 || (c.reason !== undefined && typeof c.reason !== "string") || (c.source !== undefined && typeof c.source !== "string")) return json({error: "Invalid review request."}, 400);
    const report = await penaltyAdminReport();
    const ticket = report.tickets.find(t => t.id === c.ticket);
    const club = report.clubs.find(t => t.id === c.club);
    if ((c.ticket && !ticket) || (!c.ticket && c.action !== "save")) return json({error: "Ticket is no longer available. Reload the reviews."}, 409);
    if (c.action === "save" && (!club || (ticket && ticket.clubId !== club.id))) return json({error: "The club does not match this ticket. Review its identity before editing."}, 400);
    const state = await readPenaltyEditorial();
    if (state.revision !== c.revision) return json({error: "The review changed in another tab. Reload before saving."}, 409);
    const payload = editorialChange(state, c, club?.order ?? null, CLUB_PENALTY_SEASON, new Date().toISOString(), randomUUID());
    const revision = await savePenaltyEditorial(state.revision, payload);
    if (c.action === "save" && club) {
      try {
        revalidateTag(PENALTY_EDITORIAL_TAG, {expire: 0});
        revalidatePath("/penalty-takers", "layout");
      } catch {return json({ok: true, revision, warning: "Order saved, but page refresh could not be confirmed. Do not repeat the save; contact support."});}
    }
    return json({ok: true, revision, message: c.action === "done" ? "Review closed. The hierarchy is unchanged." : c.action === "save" ? "Hierarchy saved. Public pages will use the new order on their next load." : "Review updated."});
  } catch (e) {
    const message = e instanceof Error ? e.message : "Save was not confirmed. Reload before retrying.";
    return json({error: message}, message.startsWith("CONFLICT") ? 409 : 400);
  }
}
