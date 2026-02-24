import { NextResponse } from "next/server";

const BWIN_AFFILIATE_URL = "https://mediaserver.entainpartners.com/renderBanner.do?zoneId=2190420";

export async function GET() {
  return NextResponse.redirect(BWIN_AFFILIATE_URL, 302);
}
