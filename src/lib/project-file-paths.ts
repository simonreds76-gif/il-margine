import path from "node:path";

const ALLOWED_PREFIXES = [
  "data/",
  "public/",
  "scripts/",
];

export function tryGetKnownProjectFilePath(relativePath: string): string | null {
  const normalized = relativePath.replace(/\\/g, "/").replace(/^\/+/, "");
  if (
    !normalized ||
    normalized.includes("..") ||
    path.isAbsolute(normalized) ||
    !ALLOWED_PREFIXES.some((prefix) => normalized.startsWith(prefix))
  ) {
    return null;
  }
  return path.join(process.cwd(), normalized);
}
