import thumbnails from "./team-logo-thumbnails.json";

// Only substitute offline assets that exist. Unknown and remote sources stay intact.
export function smallTeamLogo(src: string | null): string | null {
  if (!src) return src;
  const local = src.replace(/^https:\/\/ilmargine\.bet(?=\/)/, "");
  return (thumbnails as Record<string, string>)[local] ?? src;
}
