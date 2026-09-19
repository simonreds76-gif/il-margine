"use client";

import { useEffect, useRef, useState } from "react";
import { decodeAtlas } from "./decode.mjs";
import { mountAtlas } from "./atlas-ui.mjs";

type Props = { indexUrl: string; detailsBase: string; version: string; checkedAt: string };

export default function ReturnAtlasClient({ indexUrl, detailsBase, version, checkedAt }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    const node = root.current;
    let dispose: (() => void) | undefined;
    if (!node) return;
    const read = async (url: string) => {
      const request = new AbortController();
      const cancel = () => request.abort();
      abort.signal.addEventListener("abort", cancel, { once: true });
      if (abort.signal.aborted) request.abort();
      const timeout = setTimeout(cancel, 20000);
      try {
        const response = await fetch(url, { signal: request.signal });
        if (!response.ok) throw new Error(`Return Atlas asset unavailable: ${response.status}`);
        return await response.json();
      } finally {
        clearTimeout(timeout);
        abort.signal.removeEventListener("abort", cancel);
      }
    };
    void read(indexUrl).then((index) => {
      if (abort.signal.aborted) return;
      const data = decodeAtlas(index, checkedAt);
      dispose = mountAtlas(node, data, async (id: string) => {
        if (!data.players.some((player: { id: string }) => player.id === id)) throw new Error("Unknown player");
        const detail = await read(`${detailsBase}/${encodeURIComponent(id)}.json`);
        if (detail.schema !== 1 || detail.version !== version || detail.playerId !== id || !Array.isArray(detail.matches)) throw new Error("Player release mismatch");
        return detail.matches;
      });
    }).catch((cause: unknown) => {
      if (!abort.signal.aborted) {
        if (process.env.NODE_ENV === "development") console.error("Return Atlas could not initialise", cause);
        setError(true);
      }
    });
    return () => { abort.abort(); dispose?.(); };
  }, [indexUrl, detailsBase, version, checkedAt, attempt]);

  return <>
    {error && <div role="alert" className="rounded-xl border border-slate-700 p-6 text-slate-200"><p>The player records couldn’t load. Please check your connection and try again.</p><button type="button" className="mt-3 min-h-11 rounded-lg bg-emerald-400 px-5 font-semibold text-slate-950" onClick={() => { setError(false); setAttempt((value) => value + 1); }}>Try again</button></div>}
    <div ref={root} hidden={error}><p role="status" className="py-8 text-slate-300">Loading player records…</p></div>
    <noscript><p>Enable JavaScript to search players and filter their historical returns.</p></noscript>
  </>;
}
