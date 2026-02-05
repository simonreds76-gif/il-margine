import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Privacy Policy | Il Margine";
const url = `${BASE_URL}/privacy-policy`;

export const metadata: Metadata = {
  title,
  alternates: { canonical: url },
  robots: { index: true, follow: true },
};

export default function PrivacyPolicyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
