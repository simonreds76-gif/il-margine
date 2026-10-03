/** Correct known club spelling errors in football labels, never player names. */
export function correctFootballClubNames(value: string): string {
  return value.replace(/\bvillareal\b/gi, "Villarreal");
}
