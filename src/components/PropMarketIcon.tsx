import type { PropKey } from "@/lib/prop-performance";

// One small, local vector family. Labels carry the accessible market names.
  const art = {
    saves: <><path d="M10 27 7 20 4 15q-1-3 2-3l4 4V7q0-3 3-2v8-9q3-2 4 1v8-7q3-2 4 1v7-4q3-2 4 1v9l-4 7Z" fill="currentColor" fillOpacity=".12"/><path d="M10 21q5-5 11 0M11 27h10"/><path d="m27 4 1 3 3 1" stroke="#e2e8f0"/></>,
    shots: <><path d="M3 8h10M2 14h8M5 22h5" opacity=".55"/><circle cx="21" cy="18" r="9"/><path d="m21 13 5 4-2 6h-6l-2-6Z" fill="currentColor" fillOpacity=".2"/><path d="m21 9 0 4m8 2-3 2m0 9-2-3m-8 3 2-3m-6-8 4 2"/></>,
    sot: <><path d="M3 27V8h26v19M3 13h14M3 19h11M9 8v19M15 8v7M21 8v5" opacity=".5"/><circle cx="23" cy="22" r="7"/><circle cx="23" cy="22" r="2" fill="currentColor"/><path d="m17 16 3 3m6 6 3 3" stroke="#e2e8f0"/></>,
    tackles: <><path d="m5 6 7 1-1 11 7 3q4 0 4 4H4v-7Z" fill="currentColor" fillOpacity=".12"/><path d="M5 28v-3m6 3v-3m6 3v-3m-6-11 4 1m-4 2 4 1"/><circle cx="25" cy="11" r="5"/><path d="m23 10 3-1 2 3-3 2Z" fill="currentColor" fillOpacity=".3"/></>,
    fouls: <><path d="m16 12 10-4 2 6-11 4a7 7 0 1 1-1-6Z" fill="currentColor" fillOpacity=".12"/><circle cx="10" cy="18" r="2.5"/><path d="m22 4 1-2m6 4 2-1M4 27l4 2 5-3"/><path d="m17 25 5 5m0-5-5 5" stroke="#e2e8f0"/></>,
    foulsWon: <><path d="m16 12 10-4 2 6-11 4a7 7 0 1 1-1-6Z" fill="currentColor" fillOpacity=".12"/><circle cx="10" cy="18" r="2.5"/><path d="m22 4 1-2m6 4 2-1"/><path d="m19 26 3 3 7-7" stroke="#e2e8f0"/></>,
    cards: <><rect x="5" y="6" width="15" height="21" rx="2" transform="rotate(-12 12 16)" opacity=".5"/><rect x="13" y="4" width="14" height="21" rx="2" fill="currentColor" fillOpacity=".18"/><path d="M17 20h6" stroke="#e2e8f0"/></>,
    goals: <><path d="M3 26V7h26v19M3 12h26M9 7v19M16 7v8M23 7v8" opacity=".5"/><circle cx="21" cy="23" r="7" fill="#101a23"/><path d="m21 19 4 3-2 4h-4l-2-4Z" fill="currentColor" fillOpacity=".25"/><path d="m12 19 3 2M8 23h4" stroke="#e2e8f0"/></>,
    assists: <><circle cx="6" cy="24" r="3" fill="currentColor" fillOpacity=".2"/><path d="M6 16V9q0-4 4-4h16m-5-4 5 4-5 4"/><path d="M12 17h17v12H12ZM17 17v12m6-12v12M12 23h17" opacity=".5"/><circle cx="20" cy="23" r="2" fill="currentColor" stroke="none"/></>,
    passes: <><circle cx="6" cy="9" r="4" fill="currentColor" fillOpacity=".15"/><circle cx="26" cy="23" r="4" fill="currentColor" fillOpacity=".15"/><path d="M13 8h10q3 0 3 4v3m-3-3 3 3 3-3M19 24H9q-3 0-3-4v-3m-3 3 3-3 3 3"/></>,
    offsides: <><path d="M7 29V3h19l-4 6 4 6H7"/><path d="M8 4h9v5H8Zm9 5h7v5h-7Z" fill="currentColor" fillOpacity=".2" stroke="none"/><path d="M3 29h26" opacity=".5"/></>,
    team: <><path d="m11 5-7 4-3 6 5 3 3-4v14h14V14l3 4 5-3-3-6-7-4q-5 5-10 0Z" fill="currentColor" fillOpacity=".12"/><path d="M13 14h6m-6 4h6m-6 4h3" stroke="#e2e8f0"/></>,
    other: <><rect x="3" y="3" width="10" height="10" rx="2" fill="currentColor" fillOpacity=".16"/><rect x="19" y="3" width="10" height="10" rx="2"/><rect x="3" y="19" width="10" height="10" rx="2"/><path d="M19 24h10m-5-5v10"/></>,
  };
export default function PropMarketIcon({ market, className = "h-8 w-8" }: { market: PropKey; className?: string }) {
  return <svg className={className} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{art[market]}</svg>;
}
