import { NextResponse } from "next/server";

const WH_AFFILIATE_URL =
  "https://click.trafficguard.ai/william_hill_affiliate/d/property_id=tg-007324-001;;dp_source_id=utm_term;;dp_campaign_id=utm_campaign;;site_id=utm_term;;destination_url=https://register.williamhill.com/";

export async function GET() {
  return NextResponse.redirect(WH_AFFILIATE_URL, 302);
}
