export type PerformanceFilterIconName = "all" | "football" | "tennis";

/** Optical-size glyphs for the monthly record's compact filter buttons. */
export default function PerformanceFilterIcon({
  name,
  className = "",
}: {
  name: PerformanceFilterIconName;
  className?: string;
}) {
  return (
    <svg
      className={`performance-filter-icon performance-filter-icon--${name} ${className}`}
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {name === "all" && (
        <>
          <rect x="3.75" y="3.75" width="6.5" height="6.5" rx="1.4" />
          <rect x="13.75" y="3.75" width="6.5" height="6.5" rx="1.4" fill="#9ce9c9" stroke="#9ce9c9" />
          <rect x="3.75" y="13.75" width="6.5" height="6.5" rx="1.4" />
          <rect x="13.75" y="13.75" width="6.5" height="6.5" rx="1.4" />
        </>
      )}
      {name === "football" && (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 3v4.3m8.56 1.92-4.47 1.45m1.2 8.61-2.77-3.81m-7.81 3.81 2.77-3.81M3.44 9.22l4.47 1.45" />
          <path d="m12 7.3 4.47 3.25-1.71 5.25H9.24l-1.71-5.25Z" fill="#9ce9c9" stroke="none" />
        </>
      )}
      {name === "tennis" && (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="M5.3 6c4.8 2.8 4.8 9.2 0 12M18.7 6c-4.8 2.8-4.8 9.2 0 12" stroke="#9ce9c9" />
        </>
      )}
    </svg>
  );
}
