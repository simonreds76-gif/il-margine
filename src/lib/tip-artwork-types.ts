export type TipPortrait = {
  name: string;
  src: string | null;
  kind: "player" | "club" | "country";
  fallbackSrc?: string | null;
};
