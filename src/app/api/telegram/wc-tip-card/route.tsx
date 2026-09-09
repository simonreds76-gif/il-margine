import { ImageResponse } from "next/og";
import { resolveBookmakerLogo } from "@/lib/bookmaker-logos";
import { TELEGRAM_BRAND_ASSETS } from "@/lib/telegram-brand-assets";

export const runtime = "edge";

function label(url: URL, name: string, fallback = "", max = 70) {
  const text = (url.searchParams.get(name) || fallback).replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max - 3).trimEnd()}...` : text;
}

export function GET(request: Request) {
  const url = new URL(request.url);
  const worldCup = label(url, "scope", "props") === "worldcup";
  const player = label(url, "player", "Player prop", 42);
  const selection = label(url, "selection", "Selection", 64);
  const event = label(url, "event", "Player props", 68);
  const odds = label(url, "odds", "-", 10);
  const stake = label(url, "stake", "-", 10);
  const date = label(url, "date", "", 24);
  const bookmaker = label(url, "bookmaker", "Bookmaker", 25);
  const resolved = resolveBookmakerLogo(bookmaker);
  const logo = resolved ? TELEGRAM_BRAND_ASSETS[resolved.key] : null;
  const hill = resolved?.key === "williamhill";

  return new ImageResponse(
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: "#091218", color: "#f4f7f5", padding: "44px 54px", fontFamily: "sans-serif", position: "relative" }}>
      <div style={{ position: "absolute", width: 9, top: 0, bottom: 0, left: 0, background: "#caff70", display: "flex" }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 28, borderBottom: "1px solid #2a383e" }}>
        <div style={{ display: "flex", fontSize: 33, fontWeight: 700, letterSpacing: -1 }}>IL MARGINE<span style={{ color: "#caff70", marginLeft: 10 }}> / </span><span style={{ marginLeft: 14, color: "#acbbb9", fontSize: 23, alignSelf: "center", letterSpacing: 2 }}>PLAYER PROPS</span></div>
        <div style={{ display: "flex", color: "#caff70", fontSize: 23 }}>{worldCup ? "WORLD CUP" : date || "PICK ALERT"}</div>
      </div>
      <div style={{ display: "flex", marginTop: 30, color: "#aabbb9", fontSize: event.length > 50 ? 27 : 31 }}>{event}</div>
      <div style={{ display: "flex", marginTop: 18, fontSize: player.length > 29 ? 48 : 62, fontWeight: 700, letterSpacing: -1.8, lineHeight: 1.08 }}>{player}</div>
      <div style={{ display: "flex", marginTop: 15, color: "#caff70", fontSize: selection.length > 42 ? 34 : 43, lineHeight: 1.14, maxWidth: 1080 }}>{selection}</div>
      <div style={{ display: "flex", marginTop: "auto", alignItems: "stretch", height: 170, background: "#142128", borderRadius: 22, overflow: "hidden" }}>
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", width: 240, paddingLeft: 32 }}><span style={{ color: "#9bafae", fontSize: 20, letterSpacing: 2 }}>ODDS</span><span style={{ fontSize: 64, fontWeight: 700, marginTop: 4 }}>{odds}</span></div>
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", width: 250, paddingLeft: 32, borderLeft: "1px solid #2a383e" }}><span style={{ color: "#9bafae", fontSize: 20, letterSpacing: 2 }}>STAKE</span><span style={{ fontSize: 56, fontWeight: 700, marginTop: 8 }}>{stake}</span></div>
        <div style={{ display: "flex", flex: 1, flexDirection: "column", alignItems: "center", justifyContent: "center", background: hill ? "#00133b" : "#030a0e", padding: "18px 28px" }}>
          <span style={{ color: "#aabbb9", fontSize: 17, letterSpacing: 2, marginBottom: 14 }}>PRICE AT</span>
          {logo ? <img src={logo} alt={resolved?.displayName || bookmaker} width={330} height={88} style={{ objectFit: "contain" }} /> : <span style={{ fontSize: 40, fontWeight: 700 }}>{resolved?.displayName || bookmaker}</span>}
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24, color: "#93a6a5", fontSize: 20 }}><span>Price recorded when published</span><span style={{ color: "#caff70" }}>ilmargine.bet</span></div>
    </div>,
    { width: 1200, height: 675, headers: { "Cache-Control": "public, max-age=86400, s-maxage=604800", "X-Card-Version": "props-v2" } },
  );
}
