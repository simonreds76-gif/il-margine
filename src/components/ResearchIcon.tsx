import type { SVGProps } from 'react';

export type ResearchIconName = 'matchday' | 'football' | 'managers' | 'tennis' | 'tennis-matchday' | 'matchup' | 'aerial' | 'height' | 'duel' | 'delivery';

/** Small optical icons, drawn on the same grid for every research tool. */
export default function ResearchIcon({ name, ...props }: SVGProps<SVGSVGElement> & { name: ResearchIconName }) {
  const drawings = {
    matchday: <><rect x="4" y="6" width="24" height="22" rx="4"/><path d="M10 3v6m12-6v6M4 12h24M9 18h4m6 0h4m-14 5h4"/><circle cx="22" cy="24" r="2"/></>,
    football: <><path d="M16 3 5 7v9c0 6 5 10 11 13 6-3 11-7 11-13V7Z"/><path d="m16 10 5 4-2 6h-6l-2-6Zm-5 4-5-2m7 8-3 4m9-4 3 4m-1-10 5-2"/></>,
    managers: <><circle cx="16" cy="9" r="5"/><path d="M5 28v-4c0-4 4-7 7-8l4 5 4-5c3 1 7 4 7 8v4M12 17l-2 7 6 5 6-5-2-7m-4 4v8"/><path d="M13 9h6" opacity=".5"/></>,
    tennis: <><circle cx="16" cy="16" r="12"/><path d="M6 9c7 0 10 5 10 7s3 7 10 7M9 26c0-7 5-10 7-10s7-3 7-10"/></>,
    'tennis-matchday': <><rect x="4" y="6" width="24" height="22" rx="4"/><path d="M10 3v6m12-6v6M4 12h24"/><circle cx="16" cy="20" r="5"/><path d="M12 17c4 0 4 6 8 6"/></>,
    matchup: <><rect x="3" y="6" width="26" height="20" rx="2"/><path d="M8 6v20m16-20v20M3 16h26M8 11h16M8 21h16m-8-10v10"/><circle cx="11" cy="13" r="2" fill="currentColor" stroke="none"/><circle cx="21" cy="19" r="2" fill="currentColor" stroke="none"/></>,
    aerial: <><path d="M5 28h22M8 25V13m-4 4 4-4 4 4m10 8V9m-4 4 4-4 4 4"/><circle cx="16" cy="6" r="3"/><path d="M14 15c-1 4 0 7 3 10" strokeDasharray="2 3"/></>,
    height: <><path d="M7 26V6m-4 4 4-4 4 4m-8 12 4 4 4-4"/><rect x="17" y="4" width="10" height="24" rx="2"/><path d="M22 10h5m-3 6h3m-5 6h5"/></>,
    duel: <><circle cx="9" cy="10" r="3"/><circle cx="24" cy="10" r="3"/><circle cx="16" cy="4" r="2"/><path d="m3 20 6-6 6 4m-6-4v8l-5 7m5-7 5 6m4-10 6-4 5 6m-5-6v8l-5 6m5-6 5 7"/></>,
    delivery: <><path d="M5 28V4l11 4-11 4m0 16h23M5 21a7 7 0 0 1 7 7M13 16c8-5 14-1 14 6m-4-3 4 3 3-4"/><circle cx="14" cy="16" r="2" fill="currentColor" stroke="none"/></>,
  };
  return <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{drawings[name]}</svg>;
}
