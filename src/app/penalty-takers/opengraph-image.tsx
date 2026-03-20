import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Penalty Takers 2025/26 | Il Margine";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

const LEAGUES = ["Serie A", "Premier League", "La Liga", "Bundesliga", "Ligue 1"];

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          position: "relative",
          background: "#0f1117",
          color: "#f8fafc",
          fontFamily: "sans-serif",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(circle at top left, rgba(16,185,129,0.22), transparent 38%), radial-gradient(circle at bottom right, rgba(99,102,241,0.16), transparent 34%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 5,
            background: "linear-gradient(90deg, #10b981, #34d399, transparent)",
          }}
        />

        <div
          style={{
            zIndex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            padding: "64px 72px",
            width: "100%",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              fontSize: 22,
              letterSpacing: 4,
              textTransform: "uppercase",
              color: "#34d399",
              marginBottom: 26,
            }}
          >
            <div style={{ width: 36, height: 2, background: "#34d399" }} />
            <span>Il Margine Intelligence</span>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              fontSize: 78,
              lineHeight: 1.02,
              letterSpacing: -2.2,
              fontWeight: 700,
              maxWidth: 820,
            }}
          >
            <span>Penalty Takers</span>
            <span style={{ color: "#34d399" }}>2025/26</span>
          </div>

          <div
            style={{
              marginTop: 22,
              maxWidth: 860,
              fontSize: 30,
              lineHeight: 1.45,
              color: "#cbd5e1",
            }}
          >
            First, second and third-choice penalty takers for every club in Europe&apos;s top five leagues.
          </div>

          <div
            style={{
              display: "flex",
              gap: 14,
              flexWrap: "wrap",
              marginTop: 28,
            }}
          >
            {LEAGUES.map((league) => (
              <div
                key={league}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "10px 16px",
                  borderRadius: 999,
                  border: "1px solid rgba(148,163,184,0.25)",
                  background: "rgba(15,23,42,0.55)",
                  fontSize: 22,
                  color: "#cbd5e1",
                }}
              >
                {league}
              </div>
            ))}
          </div>

          <div
            style={{
              marginTop: 46,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              width: "100%",
              fontSize: 22,
              color: "#64748b",
            }}
          >
            <span>96 teams tracked</span>
            <span>ilmargine.bet</span>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
