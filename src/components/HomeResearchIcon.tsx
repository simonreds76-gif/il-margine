export type HomeResearchIconName = "football" | "tennis" | "penalty" | "record";

/** Decorative research emblems. The neighbouring heading supplies the link name. */
export default function HomeResearchIcon({
  name,
  className = "",
}: {
  name: HomeResearchIconName;
  className?: string;
}) {
  const mint = "#9ce9c9";
  const ivory = "#f1f0dd";
  const ink = "#112724";
  const line = "#46665c";

  return (
    <svg
      className={`home-research-icon home-research-icon--${name} ${className}`}
      width="48"
      height="48"
      viewBox="0 0 64 64"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="1" y="1" width="62" height="62" rx="17" fill={ink} />
      <path d="M18 1.75h28A16.25 16.25 0 0 1 62.25 18v28A16.25 16.25 0 0 1 46 62.25H18A16.25 16.25 0 0 1 1.75 46V18A16.25 16.25 0 0 1 18 1.75Z" stroke={line} strokeWidth="1.5" />
      <g strokeLinecap="round" strokeLinejoin="round">
        {name === "football" && (
          <>
            <path d="m11 14 10-3 10 3v11c0 6-4 10-10 13-6-3-10-7-10-13Z" fill={ivory} />
            <path d="m33 14 10-3 10 3v11c0 6-4 10-10 13-6-3-10-7-10-13Z" fill={mint} />
            <path d="M17 17v11m8-11v11M15 22h12" stroke={ink} strokeWidth="2.2" />
            <path d="m39 18 8 11m0-11-8 11" stroke={ink} strokeWidth="2.2" />
            <circle cx="21" cy="43" r="3.5" fill={ivory} />
            <circle cx="43" cy="43" r="3.5" fill={mint} />
            <path d="M14 55v-2a7 7 0 0 1 14 0v2M36 55v-2a7 7 0 0 1 14 0v2" fill={ivory} />
            <path d="M36 55v-2a7 7 0 0 1 14 0v2" fill={mint} />
            <path d="m19 49 2 3 2-3m18 0 2 3 2-3" stroke={ink} strokeWidth="1.5" />
            <path d="M31 44h2m-2 7h2" stroke={line} strokeWidth="1.5" />
          </>
        )}
        {name === "tennis" && (
          <>
            <path d="M11 14h17v29H11zM36 14h17v29H36z" stroke={line} strokeWidth="1.5" />
            <path d="M32 11v32" stroke={line} strokeWidth="1.5" strokeDasharray="2 4" />
            <circle cx="20" cy="24" r="5" fill={ivory} />
            <circle cx="44" cy="24" r="5" fill={mint} />
            <path d="M12 41v-3a8 8 0 0 1 16 0v3Z" fill={ivory} />
            <path d="M36 41v-3a8 8 0 0 1 16 0v3Z" fill={mint} />
            <path d="M17 33a3 3 0 0 0 6 0m18 0a3 3 0 0 0 6 0" stroke={ink} strokeWidth="1.5" />
            <path d="M12 51h10m20 0h10" stroke={line} strokeWidth="1.5" />
            <circle cx="32" cy="51" r="7" fill={mint} />
            <path d="M27 46c5 1 6 7 3 11m4-13c-3 4-2 9 3 11" stroke={ink} strokeWidth="1.3" />
          </>
        )}
        {name === "penalty" && (
          <>
            <path d="M11 36V14h42v22" stroke={ivory} strokeWidth="3" />
            <path d="M18 16v19m9-19v19m10-19v19m9-19v19M13 23h38M13 31h38" stroke={line} strokeWidth="1.2" />
            <path d="m8 42 6-7h36l6 7M8 53h48" stroke={line} strokeWidth="1.5" />
            <circle cx="44" cy="22" r="5" fill={mint} />
            <circle cx="44" cy="22" r="1.6" fill={ink} />
            <path d="M29 44c1-8 4-14 9-18" stroke={mint} strokeWidth="1.8" strokeDasharray="2 4" />
            <circle cx="27" cy="50" r="7" fill={ivory} />
            <path d="m27 46 3 2-1 4h-4l-1-4Z" fill={ink} />
            <path d="m24 48-3-1m9 1 3-1m-4 5 2 3m-6-3-2 3" stroke={ink} strokeWidth="1.2" />
          </>
        )}
        {name === "record" && (
          <>
            <path d="M16 11h26l8 8v34H16Z" fill={ivory} />
            <path d="M42 11v9h8" fill="#bed2bd" />
            <path d="M23 22h10M23 30h17M23 37h10M23 44h7" stroke={ink} strokeWidth="2" />
            <path d="M12 17v36a4 4 0 0 0 4 4h20" stroke={line} strokeWidth="1.5" />
            <circle cx="44" cy="45" r="12" fill={mint} stroke={ink} strokeWidth="2.5" />
            <path d="m38.5 45 3.5 3.5 7.5-8" stroke={ink} strokeWidth="2.5" />
          </>
        )}
      </g>
    </svg>
  );
}
