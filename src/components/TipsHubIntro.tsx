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
            ? "ATP, Challenger and Grand Slam betting picks informed by statistical models and bookmaker prices. Browse current selections and compare performance by competition."
            : "Football player props tips informed by statistical models and bookmaker prices. Explore shots, shots on target, fouls, tackles and cards across the Premier League, Serie A and other competitions. Browse our latest selections and use the league filters to compare performance."}</p>
          {tennis && <Link className="mt-4 inline-flex items-center gap-2 text-sm text-emerald-200 underline underline-offset-4" href="/resources/tennis-retirement-rules">Player retires? Check your bookmaker’s rules ↗</Link>}
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
