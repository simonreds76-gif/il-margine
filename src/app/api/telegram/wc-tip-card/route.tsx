import { ImageResponse } from "next/og";
import { resolveBookmakerLogo } from "@/lib/bookmaker-logos";

export const runtime = "edge";

const size = {
  width: 1200,
  height: 675,
};

type BookmakerCardTheme = {
  background: string;
  border: string;
  accent: string;
  accentSoft: string;
  logoFrame: string;
  logoFit?: "contain" | "cover";
  label: string;
};

const DEFAULT_BOOKMAKER_THEME: BookmakerCardTheme = {
  background: "linear-gradient(145deg, rgba(10,20,34,0.98), rgba(4,12,23,0.98))",
  border: "rgba(52,211,153,0.42)",
  accent: "#34d399",
  accentSoft: "rgba(52,211,153,0.14)",
  logoFrame: "rgba(248,250,252,0.94)",
  label: "#f8fafc",
};

const BOOKMAKER_THEMES: Record<string, BookmakerCardTheme> = {
  "10bet": {
    background: "linear-gradient(145deg, #05070a 0%, #111827 52%, #020617 100%)",
    border: "rgba(255,255,255,0.72)",
    accent: "#f8fafc",
    accentSoft: "rgba(255,255,255,0.12)",
    logoFrame: "#ffffff",
    label: "#f8fafc",
  },
  "888sport": {
    background: "linear-gradient(145deg, #06140d 0%, #0f3a23 58%, #111827 100%)",
    border: "rgba(16,185,129,0.62)",
    accent: "#10b981",
    accentSoft: "rgba(16,185,129,0.18)",
    logoFrame: "rgba(3,10,8,0.70)",
    label: "#ecfdf5",
  },
  bet365: {
    background: "linear-gradient(145deg, #06130b 0%, #063f25 52%, #111827 100%)",
    border: "rgba(255,228,24,0.62)",
    accent: "#ffe418",
    accentSoft: "rgba(255,228,24,0.16)",
    logoFrame: "rgba(4,16,10,0.82)",
    label: "#fefce8",
  },
  betfair: {
    background: "linear-gradient(145deg, #191302 0%, #5a4304 48%, #050812 100%)",
    border: "rgba(255,186,0,0.72)",
    accent: "#ffba00",
    accentSoft: "rgba(255,186,0,0.18)",
    logoFrame: "rgba(255,246,205,0.94)",
    label: "#fef3c7",
  },
  betfred: {
    background: "linear-gradient(145deg, #091a3a 0%, #113c87 46%, #7f0715 100%)",
    border: "rgba(239,68,68,0.70)",
    accent: "#ef4444",
    accentSoft: "rgba(59,130,246,0.20)",
    logoFrame: "rgba(248,250,252,0.96)",
    logoFit: "cover",
    label: "#eff6ff",
  },
  betmgm: {
    background: "linear-gradient(145deg, #070605 0%, #1f1608 48%, #06080d 100%)",
    border: "rgba(212,175,55,0.72)",
    accent: "#d4af37",
    accentSoft: "rgba(212,175,55,0.16)",
    logoFrame: "rgba(5,5,5,0.62)",
    label: "#fef3c7",
  },
  betvictor: {
    background: "linear-gradient(145deg, #050812 0%, #10233f 52%, #0b1a2b 100%)",
    border: "rgba(96,165,250,0.58)",
    accent: "#60a5fa",
    accentSoft: "rgba(96,165,250,0.16)",
    logoFrame: "rgba(248,250,252,0.96)",
    label: "#eff6ff",
  },
  betway: {
    background: "linear-gradient(145deg, #030712 0%, #0f172a 54%, #111827 100%)",
    border: "rgba(148,163,184,0.54)",
    accent: "#f8fafc",
    accentSoft: "rgba(148,163,184,0.14)",
    logoFrame: "rgba(3,7,18,0.70)",
    label: "#f8fafc",
  },
  boylesports: {
    background: "linear-gradient(145deg, #03120b 0%, #087343 56%, #04111f 100%)",
    border: "rgba(34,197,94,0.66)",
    accent: "#22c55e",
    accentSoft: "rgba(34,197,94,0.18)",
    logoFrame: "rgba(3,12,8,0.72)",
    label: "#dcfce7",
  },
  bwin: {
    background: "linear-gradient(145deg, #030712 0%, #111827 50%, #292524 100%)",
    border: "rgba(250,204,21,0.60)",
    accent: "#facc15",
    accentSoft: "rgba(250,204,21,0.14)",
    logoFrame: "rgba(248,250,252,0.95)",
    label: "#fef9c3",
  },
  coral: {
    background: "linear-gradient(145deg, #07131f 0%, #003c70 48%, #04101a 100%)",
    border: "rgba(56,189,248,0.58)",
    accent: "#38bdf8",
    accentSoft: "rgba(56,189,248,0.16)",
    logoFrame: "rgba(248,250,252,0.96)",
    label: "#e0f2fe",
  },
  ladbrokes: {
    background: "linear-gradient(145deg, #200405 0%, #a30d16 52%, #09090b 100%)",
    border: "rgba(248,113,113,0.68)",
    accent: "#f87171",
    accentSoft: "rgba(248,113,113,0.16)",
    logoFrame: "rgba(248,250,252,0.96)",
    label: "#fee2e2",
  },
  midnite: {
    background: "linear-gradient(145deg, #04020b 0%, #241052 56%, #030712 100%)",
    border: "rgba(168,85,247,0.62)",
    accent: "#a855f7",
    accentSoft: "rgba(168,85,247,0.16)",
    logoFrame: "rgba(248,250,252,0.96)",
    label: "#f3e8ff",
  },
  paddypower: {
    background: "linear-gradient(145deg, #02140a 0%, #006b36 54%, #03110a 100%)",
    border: "rgba(34,197,94,0.70)",
    accent: "#22c55e",
    accentSoft: "rgba(34,197,94,0.18)",
    logoFrame: "rgba(248,250,252,0.96)",
    label: "#dcfce7",
  },
  pinnacle: {
    background: "linear-gradient(145deg, #050812 0%, #2b2110 54%, #070707 100%)",
    border: "rgba(245,158,11,0.66)",
    accent: "#f59e0b",
    accentSoft: "rgba(245,158,11,0.18)",
    logoFrame: "rgba(255,251,235,0.96)",
    label: "#fef3c7",
  },
  sbk: {
    background: "linear-gradient(145deg, #07110f 0%, #12382f 54%, #050b0a 100%)",
    border: "rgba(12,205,147,0.72)",
    accent: "#0ccd93",
    accentSoft: "rgba(12,205,147,0.18)",
    logoFrame: "rgba(248,250,252,0.98)",
    label: "#d1fae5",
  },
  skybet: {
    background: "linear-gradient(145deg, #061637 0%, #0f4db3 50%, #9f1239 100%)",
    border: "rgba(59,130,246,0.70)",
    accent: "#60a5fa",
    accentSoft: "rgba(239,68,68,0.16)",
    logoFrame: "rgba(248,250,252,0.96)",
    label: "#eff6ff",
  },
  spreadex: {
    background: "linear-gradient(145deg, #071923 0%, #0d3a49 56%, #4a0a17 100%)",
    border: "rgba(200,16,46,0.72)",
    accent: "#c8102e",
    accentSoft: "rgba(52,115,135,0.22)",
    logoFrame: "rgba(248,250,252,0.96)",
    logoFit: "contain",
    label: "#ecfeff",
  },
  unibet: {
    background: "linear-gradient(145deg, #020b08 0%, #063e2b 56%, #030712 100%)",
    border: "rgba(0,206,0,0.66)",
    accent: "#00ce00",
    accentSoft: "rgba(0,206,0,0.16)",
    logoFrame: "rgba(2,8,6,0.74)",
    label: "#dcfce7",
  },
  virginbet: {
    background: "linear-gradient(145deg, #210205 0%, #d90913 50%, #04070d 100%)",
    border: "rgba(248,113,113,0.72)",
    accent: "#ef4444",
    accentSoft: "rgba(255,255,255,0.14)",
    logoFrame: "rgba(248,250,252,0.98)",
    label: "#fee2e2",
  },
  williamhill: {
    background: "linear-gradient(145deg, #03112f 0%, #073a82 54%, #07101f 100%)",
    border: "rgba(250,204,21,0.64)",
    accent: "#facc15",
    accentSoft: "rgba(250,204,21,0.16)",
    logoFrame: "rgba(248,250,252,0.96)",
    label: "#fef9c3",
  },
};

