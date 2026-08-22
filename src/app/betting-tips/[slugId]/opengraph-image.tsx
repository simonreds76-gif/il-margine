import { ImageResponse } from "next/og";
import { fetchSeoTipFixture } from "@/lib/tip-seo-server";

export const alt = "Il Margine betting preview";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const revalidate = 86400;

interface ImageProps {
  params: Promise<{ slugId: string }>;
}

export default async function Image({ params }: ImageProps) {
  const { slugId } = await params;
  const fixture = await fetchSeoTipFixture(slugId);
  const event = fixture?.seed.event || "Il Margine betting preview";
  const eyebrow = fixture?.seed.market === "props" ? "PLAYER PROPS" : "TENNIS MATCH";
  const pickCount = fixture?.bets.length || 0;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          position: "relative",
          overflow: "hidden",
          color: "#f8fafc",
          background: "linear-gradient(135deg, #070a0f 0%, #0b1514 52%, #07100d 100%)",
          padding: "68px 76px",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div
          style={{
            position: "absolute",
            width: 560,
            height: 560,
            borderRadius: 560,
            top: -250,
            left: -100,
            background: "rgba(16,185,129,0.17)",
            filter: "blur(4px)",
          }}
        />
        <div
          style={{
            position: "absolute",
            width: 420,
            height: 420,
            borderRadius: 420,
            right: -100,
            bottom: -190,
            background: "rgba(245,158,11,0.11)",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 28,
            border: "1px solid rgba(52,211,153,0.28)",
            borderRadius: 28,
          }}
        />

        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: "100%" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 64,
                  height: 64,
                  borderRadius: 18,
                  border: "1px solid rgba(52,211,153,0.48)",
                  color: "#6ee7b7",
                  fontSize: 31,
                  fontWeight: 900,
                }}
              >
                IM
              </div>
              <div style={{ display: "flex", fontSize: 28, fontWeight: 800, letterSpacing: "0.08em" }}>IL MARGINE</div>
            </div>
            <div
              style={{
                display: "flex",
                padding: "12px 20px",
                borderRadius: 999,
                border: "1px solid rgba(52,211,153,0.32)",
                background: "rgba(16,185,129,0.10)",
                color: "#6ee7b7",
                fontSize: 18,
                fontWeight: 700,
                letterSpacing: "0.16em",
              }}
            >
              {eyebrow} PREVIEW
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", maxWidth: 980 }}>
            <div style={{ display: "flex", color: "#fbbf24", fontSize: 21, fontWeight: 700, letterSpacing: "0.14em" }}>
              PREDICTION &amp; BETTING ANALYSIS
            </div>
            <div style={{ display: "flex", marginTop: 18, fontSize: event.length > 44 ? 52 : 66, lineHeight: 1.04, fontWeight: 900 }}>
              {event}
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", color: "#94a3b8", fontSize: 21 }}>
            <div style={{ display: "flex" }}>
              Posted prices | Tracked picks | Transparent settlement
            </div>
            <div style={{ display: "flex", color: "#e2e8f0", fontWeight: 700 }}>
              {pickCount} tracked {pickCount === 1 ? "selection" : "selections"}
            </div>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
