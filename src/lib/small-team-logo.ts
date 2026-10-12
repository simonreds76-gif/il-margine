import thumbnails from "./team-logo-thumbnails.json";

// Only substitute offline assets that exist. Unknown and remote sources stay intact.
export function smallTeamLogo(src: string | null, size: 64 | 144 = 144): string | null {
  if (!src) return src;
  const local = src.replace(/^https:\/\/ilmargine\.bet(?=\/)/, "");
  const thumbnail = (thumbnails as Record<string, string>)[local];
  return thumbnail ? (size === 64 ? thumbnail.replace(".webp", "-64.webp") : thumbnail) : src;
}
