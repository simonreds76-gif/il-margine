import { RESOURCE_GUIDES, GUIDE_REVIEW_DATE } from "./resource-guides";
export type ResourceCategory = "Lab Notes" | "Bankroll Management" | "Value Betting" | "Advanced Concepts" | "Psychology" | "Tools";
export interface Resource {
  href: string; title: string; description: string; minRead: number; category: ResourceCategory;
  tag?: "tennis" | "props" | "goalscorer" | "method" | "tools";
  datePublished?: string; dateModified?: string; excerpt?: string;
  surface?: "lab-note" | "guide" | "tool"; homepageFeature?: boolean; featured?: boolean;
}
const order = ["how-to-read-a-tipster-track-record", "closing-line-value", "kelly-criterion-sports-betting", "fair-odds-lab-explained", "clay-season-tennis-model-caveats"];
export const RESOURCES: Resource[] = [
  ...order.map((slug): Resource => {
    const guide = RESOURCE_GUIDES[slug];
    return { href: `/resources/${slug}`, title: guide.title, description: guide.description, excerpt: guide.description, minRead: guide.minutes,
      category: slug.includes("kelly") ? "Bankroll Management" : slug.includes("clay") || slug.includes("track-record") ? "Lab Notes" : "Value Betting",
      tag: slug.includes("clay") ? "tennis" : "method", datePublished: guide.published, dateModified: GUIDE_REVIEW_DATE,
      surface: "guide", homepageFeature: ["how-to-read-a-tipster-track-record", "fair-odds-lab-explained", "clay-season-tennis-model-caveats"].includes(slug), featured: order.indexOf(slug) < 3 };
  }),
  { href: "/calculator", title: "Four betting calculators", description: "Try returns simulations, Kelly staking, margin removal and closing-line value with your own numbers.", minRead: 2, category: "Tools", surface: "tool", tag: "tools" },
  { href: "/return-atlas", title: "Return Atlas", description: "Explore ATP player betting history by season, surface and favourite or underdog status. Compare betting on the player with backing the opponent.", minRead: 2, category: "Tools", surface: "tool", tag: "tennis" },
  { href: "/resources/roger", title: "Ask Roger about tennis", description: "Make a tennis statistics question specific: player, opponent, surface and period. See examples and learn how to check the answer.", minRead: 3, category: "Tools", surface: "tool", tag: "tennis", dateModified: GUIDE_REVIEW_DATE },
];
export const RESOURCE_CATEGORIES = Array.from(new Set(RESOURCES.map(r => r.category)));
export const CURRENTLY_WATCHING = "Surface, opponent quality and the price all matter. Use the tennis guides to turn a broad form claim into a question you can check.";
export const HOMEPAGE_LAB_NOTES = RESOURCES.filter(r => r.homepageFeature).slice(0,3);
