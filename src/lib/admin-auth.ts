import { cookies } from "next/headers";
import { createHmac } from "crypto";

const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
const COOKIE_NAME = "admin_session";

function getSignedToken(): string {
  if (!ADMIN_PASSWORD) return "";
  return createHmac("sha256", ADMIN_PASSWORD).update(COOKIE_NAME).digest("base64url");
}

export async function isAdminSession(): Promise<boolean> {
  if (!ADMIN_PASSWORD) return false;
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;
  return token === getSignedToken();
}
