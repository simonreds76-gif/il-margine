export type LabIconKind = "comparisons" | "matches" | "hits" | "guide" | "leagues";

/** Decorative section markers; the adjacent label always supplies the meaning. */
export function LabIcon({ kind }: { kind: LabIconKind }) {
  return <svg className="ip-lab-icon" width="28" height="28" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {kind === "comparisons" && <><rect x="4" y="5" width="24" height="22" rx="4"/><path d="M16 5v22M8 11h4m8 0h4M8 17h4m8 6v-6m4 6v-9"/><circle cx="10" cy="22" r="1" fill="currentColor" stroke="none"/></>}
    {kind === "matches" && <><rect x="3" y="6" width="26" height="20" rx="3"/><path d="M16 6v20M3 12h5v8H3m26-8h-5v8h5"/><circle cx="16" cy="16" r="4"/></>}
    {kind === "hits" && <><path d="M7 4h18v7c0 7-4 10-9 10s-9-3-9-10V4Zm0 3H3v4c0 4 3 5 5 5m17-9h4v4c0 4-3 5-5 5M16 21v7m-6 0h12"/><path d="m11 12 3 3 7-7"/></>}
    {kind === "guide" && <><path d="M16 7C12 4 7 4 3 5v21c5-1 9-1 13 2 4-3 8-3 13-2V5c-4-1-9-1-13 2v21M7 11l5 1m-5 5 5 1m8-6 5-1m-5 7 5-1"/></>}
    {kind === "leagues" && <><rect x="4" y="4" width="9" height="9" rx="2"/><rect x="19" y="4" width="9" height="9" rx="2"/><rect x="4" y="19" width="9" height="9" rx="2"/><rect x="19" y="19" width="9" height="9" rx="2"/></>}
  </svg>;
}
