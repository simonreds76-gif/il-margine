import "server-only";
import { createHash } from "node:crypto";
import tennisPortraits from "@/data/tip-tennis-portraits.json";
import penaltyPortraits from "../../data/goalscorer/penalty-player-portraits.json";
import labPortraits from "../../data/goalscorer/lab-player-portraits.json";
import { foldNameText } from "./player-name-matching";
import { resolveTeamLogoPath } from "./team-logos";
import type { TipPortrait } from "./tip-artwork-types";

type PickIdentity = { id?: number; market: string; category: string; event: string; player: string | null; match_date?: string | null };
const key = (name: string) => foldNameText(name).toLowerCase().replace(/[^a-z0-9]/g, "");
const words = (name: string) => foldNameText(name).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const leagueKeys: Record<string, string> = { pl: "epl", seriea: "serie-a", laliga: "la-liga", bundesliga: "bundesliga", ligue1: "ligue-1" };
const clubAliases: Record<string, string> = { psg: "parissaintgermain", acmilan: "milan" };
const clubKey = (club: string) => clubAliases[key(club)] ?? key(club);
// Verified editorial surname shorthand in current ATP picks. Full names still
// resolve exactly, and ambiguous names outside this context remain unresolved.
const currentAtpPortraitAliases: Record<string, string> = {
  zverev: "Alexander Zverev",
  berrettini: "Matteo Berrettini",
};

// The URL must change with the saved identity, even when the bet ID stays the
// same. This also resets the portrait component's failed-image state on edit.
function portraitLookupUrl(pick: PickIdentity): string | null {
  if (!Number.isSafeInteger(pick.id) || Number(pick.id) <= 0) return null;
  const revision = createHash("sha256").update(JSON.stringify([
    pick.market, pick.category, pick.event, pick.player,
  ])).digest("hex").slice(0, 12);
  return `/api/tip-portrait/${pick.id}?v=${revision}`;
}

// Verified FotMob identities for published surname-only selections. Club context
// prevents assigning a namesake or carrying an old club crest into another fixture.
const footballPlayers = [
  // FotMob Slavia squad 7787, verified 22 October 2026. Sabah has no squad feed.
  { name: "David Zima", alias: "Zima", club: "Slavia Prague", id: "1085401" },
  // Verified Malaga appearances and photo; absent from the provider's senior squad list.
  { name: "Ángel Recio", alias: "Recio", club: "Malaga", id: "1260010" },
  // Verified 11 October 2026 against FotMob player profiles 290410 and 1203512.
  { name: "Michael Keane", alias: "Keane", club: "Everton", id: "290410" },
  { name: "Tim Iroegbunam", alias: "Iroegbunam", club: "Hull", id: "1203512" },
  { name: "Marten de Roon", alias: "De Roon", club: "Roma", id: "198559" },
  { name: "Mario Hermoso", alias: "Hermoso", club: "Roma", id: "671203" },
  { name: "Mike Maignan", alias: "Maignan", club: "Milan", id: "466439" },
  { name: "Jeffrey De Lange", alias: "De Lange", club: "Marseille", id: "687868" },
  { name: "Loris Karius", alias: "Karius", club: "Schalke 04", id: "287894" },
  { name: "Lukasz Skorupski", alias: "Skorupski", club: "Bologna", id: "178732" },
  { name: "Noel Törnqvist", alias: "Tornqvist", club: "Monza", id: "1122424" },
];

function participants(event: string): string[] {
  const parts = event.split(/\s+(?:vs?\.?|versus)\s+|\s+[–—-]\s+/i).map((part) => part.trim());
  return parts.length === 2 && parts.every(Boolean) ? parts : [];
}

function tennisPortrait(name: string): TipPortrait {
  const query = words(name);
  const exact = tennisPortraits.filter((row) => words(row.name) === query);
  const candidates = exact.length ? exact : tennisPortraits.filter((row) => words(row.name).endsWith(` ${query}`));
  // Never choose between players sharing a surname without a verified alias.
  const row = candidates.length === 1 ? candidates[0] : null;
  return { name: row?.name ?? name, src: row?.src ?? null, kind: "player" };
}

export function getTipArtwork(pick: PickIdentity): TipPortrait[] {
  const sides = participants(pick.event);
  if (pick.market === "tennis") {
    const useCurrentAtpShorthand = pick.category === "atp" && (!pick.match_date || pick.match_date >= "2024-01-01");
    return sides.map((name) => tennisPortrait(useCurrentAtpShorthand ? currentAtpPortraitAliases[key(name)] ?? name : name));
  }
  const name = pick.player?.trim();
  const clubPortraits = sides.map((club): TipPortrait => ({ name: club, src: resolveTeamLogoPath(club, pick.category), kind: "club" }));
  if (!name || sides.some((club) => key(club) === key(name))) return clubPortraits;

  const known = footballPlayers.find((row) => [row.name, row.alias].some((alias) => key(alias) === key(name))
    && sides.some((club) => key(club) === key(row.club) || (resolveTeamLogoPath(club, pick.category) != null && resolveTeamLogoPath(club, pick.category) === resolveTeamLogoPath(row.club, pick.category))));
  if (known) return [{ name: known.name, src: `https://images.fotmob.com/image_resources/playerimages/${known.id}.png`, kind: "player", fallbackSrc: resolveTeamLogoPath(known.club, pick.category) }];

  const league = leagueKeys[pick.category];
  const portraits: Record<string, string> = penaltyPortraits;
  const lab: Record<string, string> = labPortraits;
  // Club-scoped identities take precedence (e.g. the two Vitinhas).
  const scoped = sides.map((club) => ({ club, id: portraits[`${league}|${clubKey(club)}|${key(name)}`] })).filter((row) => row.id);
  const scopedIds = new Set(scoped.map((row) => row.id));
  const id = scopedIds.size === 1 ? scoped[0].id : scopedIds.size > 1 ? null : lab[`${league}|${key(name)}`] ?? portraits[key(name)];
  return [{ name, src: id ? `https://images.fotmob.com/image_resources/playerimages/${id}.png` : portraitLookupUrl(pick), kind: "player", fallbackSrc: scopedIds.size === 1 ? resolveTeamLogoPath(scoped[0].club, pick.category) : null }];
}
