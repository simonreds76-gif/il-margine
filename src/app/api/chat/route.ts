// Retired endpoint: old tabs must never trigger model or database requests.
export function POST() {
  return Response.json({ error: "This service has been retired." }, { status: 410 });
}

export const GET = POST;
