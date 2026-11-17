import Link from "next/link";
import ToolEmblem from "@/components/ToolEmblem";

/*
 * Onward routes from an individual tip. Fable, 17 Nov 2026. PREVIEW.
 * Presentational only: no data, no fetch, no state, no analytics. Two links at most.
 * The research route is chosen by SPORT only (the same Return Atlas route and wording the tips pages already
 * use). It never names a player, club or fixture, so it cannot point at research that does not exist.
 * Styles live in src/app/tip-detail.css, which both tip pages import.
 */
type OnwardRoute = { href: string; emblem: "record" | "football" | "tennis"; kicker: string; title: string; note: string };

export default function TipOnward({ market, record = true }: { market: string; record?: boolean }) {
  const routes: OnwardRoute[] = [];
  if (record) {
    routes.push({ href: "/track-record", emblem: "record", kicker: "The public record", title: "Track record", note: "ROI, profit and results by month" });
  }
  if (market === "tennis") {
    routes.push({ href: "/return-atlas", emblem: "tennis", kicker: "Return Atlas · Tennis", title: "Player returns", note: "Betting history by odds and surface" });
  } else if (market === "props") {
    routes.push({ href: "/football-atlas", emblem: "football", kicker: "Return Atlas · Football", title: "Club returns", note: "Betting history by odds and venue" });
  }
  if (routes.length === 0) return null;

  return (
    <nav className="tip-onward" aria-label="Continue from this tip">
      <p className="tip-onward-title">Where next</p>
      <ul>
        {routes.map((route) => (
          <li key={route.href}>
            <Link prefetch={false} href={route.href}>
              <ToolEmblem name={route.emblem} className="tip-onward-emblem" />
              <span className="tip-onward-text">
                <small>{route.kicker}</small>
                <strong>{route.title}</strong>
                <span>{route.note}</span>
              </span>
              <svg className="tip-onward-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
                <path d="M5 12h14m-6-6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
