export type FootballAtlasIconName = 'all' | 'favourite' | 'underdog' | 'team' | 'opponent' | 'draw';
/** A sportsbook-ticket family. Visible labels carry meaning; adjacent icons are decorative. */
export default function FootballAtlasIcon({ name, className = '', label }: { name: FootballAtlasIconName; className?: string; label?: string }) {
 const marketRole = name === 'favourite' || name === 'underdog';
 return <svg viewBox="0 0 56 56" width="48" height="48" className={`fa-ticket-icon ${className}`} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" focusable="false" role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
  {name === 'all' && <path d="M15 7h31v35" opacity=".45"/>}
  <path d="M10 11h32a3 3 0 0 1 3 3v9a5 5 0 0 0 0 10v14l-5-3-5 3-5-3-5 3-5-3-5 3-5-3-3 2V33a5 5 0 0 0 0-10v-9a3 3 0 0 1 3-3Z" fill="currentColor" fillOpacity=".07"/>
  <path d="M14 18h11m-11 20h24" opacity=".5"/>
  {marketRole ? <>
   {/* An illustrative pair, not fixed classification thresholds. */}
   <text x="26" y="27" textAnchor="middle" fontSize="9" fontWeight={name === 'favourite' ? '800' : '400'} fill="currentColor" stroke="none" opacity={name === 'favourite' ? 1 : .45}>1.80</text>
   <text x="26" y="36" textAnchor="middle" fontSize="9" fontWeight={name === 'underdog' ? '800' : '400'} fill="currentColor" stroke="none" opacity={name === 'underdog' ? 1 : .45}>3.20</text>
   <path d={name === 'favourite' ? 'm36 23 2 2 4-4' : 'm36 32 2 2 4-4'} strokeWidth="2"/>
  </> : name === 'draw' ? <path d="M19 25h14m-14 6h14" strokeWidth="3"/> : <>
   <rect x="13" y="24" width="10" height="10" rx="3" fill="currentColor" fillOpacity={name === 'team' ? .35 : .05}/>
   <rect x="29" y="24" width="10" height="10" rx="3" fill="currentColor" fillOpacity={name === 'opponent' ? .35 : .05}/>
   {name === 'team' && <path d="m15 29 2 2 4-5" strokeWidth="2"/>}{name === 'opponent' && <path d="m31 29 2 2 4-5" strokeWidth="2"/>}
  </>}
 </svg>;
}
