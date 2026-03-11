import { BASE_URL } from "@/lib/config";

export const dynamic = "force-static";

export async function GET() {
  const body = [
    "# Il Margine",
    "",
    "> Data-driven betting analysis and transparent track record.",
    "",
    "## Canonical",
    `${BASE_URL}`,
    "",
    "## Key Pages",
    `- Home: ${BASE_URL}/`,
    `- Tennis Tips: ${BASE_URL}/tennis-tips`,
    `- ATP Tennis: ${BASE_URL}/atp-tennis`,
    `- Track Record: ${BASE_URL}/track-record`,
    `- The Edge: ${BASE_URL}/the-edge`,
    `- FAQ: ${BASE_URL}/faq`,
    `- Resources: ${BASE_URL}/resources`,
    `- Roger (chat assistant): ${BASE_URL}/resources/roger`,
    "",
    "## Discovery",
    `- Sitemap: ${BASE_URL}/sitemap.xml`,
    `- Robots: ${BASE_URL}/robots.txt`,
    "",
    "## Policies",
    `- Disclaimer: ${BASE_URL}/disclaimer`,
    `- Privacy Policy: ${BASE_URL}/privacy-policy`,
    `- Cookies Policy: ${BASE_URL}/cookies-policy`,
  ].join("\n");

  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
