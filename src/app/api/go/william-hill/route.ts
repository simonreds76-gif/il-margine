import { NextResponse } from "next/server";

/** William Hill affiliate click-tracking URL (C.ashx). Redirects to William Hill with your btag/affid/siteid/adid. */
const WH_AFFILIATE_URL =
  "https://campaigns.williamhill.com/C.ashx?btag=a_214702b_1456c_&affid=1744894&siteid=214702&adid=1456&c=";

export async function GET() {
  return NextResponse.redirect(WH_AFFILIATE_URL, 302);
}
