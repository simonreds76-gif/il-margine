import Link from "next/link";
import SportIcon from "./SportIcon";
export default function SportCta({ sport, label, href }: { sport: "football" | "tennis"; label?: string; href?: string }) {
  return <Link href={href ?? (sport === "football" ? "/player-props" : "/tennis-tips")} prefetch={false} className="sport-cta">
    <span className="sport-cta-emblem"><SportIcon sport={sport} emblem className="h-full w-full" /></span>
    <span className="sport-cta-label">{label ?? (sport === "football" ? "Player Props Tips" : "ATP Tennis Tips")}</span>
    <svg aria-hidden="true" viewBox="0 0 24 24" className="sport-cta-arrow" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M4 12h15m-6-6 6 6-6 6"/></svg>
  </Link>;
}
