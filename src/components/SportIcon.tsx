import { useId } from "react";
type Sport = "football" | "tennis" | "all" | "compare";
/** Filled emblems from the approved CTA concept. Labels remain real text. */
export default function SportIcon({ sport, className = "h-6 w-6", emblem = false }: { sport: Sport; className?: string; emblem?: boolean }) {
  const id = useId().replaceAll(":", "");
  return <svg aria-hidden="true" focusable="false" viewBox="0 0 72 72" className={`shrink-0 ${className}`} fill="none">
    <defs>
      <linearGradient id={`${id}-white`} x1="10" y1="5" x2="58" y2="65" gradientUnits="userSpaceOnUse"><stop stopColor="#fff"/><stop offset="1" stopColor="#c1d1d9"/></linearGradient>
      <linearGradient id={`${id}-mint`} x1="35" y1="38" x2="68" y2="69" gradientUnits="userSpaceOnUse"><stop stopColor="#a4f3d6"/><stop offset="1" stopColor="#5fcda9"/></linearGradient>
      <clipPath id={`${id}-ball`}><circle cx="29" cy="31" r="25"/></clipPath>
      <clipPath id={`${id}-strings`}><ellipse cx="29" cy="25" rx="12" ry="18"/></clipPath>
    </defs>
    {sport === "football" ? <>
      <circle cx="29" cy="31" r="25" fill={`url(#${id}-white)`} stroke="#93acb7" strokeWidth=".8"/>
      <g clipPath={`url(#${id}-ball)`} fill="#17252b" stroke="#17252b" strokeWidth="1.4" strokeLinejoin="round">
        <path d="m29 19 10 7-4 12H23l-4-12 10-7Z"/>
        <path d="m17 5 11-3 12 5-5 6H23Zm32 10 11 11-2 11-8-3-4-11ZM47 48l-4 13-13 2-1-9 9-7ZM11 48l-4 12-9-12 5-13 8 3ZM1 12l9-9 8 8-5 11-11 2Z"/>
        <path d="M29 19v-6m10 13 7-3M35 38l3 9m-15-9-12 0m8-12-6-4" fill="none"/>
      </g>
      {emblem && <g fill={`url(#${id}-mint)`} stroke="#17252b" strokeWidth="2"><rect x="39" y="48" width="8" height="18" rx="2"/><rect x="50" y="40" width="8" height="26" rx="2"/><rect x="61" y="31" width="8" height="35" rx="2"/></g>}
    </> : sport === "tennis" ? <>
      <g transform="rotate(36 29 28)">
        <path d="M20 39 27 51h4l7-12-9 6Z" fill={`url(#${id}-white)`}/>
        <rect x="25.8" y="47" width="6.4" height="21" rx="2.5" fill={`url(#${id}-white)`}/>
        <ellipse cx="29" cy="25" rx="16" ry="22" fill={`url(#${id}-white)`}/>
        <ellipse cx="29" cy="25" rx="12.6" ry="18.6" fill="#18262f"/>
        <g clipPath={`url(#${id}-strings)`} stroke="#dce8ec" strokeWidth=".8" opacity=".85"><path d="M17 6v39M22 6v39M27 6v39M32 6v39M37 6v39M42 6v39M15 10h29M15 15h29M15 20h29M15 25h29M15 30h29M15 35h29M15 40h29"/></g>
      </g>
      <circle cx="57" cy="55" r="11" fill={`url(#${id}-mint)`}/><path d="M48 62c14-1 3-15 18-14" stroke="#183e38" strokeWidth="2.2"/>
    </> : sport === "all" ? <g fill="currentColor"><circle cx="23" cy="23" r="9"/><circle cx="49" cy="23" r="9"/><circle cx="23" cy="49" r="9"/><circle cx="49" cy="49" r="9"/></g> : <g stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M10 23h52M10 49h52"/><circle cx="26" cy="23" r="7" fill="#14212b"/><circle cx="47" cy="49" r="7" fill="#14212b"/></g>}
  </svg>;
}
