import { newsDate, outcomeLabel, type PenaltyArticle } from "@/lib/penalty-news";

// Generated at build time. No portrait downloads or per-share data requests.
export default function PenaltyNewsSocial({ article: a }: { article?: PenaltyArticle }) {
  return <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%", padding: "54px 64px", background: "#0f1720", color: "#f0f5f7", fontFamily: "sans-serif", position: "relative" }}>
    <div style={{ display: "flex", position: "absolute", top: 0, left: 0, right: 0, height: 7, background: "#9be6c5" }} />
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 24, color: "#a8becc" }}><span style={{ color: "#b7efd6", fontWeight: 700, letterSpacing: 3 }}>IL MARGINE</span><span>FOOTBALL · FROM THE SPOT</span></div>
    <div style={{ display: "flex", marginTop: 48, alignItems: "center", gap: 14, fontSize: 22, color: "#b7efd6" }}><span style={{ display: "flex", border: "2px solid #9be6c5", borderRadius: 30, width: 38, height: 38, alignItems: "center", justifyContent: "center" }}>●</span><span>PENALTY NEWS</span>{a && <span style={{ color: "#b3c4cf", marginLeft: 20 }}>{a.leagueLabel} · {newsDate(a.date)}</span>}</div>
    <div style={{ display: "flex", fontSize: a && a.player.length > 26 ? 54 : 68, lineHeight: 1.1, fontWeight: 700, letterSpacing: -2, marginTop: 28 }}>{a ? a.player : "The penalty. The outcome. The next taker."}</div>
    {a ? <><div style={{ display: "flex", marginTop: 22, fontSize: 32, color: a.outcome === "scored" ? "#b7efd6" : "#efc78e" }}>{outcomeLabel[a.outcome]} · {a.minute}′ penalty</div><div style={{ display: "flex", marginTop: 26, fontSize: 31, color: "#d4e0e8" }}>{a.home} {a.homeScore}–{a.awayScore} {a.away}</div></> : <div style={{ display: "flex", fontSize: 30, lineHeight: 1.5, marginTop: 22, color: "#b7cbd7", maxWidth: 980 }}>Completed-match reports and current club penalty-taker guides across Europe’s top five leagues.</div>}
    <div style={{ display: "flex", marginTop: "auto", borderTop: "1px solid #344853", paddingTop: 22, justifyContent: "space-between", fontSize: 22, color: "#a3bac8" }}><span>{a ? "Match report · Current taker order reviewed separately" : "The foul · The decision · The finish"}</span><span>ilmargine.bet</span></div>
  </div>;
}
