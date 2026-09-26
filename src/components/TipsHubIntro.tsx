import Link from "next/link";
import ToolEmblem from "./ToolEmblem";
import PageHomeLink from "./PageHomeLink";

export default function TipsHubIntro({ sport }: { sport: "tennis" | "football" }) {
  const tennis = sport === "tennis";
  return <section className="public-hub-heading tips-hub-intro">
    <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
      <PageHomeLink />
      <div className="tips-intro-layout">
        <div>
          <p className="site-eyebrow">{tennis ? "Tennis analysis" : "Football player props"}</p>
          <div className="tips-intro-title"><ToolEmblem name={sport} /><h1>{tennis ? "Tennis Betting " : "Football Player Props "}<span>{tennis ? "Tips" : "Betting Tips"}</span></h1></div>
          <p className="tips-intro-copy">{tennis
            ? "ATP, Challenger and Grand Slam betting picks informed by our models and the available price. Choose a competition to compare current selections, recorded odds, stakes and results — including losing bets."
            : "Football player betting picks across shots, fouls, tackles and cards, assessed against our models and the available price. Choose a league to compare current selections, recorded stakes and results — including losing bets."}</p>
        </div>
        <Link prefetch={false} href={tennis ? "/return-atlas" : "/football-atlas"} className="tips-atlas-link" aria-label={`Explore Return Atlas ${tennis ? "Tennis" : "Football"}`}>
          <ToolEmblem name={sport} className="tool-emblem--compact" />
          <span><small>Research the history</small><strong>Return Atlas · {tennis ? "Tennis" : "Football"}</strong><span>{tennis ? "Compare player returns by odds and surface" : "Compare club returns by odds and venue"}</span></span>
          <b aria-hidden="true">↗</b>
        </Link>
      </div>
    </div>
  </section>;
}
