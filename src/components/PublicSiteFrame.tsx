"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/** Keep the public design system out of admin and local research tools. */
export default function PublicSiteFrame({ children }: { children: ReactNode }) {
  const path = usePathname();
  const internal = /^\/(model-monitor|admin|dev|ops)(\/|$)/.test(path);
  return <div className={`site-content w-full min-h-screen${internal ? "" : " public-site"}`}>{children}</div>;
}
