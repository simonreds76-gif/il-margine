import "server-only";
import { ImageResponse } from "next/og";
import sharp from "sharp";
import { BASE_URL } from "./config";
import { SITE_BRAND_IMAGE } from "./site-brand-image";
import { SHARE_FONTS } from "./share-fonts";
import { getTipArtwork } from "./tip-artwork";
import { formatOdds, formatStake } from "./format";
import { shareDate, shareSelection, type ShareTip } from "./tip-share";

// Optional, identity-checked artwork must never prevent a selection being shared.
async function imageData(src: string | null): Promise<string | null> {
  if (!src) return null;
  try {
    const url = new URL(src, BASE_URL);
    if (![new URL(BASE_URL).host, "images.fotmob.com", "a.espncdn.com", "images.wimbledon.com", "thumb.wikimedia.org"].includes(url.host)) return null;
    const response = await fetch(url, { signal: AbortSignal.timeout(3500), next: { revalidate: 604800 } });
    if (!response.ok || !response.headers.get("content-type")?.startsWith("image/")) return null;
    const bytes = Buffer.from(await response.arrayBuffer());
    if (bytes.length > 2_000_000) return null;
    const png = await sharp(bytes, { limitInputPixels: 16_000_000 }).resize(160, 160, { fit: "inside", withoutEnlargement: true }).png().toBuffer();
    return `data:image/png;base64,${png.toString("base64")}`;
  } catch { return null; }
}

export async function renderTipShareImage(bets: ShareTip[]) {
  const first = bets[0];
  if (!first) return new Response("Tip not found", { status: 404, headers: { "Cache-Control": "no-store" } });
  const single = bets.length === 1;
  const clubs = first.market === "props" ? getTipArtwork({ ...first, player: null }) : [];
  const artwork = (single ? [...getTipArtwork(first), ...clubs] : first.market === "props" ? clubs : getTipArtwork(first)).slice(0, 4);
  const photos = await Promise.all(artwork.map(async p => ({ ...p, data: await imageData(p.src) ?? await imageData(p.fallbackSrc ?? null) })));
  const portraits = photos.filter(p => p.data);
  const eventSize = first.event.length > 62 ? 40 : first.event.length > 42 ? 48 : 62;
  return new ImageResponse(
    <div style={{ display: "flex", width: "100%", height: "100%", background: "linear-gradient(105deg,#080f12 48%,#14342b 100%)", color: "#f2f1e8", fontFamily: "Share", borderLeft: "8px solid #57d196", padding: "38px 48px" }}>
      <div style={{ display: "flex", flexDirection: "column", width: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 25, borderBottom: "1px solid #293e37" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={SITE_BRAND_IMAGE} width={245} height={59} alt="Il Margine" />
          <div style={{ display: "flex", alignItems: "center", gap: 18, color: "#b5c5bc", fontSize: 18, letterSpacing: 4 }}>
            {!single ? portraits.map((p, i) =>
              // eslint-disable-next-line @next/next/no-img-element
              <img key={`${p.name}-${i}`} src={p.data!} width={48} height={48} alt={p.name} style={{ objectFit: "contain" }} />
            ) : null}
            {first.market === "tennis" ? "TENNIS" : "FOOTBALL"}
          </div>
        </div>
        <div style={{ display: "flex", flex: 1, paddingTop: 28, paddingBottom: 24 }}>
          <div style={{ display: "flex", flexDirection: "column", width: single ? 744 : "100%", paddingRight: single ? 36 : 0 }}>
            <div style={{ display: "flex", color: "#57d196", letterSpacing: 4, fontSize: 19, fontWeight: 700 }}>{single ? first.market === "tennis" ? "MATCH SELECTION" : "PLAYER PROP" : `${bets.length} PUBLISHED SELECTIONS`}</div>
            <div style={{ display: "flex", fontSize: single ? eventSize : Math.min(eventSize, 48), lineHeight: 1.08, fontWeight: 700, marginTop: 20, maxHeight: single ? 145 : 105, overflow: "hidden", wordBreak: "break-word" }}>{first.event}</div>
            {single ? <div style={{ display: "flex", fontSize: shareSelection(first).length > 65 ? 24 : 30, lineHeight: 1.25, marginTop: 26, maxHeight: 76, overflow: "hidden" }}>{shareSelection(first)}</div> :
              <div style={{ display: "flex", flexDirection: "column", marginTop: 22, gap: 12 }}>
                {bets.slice(0, 3).map(bet => <div key={bet.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 9, borderBottom: "1px solid #293e37", fontSize: 24 }}>
                  <div style={{ display: "flex", width: 760, maxHeight: 56, overflow: "hidden" }}>{shareSelection(bet)}</div>
                  <div style={{ display: "flex", color: "#57d196", fontSize: 30, fontWeight: 700 }}>{formatOdds(bet.odds)}</div>
                  <div style={{ display: "flex", color: "#b5c5bc", width: 90, justifyContent: "flex-end" }}>{formatStake(bet.stake)}u</div>
                </div>)}
              </div>}
            {single ? <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: "auto", paddingTop: 20 }}>
              {portraits.map((p, i) => <div key={`${p.name}-${i}`} style={{ display: "flex", width: first.market === "tennis" ? 185 : 58, height: 58, borderRadius: 10, background: "#163f30", border: "1px solid #37785c", overflow: "hidden", alignItems: "center", justifyContent: "center", gap: 8 }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.data!} width={52} height={52} alt={p.name} style={{ objectFit: "contain" }} />
                {first.market === "tennis" ? <div style={{ display: "flex", width: 113, fontSize: 14, color: "#d9e9df" }}>{p.name}</div> : null}
              </div>)}
              <div style={{ display: "flex", background: "#163f30", color: "#9ee4c2", padding: "10px 18px", borderRadius: 25, fontSize: 16 }}>PUBLISHED SELECTION</div>
            </div> : null}
          </div>
          {single ? <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", flex: 1, paddingLeft: 42, borderLeft: "1px solid #294b3e", marginTop: 32, marginBottom: 22 }}>
            <div style={{ display: "flex", color: "#adc3b7", fontSize: 17, letterSpacing: 2 }}>RECORDED ODDS</div>
            <div style={{ display: "flex", color: "#57d196", fontSize: formatOdds(first.odds).length > 5 ? 68 : 94, fontWeight: 700, marginTop: 8 }}>{formatOdds(first.odds)}</div>
            <div style={{ display: "flex", fontSize: 24, marginTop: 14 }}>STAKE {formatStake(first.stake)}u</div>
            <div style={{ display: "flex", color: "#adc3b7", fontSize: 19, marginTop: 20 }}>{shareDate(first.match_date)}</div>
          </div> : null}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid #293e37", paddingTop: 25, alignItems: "center" }}>
          <div style={{ display: "flex", fontSize: 21, fontWeight: 700 }}>ilmargine.bet</div>
          <div style={{ display: "flex", color: "#a1b7aa", fontSize: 16, letterSpacing: single ? 3 : 0 }}>{single ? "MIND THE MARGIN" : `${shareDate(first.match_date)} · Prices as published${bets.length > 3 ? ` · +${bets.length - 3} more on the match card` : ""}`}</div>
        </div>
      </div>
    </div>,
    { width: 1200, height: 630, fonts: SHARE_FONTS, headers: { "Cache-Control": "public, max-age=0, s-maxage=604800, must-revalidate" } },
  );
}
