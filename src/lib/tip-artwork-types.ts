export type TipPortrait = {
  name: string;
  src: string | null;
  kind: "player" | "club";
  fallbackSrc?: string | null;
};
