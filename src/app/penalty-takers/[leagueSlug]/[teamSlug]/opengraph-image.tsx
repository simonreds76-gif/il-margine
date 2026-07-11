import { ImageResponse } from "next/og";
import { BASE_URL } from "@/lib/config";
import { getClubPenaltyTeam } from "@/lib/club-penalty-takers";

export const alt = "Club penalty taker hierarchy | Il Margine";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

type ImageProps = { params: Promise<{ leagueSlug: string; teamSlug: string }> };

export default async function Image({ params }: ImageProps) {
  const { leagueSlug, teamSlug } = await params;
  const team = await getClubPenaltyTeam(leagueSlug, teamSlug);
  if (!team) throw new Error("Club penalty taker not found");

  return new ImageResponse(
    (
      <div style={{ height: "100%", width: "100%", display: "flex", position: "relative", overflow: "hidden", background: "#070d11", color: "#f8fafc", fontFamily: "sans-serif" }}>
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 10% 15%, rgba(16,185,129,.22), transparent 34%), radial-gradient(circle at 92% 90%, rgba(59,130,246,.15), transparent 38%)" }} />
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 6, background: "linear-gradient(90deg,#10b981,#34d399,transparent)" }} />
        <div style={{ width: "100%", padding: "58px 70px", display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16, color: "#34d399", fontSize: 20, letterSpacing: 4, textTransform: "uppercase" }}>
              <span style={{ width: 34, height: 2, background: "#34d399" }} />
              <span>Il Margine Intelligence</span>
            </div>
            <span style={{ padding: "9px 16px", border: "1px solid rgba(52,211,153,.35)", borderRadius: 999, color: "#a7f3d0", fontSize: 18 }}>{team.seasonLabel}</span>
          </div>

          <div style={{ marginTop: 54, display: "flex", alignItems: "center", gap: 34 }}>
            <div style={{ height: 126, width: 126, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 30, background: "#fff", border: "1px solid rgba(255,255,255,.18)" }}>
              {team.logoPath ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={`${BASE_URL}${team.logoPath}`} alt="" width="88" height="88" style={{ objectFit: "contain" }} />
              ) : (
                <span style={{ fontSize: 38, fontWeight: 700, color: "#0f172a" }}>{team.initials}</span>
              )}
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ color: "#94a3b8", fontSize: 24 }}>{team.leagueLabel}</div>
              <div style={{ marginTop: 6, display: "flex", fontSize: 55, lineHeight: 1.05, fontWeight: 700, letterSpacing: -1.5 }}>
                <span>{team.team} penalty taker</span>
              </div>
            </div>
          </div>

          <div style={{ marginTop: 48, display: "flex", alignItems: "stretch", gap: 16 }}>
            {[
              ["First choice", team.primary],
              ["Second choice", team.secondary],
              ["Status", team.isArchived ? "Archived" : team.hierarchyStatus === "unknown" ? "Not verified" : team.hierarchyStatus],
            ].map(([label, value], index) => (
              <div key={label} style={{ flex: 1, display: "flex", flexDirection: "column", padding: "18px 22px", borderRadius: 20, border: "1px solid rgba(148,163,184,.20)", background: "rgba(15,23,42,.65)" }}>
                <span style={{ color: "#64748b", fontSize: 16, textTransform: "uppercase", letterSpacing: 2 }}>{label}</span>
                <span style={{ marginTop: 8, color: index === 0 ? "#6ee7b7" : "#e2e8f0", fontSize: 27, fontWeight: 600, textTransform: label === "Status" ? "capitalize" : "none" }}>{value}</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: "auto", display: "flex", justifyContent: "space-between", color: "#64748b", fontSize: 19 }}>
            <span>Evidence-led. Human reviewed.</span><span>ilmargine.bet</span>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
