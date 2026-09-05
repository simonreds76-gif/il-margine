import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const url = request.nextUrl;

  if (url.pathname === "/" && url.searchParams.has("q")) {
    const canonicalUrl = new URL("/", request.url);
    return NextResponse.redirect(canonicalUrl, 308);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [{ source: "/", has: [{ type: "query", key: "q" }] }],
};
