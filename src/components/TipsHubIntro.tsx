import Link from "next/link";
import ToolEmblem from "./ToolEmblem";
import PageHomeLink from "./PageHomeLink";
import styles from "./TipsHubIntro.module.css";

export default function TipsHubIntro({ sport }: { sport: "tennis" | "football" }) {
  const tennis = sport === "tennis";
  return <section className={styles.hero} aria-labelledby="tips-title">
    <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
      <PageHomeLink />
      <p className="site-eyebrow">{tennis ? "Tennis analysis" : "Football player props"}</p>
      <div className={styles.title}>
        <ToolEmblem name={sport} className={styles.sportIcon} />
        <h1 id="tips-title">{tennis ? "Tennis Betting " : "Football Player Props "}<span>{tennis ? "Tips" : "Betting Tips"}</span></h1>
      </div>
      <div className={styles.details}>
        <p className={styles.copy}>{tennis
          ? "Tennis betting tips informed by statistical models and bookmaker prices. Explore ATP, Challenger and Grand Slam picks, then compare current selections and performance by competition."
          : "Football player props informed by statistical models and bookmaker prices. Explore shots, shots on target, fouls, tackles and cards, then compare picks and performance by league."}</p>
        <Link prefetch={false} href={tennis ? "/return-atlas" : "/football-atlas"} className={styles.atlasLink} aria-label={`Explore Return Atlas ${tennis ? "Tennis" : "Football"}`}>
          <span className={styles.atlasIcon}><ToolEmblem name={sport} className={styles.atlasEmblem} /></span>
          <span className={styles.atlasLabel}>
            <small>Return Atlas <span>· {tennis ? "Tennis" : "Football"}</span></small>
            <strong>{tennis ? "Player returns" : "Club returns"}</strong>
            <span>{tennis ? "Betting history by odds and surface" : "Betting history by odds and venue"}</span>
          </span>
          <span className={styles.arrow} aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><path d="M5 12h14m-6-6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
        </Link>
      </div>
    </div>
  </section>;
}
