/** Small, decorative symbols for record metrics; the label carries the meaning. */
export default function RecordIcon({ name, className = "h-6 w-6" }: { name: "roi" | "bets" | "calendar"; className?: string }) {
  return <svg aria-hidden="true" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
    {name === "roi" && <><path d="M5 5v22h23M10 21l6-7 5 3 6-10m-7 0h7v7" /><path d="M10 26v-5m6 5V14m5 12v-9" opacity=".3" /></>}
    {name === "bets" && <><rect x="7" y="5" width="20" height="24" rx="4" /><path d="M12 12l2 2 3-4m3 2h3m-11 8 2 2 3-4m3 2h3" /></>}
    {name === "calendar" && <><rect x="4" y="7" width="24" height="22" rx="4" /><path d="M10 3v8m12-8v8M4 15h24m-17 6h2m6 0h2" /></>}
  </svg>;
}
