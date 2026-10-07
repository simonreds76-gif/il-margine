import styles from "./TipsHubIntro.module.css";

export default function TipsCompetitionToolbar({ sport }: { sport: "football" | "tennis" }) {
  return <div className={styles.filterToolbar}>
    <p>Filter by {sport === "football" ? "league" : "competition"} <span>· Picks &amp; results</span></p>
    <nav aria-label="On this page" className={styles.sectionLinks}>
      <a href="#picks">Current picks <span aria-hidden="true">↓</span></a>
      <a href="#competition-record">Results &amp; ROI <span aria-hidden="true">↓</span></a>
      <a href="#how-to-use">How it works <span aria-hidden="true">↓</span></a>
    </nav>
  </div>;
}
