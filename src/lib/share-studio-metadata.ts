import type { Metadata } from "next";
import previews from "@/data/share-studio-metadata.json";

export function studioMetadata(id: keyof typeof previews): Pick<Metadata, "openGraph" | "twitter"> {
  return previews[id] as Pick<Metadata, "openGraph" | "twitter">;
}
