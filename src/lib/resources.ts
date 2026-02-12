/**
 * Resource articles config. Add new articles here.
 * Categories: Bankroll Management | Value Betting | Strategy | Advanced Concepts | Psychology
 */
export type ResourceCategory =
  | "Bankroll Management"
  | "Value Betting"
  | "Advanced Concepts"
  | "Psychology";

export interface Resource {
  href: string;
  title: string;
  description: string;
  minRead: number;
  category: ResourceCategory;
}

export const RESOURCES: Resource[] = [
  {
    href: "/resources/kelly-criterion-sports-betting",
    title: "The Kelly Criterion for Sports Betting",
    description:
      "Master the mathematics of optimal bet sizing. Learn how professional bettors use the Kelly Criterion to maximize bankroll growth while controlling risk. Covers fractional Kelly, player props, tennis, and practical implementation.",
    minRead: 13,
    category: "Bankroll Management",
  },
];

export const RESOURCE_CATEGORIES: ResourceCategory[] = [
  "Bankroll Management",
  "Value Betting",
  "Advanced Concepts",
  "Psychology",
];
