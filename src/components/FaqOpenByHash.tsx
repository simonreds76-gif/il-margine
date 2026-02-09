"use client";

import { useEffect } from "react";

/**
 * On load (and when hash changes), scroll to the element with id=hash and open it if it's a <details>.
 */
export default function FaqOpenByHash() {
  useEffect(() => {
    const hash = typeof window !== "undefined" ? window.location.hash.slice(1) : "";
    if (!hash) return;
    const el = document.getElementById(hash);
    if (el?.tagName === "DETAILS") (el as HTMLDetailsElement).open = true;
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash.slice(1);
      if (!hash) return;
      const el = document.getElementById(hash);
      if (el?.tagName === "DETAILS") (el as HTMLDetailsElement).open = true;
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return null;
}
