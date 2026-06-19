import { ImageResponse } from "next/og";
import { BASE_URL } from "@/lib/config";
import { getBookmakerLogoPath } from "@/lib/bookmaker-logos";

export const runtime = "edge";

const size = {
  width: 1200,
  height: 675,
};

function param(url: URL, key: string, fallback = ""): string {
  return (url.searchParams.get(key) || fallback).trim();
}

function truncate(value: string, max: number): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, Math.max(0, max - 1)).trimEnd()}…`;
}

function bookmakerLogoUrl(bookmaker: string): string | null {
  const path = getBookmakerLogoPath(bookmaker);
  if (!path) return null;
  return `${BASE_URL}${path}`;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const event = truncate(param(url, "event", "World Cup"), 64);
  const player = truncate(param(url, "player"), 46);
  const selection = truncate(param(url, "selection", "Selection"), 58);
  const odds = truncate(param(url, "odds", "-"), 12);
  const stake = truncate(param(url, "stake", "-"), 10);
  const bookmaker = truncate(param(url, "bookmaker", "Bookmaker"), 22);
  const matchDate = truncate(param(url, "date", ""), 18);
  const logoUrl = bookmakerLogoUrl(bookmaker);
  const pickLine = player ? `${player} · ${selection}` : selection;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 54,
          color: "#f8fafc",
          background:
            "radial-gradient(circle at 16% 18%, rgba(16,185,129,0.34), transparent 30%), radial-gradient(circle at 90% 22%, rgba(245,158,11,0.20), transparent 28%), linear-gradient(135deg, #050812 0%, #08111d 46%, #02040a 100%)",
          fontFamily: "Arial, sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            background:
              "linear-gradient(90deg, rgba(16,185,129,0.10) 1px, transparent 1px), linear-gradient(0deg, rgba(16,185,129,0.08) 1px, transparent 1px)",
            backgroundSize: "42px 42px",
            opacity: 0.32,
          }}
        />

        <div style={{ position: "relative", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                color: "#34d399",
                fontSize: 26,
                letterSpacing: 5,
                textTransform: "uppercase",
                fontWeight: 800,
              }}
            >
              Il Margine WC Pick
            </div>
            <div style={{ marginTop: 10, color: "#cbd5e1", fontSize: 28, fontWeight: 700 }}>{event}</div>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              border: "1px solid rgba(52,211,153,0.45)",
              borderRadius: 999,
              padding: "12px 20px",
              color: "#ecfdf5",
              fontSize: 22,
              fontWeight: 800,
              background: "rgba(6,78,59,0.38)",
            }}
          >
            Free World Cup Picks
          </div>
        </div>

        <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", flexDirection: "column", width: 760 }}>
            <div style={{ color: "#ffffff", fontSize: 60, fontWeight: 900, lineHeight: 1.05 }}>
              {pickLine}
            </div>
            <div style={{ marginTop: 24, display: "flex", alignItems: "center" }}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  padding: "18px 28px",
                  borderRadius: 22,
                  background: "rgba(15,23,42,0.82)",
                  border: "1px solid rgba(148,163,184,0.26)",
                }}
              >
                <span style={{ color: "#94a3b8", fontSize: 20, textTransform: "uppercase", letterSpacing: 2 }}>Odds</span>
                <span style={{ color: "#f8fafc", fontSize: 48, fontWeight: 900 }}>{odds}</span>
              </div>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  marginLeft: 16,
                  padding: "18px 28px",
                  borderRadius: 22,
                  background: "rgba(15,23,42,0.82)",
                  border: "1px solid rgba(148,163,184,0.26)",
                }}
              >
                <span style={{ color: "#94a3b8", fontSize: 20, textTransform: "uppercase", letterSpacing: 2 }}>Stake</span>
                <span style={{ color: "#34d399", fontSize: 48, fontWeight: 900 }}>{stake}</span>
              </div>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              width: 300,
              minHeight: 250,
              borderRadius: 34,
              background: "linear-gradient(180deg, rgba(248,250,252,0.95), rgba(226,232,240,0.92))",
              border: "2px solid rgba(251,191,36,0.80)",
              padding: 26,
            }}
          >
            {logoUrl ? (
              <img
                src={logoUrl}
                alt={bookmaker}
                style={{
                  width: 230,
                  height: 110,
                  objectFit: "contain",
                }}
              />
            ) : (
              <div style={{ color: "#0f172a", fontSize: 40, fontWeight: 900, textAlign: "center" }}>{bookmaker}</div>
            )}
            <div style={{ marginTop: 20, color: "#0f172a", fontSize: 26, fontWeight: 900 }}>{bookmaker}</div>
          </div>
        </div>

        <div
          style={{
            position: "relative",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            color: "#cbd5e1",
            fontSize: 24,
          }}
        >
          <div style={{ display: "flex", color: "#fbbf24", fontWeight: 800 }}>{matchDate || "World Cup 2026"}</div>
          <div style={{ display: "flex", color: "#34d399", fontWeight: 900 }}>ilmargine.bet</div>
        </div>
      </div>
    ),
    size,
  );
}
