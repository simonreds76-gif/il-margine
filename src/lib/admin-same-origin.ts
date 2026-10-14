// Next may reconstruct request.url with an internal hostname behind a proxy.
// Compare the browser Origin with the externally requested Host instead.
export function isAdminSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    const parsed = new URL(origin);
    const host = request.headers.get("host") || new URL(request.url).host;
    return ["https:", "http:"].includes(parsed.protocol) && parsed.host.toLowerCase() === host.toLowerCase();
  } catch { return false; }
}
