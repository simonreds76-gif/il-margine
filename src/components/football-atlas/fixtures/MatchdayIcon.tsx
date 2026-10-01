type Kind = 'histories' | 'outcomes' | 'returns';

/** Small, labelled elsewhere: paired rivals, three outcomes, and a return ledger. */
export default function MatchdayIcon({ kind }: { kind: Kind }) {
  return <svg aria-hidden="true" focusable="false" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    {kind === 'histories' ? <>
      <circle cx="11" cy="12" r="5" fill="#87e3bc" fillOpacity=".18" />
      <circle cx="29" cy="12" r="5" fill="#87e3bc" fillOpacity=".18" />
      <path d="M3 29v-2a8 8 0 0 1 15-4m19 6v-2a8 8 0 0 0-15-4M12 33h16m-13-3-3 3 3 3m10-6 3 3-3 3" />
    </> : kind === 'outcomes' ? <>
      <rect x="2" y="11" width="10" height="20" rx="3" fill="#87e3bc" fillOpacity=".12" />
      <rect x="15" y="7" width="10" height="24" rx="3" fill="#87e3bc" fillOpacity=".2" />
      <rect x="28" y="11" width="10" height="20" rx="3" fill="#87e3bc" fillOpacity=".12" />
      <path d="m6 19 2-1v7m10-6 4 5m0-5-4 5m13-5c0-3 5-3 5 0 0 2-5 3-5 6h5" />
    </> : <>
      <path d="M7 5h21l5 5v25H7Z" fill="#87e3bc" fillOpacity=".1" />
      <path d="M27 5v6h6M12 16h15M12 21h7m5 0h3M12 26h7m5 0h3M12 31h7m5 0h3" />
    </>}
  </svg>;
}
