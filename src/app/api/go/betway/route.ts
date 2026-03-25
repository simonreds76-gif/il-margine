import { NextResponse } from "next/server";

const BETWAY_AFFILIATE_URL =
  "https://betway.com/bwp/bet10get40/en-gb/?s=sp51997";

export async function GET() {
  return NextResponse.redirect(BETWAY_AFFILIATE_URL, 302);
}
