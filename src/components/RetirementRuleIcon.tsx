import type { RetirementRuleFamily } from "@/lib/tennis-retirement-rules";

/** A ball, a completed set, a protected stake and a finished match. */
export default function RetirementRuleIcon({ family }: { family: RetirementRuleFamily }) {
  return <svg className="retirement-rule-icon" viewBox="0 0 48 48" fill="none" aria-hidden="true" focusable="false">
    <rect x="2" y="2" width="44" height="44" rx="13" fill="#19392f" stroke="#609a83" />
    {family === "point" ? <><circle cx="24" cy="24" r="13" fill="#a8ecd0" /><path d="M14 15c9 4 13 12 15 21M34 15c-6 4-11 10-19 17" stroke="#254e40" strokeWidth="2.5" /></> : family === "set" ? <><rect x="11" y="13" width="26" height="23" rx="4" stroke="#c8ede1" strokeWidth="2" /><path d="M11 20h26M19 10v6m10-6v6m-11 12 4 4 9-9" stroke="#a8ecd0" strokeWidth="2.5" strokeLinecap="round" /></> : family === "protection" ? <><path d="m24 10 12 5v10c0 7-7 12-12 15-5-3-12-8-12-15V15Z" fill="#a8ecd0" /><path d="M30 23a7 7 0 1 0-2 8m2-13v6h-6" stroke="#254e40" strokeWidth="2.3" strokeLinecap="round" /></> : <><path d="M15 12v26m1-24h19l-4 7 4 7H16" stroke="#c8ede1" strokeWidth="2.5" strokeLinejoin="round" /><path d="m22 20 3 3 6-7" stroke="#a8ecd0" strokeWidth="2.5" strokeLinecap="round" /></>}
  </svg>;
}
