"use client";
import { useEffect, useRef } from "react";

export default function ManagerClient({ html, indexUrl }: { html: string; indexUrl: string }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = host.current;
    if (!node) return;
    const controller = new AbortController();
    node.innerHTML = html;
    import("./runtime/panel.mjs").then(({ mountManagers }) => {
      if (!controller.signal.aborted) return mountManagers(node, indexUrl, controller.signal);
    }).catch(() => {
      const status = node.querySelector('[role="status"]');
      if (status && !controller.signal.aborted) status.textContent = "The archive could not load. Please reload to try again.";
    });
    return () => controller.abort();
  }, [html, indexUrl]);
  return <div ref={host} dangerouslySetInnerHTML={{ __html: html }} />;
}
