/** Comparison-only folding. Preserve display names, URL slugs and stored IDs. */
const latinFolds: Record<string, string> = {
  ø: "o", Ø: "O", ł: "l", Ł: "L", đ: "d", Đ: "D", ð: "d", Ð: "D",
  þ: "th", Þ: "TH", æ: "ae", Æ: "AE", œ: "oe", Œ: "OE", ß: "ss", ẞ: "SS",
  ı: "i", ħ: "h", Ħ: "H",
};

export function foldNameText(value: string | null | undefined): string {
  return (value ?? "")
    .replace(/[øØłŁđĐðÐþÞæÆœŒßẞıħĦ]/g, (char) => latinFolds[char])
    .normalize("NFKD")
    .replace(/\p{M}/gu, "");
}