function param(url: URL, key: string, fallback = ""): string {
  return (url.searchParams.get(key) || fallback).trim();
}

function truncate(value: string, max: number): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, Math.max(0, max - 1)).trimEnd()}...`;
}

function resolveBookmakerCard(bookmaker: string, origin: string) {
  const resolved = resolveBookmakerLogo(bookmaker);
  const key = resolved?.key ?? "generic";
  const path =
    resolved?.paths[0] ?? null;
  return {
    key,
    displayName: resolved?.displayName ?? bookmaker,
    logoUrl: path ? new URL(path, origin).toString() : null,
    theme: BOOKMAKER_THEMES[key] ?? DEFAULT_BOOKMAKER_THEME,
  };
}
function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}

async function fetchImageDataUrl(imageUrl: string | null): Promise<string | null> {
  if (!imageUrl) return null;
  try {
    const response = await fetch(imageUrl, { cache: "force-cache" });
    const contentType = response.headers.get("content-type") || "image/png";
    if (!response.ok || !contentType.toLowerCase().startsWith("image/")) return null;
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (!bytes.length) return null;
    return `data:${contentType};base64,${bytesToBase64(bytes)}`;
  } catch {
    return null;
  }
}
export async function GET(request: Request) {
  const url = new URL(request.url);
  const worldCup = param(url, "scope", "worldcup") === "worldcup";
  const event = truncate(param(url, "event", worldCup ? "World Cup" : "Player props"), 64);
  const player = truncate(param(url, "player"), 46);
  const selection = truncate(param(url, "selection", "Selection"), 58);
  const odds = truncate(param(url, "odds", "-"), 12);
  const stake = truncate(param(url, "stake", "-"), 10);
  const bookmakerParam = param(url, "bookmaker", "Bookmaker");
  const matchDate = truncate(param(url, "date", ""), 18);
  const bookmakerCard = resolveBookmakerCard(bookmakerParam, url.origin);
  const bookmakerName = truncate(bookmakerCard.displayName, 22);
  const logoUrl = bookmakerCard.logoUrl;
  const logoDataUrl = await fetchImageDataUrl(logoUrl);
  const logoTheme = bookmakerCard.theme;
  const pickLine = player ? `${player} - ${selection}` : selection;

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
              {worldCup ? "Il Margine WC Pick" : "Il Margine Player Prop"}
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
            {worldCup ? "World Cup Archive" : "Free Pick Alerts"}
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
              width: 322,
              minHeight: 266,
              borderRadius: 36,
              background: logoTheme.background,
              border: `2px solid ${logoTheme.border}`,
              padding: 22,
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                position: "absolute",
                top: -70,
                right: -50,
                width: 180,
                height: 180,
                borderRadius: 999,
                background: logoTheme.accentSoft,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: 0,
                height: 8,
                background: logoTheme.accent,
              }}
            />
            <div
              style={{
                position: "relative",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "100%",
                height: 132,
                borderRadius: 26,
                background: logoTheme.logoFrame,
                border: "1px solid rgba(255,255,255,0.24)",
                padding: 18,
              }}
            >
            {logoDataUrl ? (
              <img
                src={logoDataUrl}
                alt={bookmakerName}
                style={{
                  width: 264,
                  height: 108,
                  objectFit: logoTheme.logoFit ?? "contain",
                }}
              />
            ) : (
              <div style={{ color: logoTheme.accent, fontSize: 40, fontWeight: 900, textAlign: "center" }}>{bookmakerName}</div>
            )}
            </div>
            <div
              style={{
                position: "relative",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginTop: 18,
                padding: "10px 16px",
                borderRadius: 999,
                background: "rgba(2,6,23,0.42)",
                border: `1px solid ${logoTheme.border}`,
                color: logoTheme.label,
                fontSize: 28,
                fontWeight: 900,
                letterSpacing: 0.2,
                textAlign: "center",
                minWidth: 226,
              }}
            >
              {bookmakerName}
            </div>
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
