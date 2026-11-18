"use client";

import { useEffect } from "react";

/** Reveal the containing family for saved links, including streamed specialist panels. */
export default function MonitorFragment() {
  useEffect(() => {
    let pending: MutationObserver | undefined;
    function follow() {
      pending?.disconnect();
      const hash = location.hash.slice(1);
      if (!hash) return;
      function reveal() {
        const target = document.getElementById(hash);
        if (!target) return false;
        const family = target.closest<HTMLDetailsElement>("details[data-model-family]");
        if (family) {
          family.open = true;
          target.scrollIntoView({block: "start"});
        }
        return true;
      }
      if (!reveal()) {
        pending = new MutationObserver(() => { if (reveal()) pending?.disconnect(); });
        pending.observe(document.querySelector("main") ?? document.body, {childList: true, subtree: true});
      }
    }
    follow();
    window.addEventListener("hashchange", follow);
    return () => { pending?.disconnect(); window.removeEventListener("hashchange", follow); };
  }, []);
  return null;
}
