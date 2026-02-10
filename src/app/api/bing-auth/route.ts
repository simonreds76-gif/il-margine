/** Serves Bing Webmaster verification file with correct Content-Type. */

const BING_AUTH_XML = `<?xml version="1.0"?>
<users>
\t<user>FD4A9F8A7202C71E5465E6A51F6B8F62</user>
</users>
`;

export async function GET() {
  return new Response(BING_AUTH_XML, {
    headers: {
      "Content-Type": "application/xml",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
