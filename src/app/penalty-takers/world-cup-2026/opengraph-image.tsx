import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "World Cup 2026 Penalty Takers | Il Margine";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

const PILLS = ["42 qualified teams", "Country pages live", "11 Jun - 19 Jul 2026"];

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
              "radial-gradient(circle at top left, rgba(212,168,83,0.24), transparent 34%), radial-gradient(circle at bottom right, rgba(16,185,129,0.12), transparent 28%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 5,
            background: "linear-gradient(90deg, #d4a853, #10b981, transparent)",
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
              color: "#d4a853",
              marginBottom: 26,
            }}
          >
            <div style={{ width: 36, height: 2, background: "#d4a853" }} />
            <span>Il Margine Intelligence</span>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              fontSize: 74,
              lineHeight: 1.03,
              letterSpacing: -2.2,
              fontWeight: 700,
              maxWidth: 880,
            }}
          >
            <span>World Cup 2026</span>
            <span style={{ color: "#d4a853" }}>Penalty Takers</span>
          </div>

          <div
            style={{
              marginTop: 22,
              maxWidth: 880,
              fontSize: 30,
              lineHeight: 1.45,
              color: "#cbd5e1",
            }}
          >
            Tournament hub plus country pages for searches like Germany penalty taker, Brazil penalty taker and France penalty taker.
          </div>

          <div
            style={{
              display: "flex",
              gap: 14,
              flexWrap: "wrap",
              marginTop: 28,
            }}
          >
            {PILLS.map((pill) => (
              <div
                key={pill}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "10px 16px",
                  borderRadius: 999,
                  border: "1px solid rgba(212,168,83,0.25)",
                  background: "rgba(35,29,17,0.55)",
                  fontSize: 22,
                  color: "#f5e7c5",
                }}
              >
                {pill}
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
            <span>USA / Mexico / Canada</span>
            <span>ilmargine.bet</span>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
