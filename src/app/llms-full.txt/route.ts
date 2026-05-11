import { BASE_URL } from "@/lib/config";

export const dynamic = "force-static";

export async function GET() {
  const body = [
    "# Il Margine (Full Index)",
    "",
    "> Extended page index for LLM crawlers and retrieval systems.",
    "",
    "## Main",
    `- ${BASE_URL}/`,
    `- ${BASE_URL}/tennis-tips`,
    `- ${BASE_URL}/player-props`,
    `- ${BASE_URL}/fair-odds-lab`,
    `- ${BASE_URL}/atp-tennis`,
    `- ${BASE_URL}/track-record`,
    `- ${BASE_URL}/the-edge`,
    `- ${BASE_URL}/faq`,
    `- ${BASE_URL}/resources`,
    `- ${BASE_URL}/resources/roger`,
    `- ${BASE_URL}/resources/closing-line-value`,
    `- ${BASE_URL}/resources/kelly-criterion-sports-betting`,
    `- ${BASE_URL}/calculator`,
    `- ${BASE_URL}/fair-odds`,
    "",
    "## Supporting",
    `- ${BASE_URL}/contact`,
    `- ${BASE_URL}/cookies-policy`,
    `- ${BASE_URL}/privacy-policy`,
    `- ${BASE_URL}/disclaimer`,
    "",
    "## Discovery",
    `- ${BASE_URL}/sitemap.xml`,
    `- ${BASE_URL}/robots.txt`,
    `- ${BASE_URL}/llms.txt`,
  ].join("\n");

  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
