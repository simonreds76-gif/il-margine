type AbstractJerseyProps = {
  teamPrimaryColor: string;
  teamSecondaryColor?: string;
  playerNumber: string;
  accentEmerald?: boolean;
};

export function AbstractJersey({
  teamPrimaryColor,
  teamSecondaryColor = "#0f172a",
  playerNumber,
  accentEmerald = true,
}: AbstractJerseyProps) {
  const accent = accentEmerald ? "#34d399" : teamSecondaryColor;
  const safeId = `${playerNumber}-${teamPrimaryColor}-${teamSecondaryColor}`.replace(
    /[^a-zA-Z0-9_-]/g,
    "",
  );

  return (
    <svg
      aria-hidden="true"
      className="h-auto w-full drop-shadow-[0_24px_45px_rgba(16,185,129,0.14)]"
      viewBox="0 0 220 250"
    >
      <defs>
        <linearGradient id={`jersey-${safeId}`} x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor={teamPrimaryColor} />
          <stop offset="100%" stopColor={teamSecondaryColor} />
        </linearGradient>
        <filter id={`jersey-glow-${safeId}`} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feColorMatrix
            in="blur"
            type="matrix"
            values="0 0 0 0 0.203 0 0 0 0 0.827 0 0 0 0 0.6 0 0 0 0.35 0"
          />
          <feMerge>
            <feMergeNode />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <path
        d="M65 34 28 58 14 116l36 13 12-39v116h96V90l12 39 36-13-14-58-37-24-25 19H90L65 34Z"
        fill={`url(#jersey-${safeId})`}
        filter={`url(#jersey-glow-${safeId})`}
        stroke="rgba(226,232,240,0.28)"
        strokeWidth="2"
      />
      <path
        d="M88 53c6 11 14 16 22 16s16-5 22-16"
        fill="none"
        stroke="rgba(15,23,42,0.75)"
        strokeLinecap="round"
        strokeWidth="8"
      />
      <path
        d="M58 96h104M62 130h96M62 164h96"
        stroke={accent}
        strokeLinecap="round"
        strokeOpacity="0.38"
        strokeWidth="2"
      />
      <path
        d="M76 54 56 204M144 54l20 150"
        stroke={accent}
        strokeOpacity="0.42"
        strokeWidth="2"
      />
      <text
        x="110"
        y="145"
        fill="rgba(248,250,252,0.96)"
        fontFamily="ui-sans-serif, system-ui, sans-serif"
        fontSize="64"
        fontWeight="900"
        letterSpacing="-4"
        textAnchor="middle"
      >
        {playerNumber}
      </text>
      <path
        d="M52 213h116"
        stroke={accent}
        strokeLinecap="round"
        strokeOpacity="0.8"
        strokeWidth="3"
      />
    </svg>
  );
}
