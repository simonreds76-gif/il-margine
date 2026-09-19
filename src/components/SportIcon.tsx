type Sport = "football" | "tennis" | "all" | "compare";

/** Shared, decorative sport marks; the adjoining text supplies the label. */
export default function SportIcon({ sport, className = "h-6 w-6", emblem = false }: { sport: Sport; className?: string; emblem?: boolean }) {
  return <svg aria-hidden="true" focusable="false" viewBox="0 0 32 32" className={`shrink-0 ${className}`} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    {sport === "football" ? <>
      <circle cx="14" cy="14" r="11" />
      <path d="m14 8 5.7 4.1-2.2 6.7h-7l-2.2-6.7L14 8Z" fill="currentColor" stroke="none" />
      <path d="M14 8V3m5.7 9.1 4.8-1.6m-7 8.3 3 4.1m-10-4.1-3 4.1m.8-10.7-4.8-1.6" />
      {emblem && <g className="text-emerald-300" stroke="none"><path d="M17 22h4v7h-4zm6-4h4v11h-4zm6-5h3v16h-3z" fill="#0f1117" stroke="#0f1117" strokeWidth="3"/><path d="M17 22h4v7h-4zm6-4h4v11h-4zm6-5h3v16h-3z" fill="currentColor"/></g>}
    </> : sport === "tennis" ? <>
      <g transform="rotate(36 14 14)"><ellipse cx="14" cy="11" rx="7" ry="9"/><path d="M14 20v9m-2-1h4M11 4v14m6-14v14M8 8h12M7 12h14M9 16h10"/><path d="M13 22h2v7h-2z" fill="currentColor"/></g>
      <circle cx="25" cy="25" r="5" className="text-emerald-300" fill="currentColor" stroke="none"/><path d="M22 29c4-1 1-7 6-7" stroke="#0f1117" strokeWidth="1.5"/>
    </> : sport === "all" ? <g fill="currentColor" stroke="none"><circle cx="10" cy="10" r="4"/><circle cx="22" cy="10" r="4"/><circle cx="10" cy="22" r="4"/><circle cx="22" cy="22" r="4"/></g> : <><path d="M5 10h22M5 22h22"/><circle cx="12" cy="10" r="3" fill="#0f1117"/><circle cx="21" cy="22" r="3" fill="#0f1117"/></>}
  </svg>;
}
