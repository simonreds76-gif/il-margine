import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createHmac } from "crypto";
import { revalidatePath } from "next/cache";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { postPlayerPropTipToTelegram } from "@/lib/player-props-telegram";
import { slugifyTip } from "@/lib/slugify";
import { tipPreviewPath } from "@/lib/tip-seo";

const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
const COOKIE_NAME = "admin_session";
const PUBLIC_BET_PATHS = [
  "/",
  "/player-props",
  "/tennis-tips",
  "/track-record",
  "/calculator",
] as const;

type RevalidationBet = {
  id: number;
  market?: string | null;
  event?: string | null;
  match_date?: string | null;
};

const REVALIDATION_BET_COLUMNS = "id, market, event, match_date";

function revalidatePublicBetSurfaces(...bets: Array<RevalidationBet | null | undefined>) {
  for (const path of PUBLIC_BET_PATHS) {
    revalidatePath(path);
  }

  // Invalidate only the changed fixtures. Invalidating a route pattern here
  // causes every crawled tip page to regenerate and consume ISR writes.
  const tipPaths = new Set<string>();
  for (const bet of bets) {
    if (!bet?.id || !bet.event) continue;
    tipPaths.add(`/tips/${slugifyTip(bet.event, bet.id)}`);
    const previewPath = tipPreviewPath(bet);
    tipPaths.add(previewPath);
    tipPaths.add(`${previewPath}/opengraph-image`);
  }
  for (const path of tipPaths) {
    revalidatePath(path);
  }
}

function getSignedToken(): string {
  if (!ADMIN_PASSWORD) return "";
  return createHmac("sha256", ADMIN_PASSWORD).update("admin_session").digest("base64url");
}

async function isAdmin(): Promise<boolean> {
  if (!ADMIN_PASSWORD) return false;
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;
  return token === getSignedToken();
}

export async function POST(req: Request) {
  if (!(await isAdmin())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  let supabase;
  try {
    supabase = getSupabaseAdmin();
  } catch {
    return NextResponse.json({ error: "Server misconfigured: add SUPABASE_SERVICE_ROLE_KEY in Vercel." }, { status: 500 });
  }
  const body = await req.json();
  const { data, error } = await supabase
    .from("bets")
    .insert([body])
    .select("id, market, category, event, player, selection, odds, stake, match_date, notes, bookmaker:bookmakers(name, short_name)")
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });

  revalidatePublicBetSurfaces(data);

  const telegram = await postPlayerPropTipToTelegram(data);
  if (telegram.status === "failed") {
    console.warn("Player props Telegram post failed:", telegram.reason);
  }

  return NextResponse.json({ id: data.id, telegram });
}

export async function PUT(req: Request) {
  if (!(await isAdmin())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  let supabase;
  try {
    supabase = getSupabaseAdmin();
  } catch {
    return NextResponse.json({ error: "Server misconfigured: add SUPABASE_SERVICE_ROLE_KEY in Vercel." }, { status: 500 });
  }

  const { id, action } = await req.json();
  if (!id || action !== "post_telegram") {
    return NextResponse.json({ error: "id and action=post_telegram required" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("bets")
    .select("id, market, category, event, player, selection, odds, stake, match_date, notes, bookmaker:bookmakers(name, short_name)")
    .eq("id", Number(id))
    .single();
  if (error || !data) return NextResponse.json({ error: error?.message || "Bet not found" }, { status: 404 });

  const telegram = await postPlayerPropTipToTelegram(data);
  if (telegram.status === "failed") {
    console.warn("Player props Telegram retry failed:", telegram.reason);
    return NextResponse.json({ error: telegram.reason, telegram }, { status: 502 });
  }
  if (telegram.status !== "posted") {
    return NextResponse.json({ error: `Telegram not posted (${telegram.reason})`, telegram }, { status: 400 });
  }

  return NextResponse.json({ ok: true, telegram });
}

export async function PATCH(req: Request) {
  if (!(await isAdmin())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  let supabase;
  try {
    supabase = getSupabaseAdmin();
  } catch {
    return NextResponse.json({ error: "Server misconfigured: add SUPABASE_SERVICE_ROLE_KEY in Vercel." }, { status: 500 });
  }
  const { id, ...updates } = await req.json();
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });

  const { data: previousBet, error: previousError } = await supabase
    .from("bets")
    .select(REVALIDATION_BET_COLUMNS)
    .eq("id", Number(id))
    .single();
  if (previousError || !previousBet) {
    return NextResponse.json({ error: previousError?.message || "Bet not found" }, { status: 404 });
  }

  const { data: updatedBet, error } = await supabase
    .from("bets")
    .update(updates)
    .eq("id", Number(id))
    .select(REVALIDATION_BET_COLUMNS)
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  revalidatePublicBetSurfaces(previousBet, updatedBet);
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: Request) {
  if (!(await isAdmin())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  let supabase;
  try {
    supabase = getSupabaseAdmin();
  } catch {
    return NextResponse.json({ error: "Server misconfigured: add SUPABASE_SERVICE_ROLE_KEY in Vercel." }, { status: 500 });
  }
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });

  const { data: previousBet, error: previousError } = await supabase
    .from("bets")
    .select(REVALIDATION_BET_COLUMNS)
    .eq("id", Number(id))
    .single();
  if (previousError || !previousBet) {
    return NextResponse.json({ error: previousError?.message || "Bet not found" }, { status: 404 });
  }

  const { error } = await supabase.from("bets").delete().eq("id", Number(id));
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  revalidatePublicBetSurfaces(previousBet);
  return NextResponse.json({ ok: true });
}
