export function DisclosureCue() {
  return <span className="ip-disclosure-cue">
    <span className="ip-disclosure-closed">Click to expand</span>
    <span className="ip-disclosure-open">Click to collapse</span>
    <span className="ip-disclosure-arrow" aria-hidden="true"><svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="m6 9 6 6 6-6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
  </span>;
}
