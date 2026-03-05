/**
 * Resource articles config. Add new articles here.
 * Categories: Bankroll Management | Value Betting | Strategy | Advanced Concepts | Psychology
 */
export type ResourceCategory =
  | "Bankroll Management"
  | "Value Betting"
  | "Advanced Concepts"
  | "Psychology"
  | "Tools";

export interface Resource {
  href: string;
  title: string;
  description: string;
  minRead: number;
  category: ResourceCategory;
}

export const RESOURCES: Resource[] = [
  {
    href: "/resources/closing-line-value",
    title: "Closing Line Value: The Only Metric That Matters",
    description:
      "Learn why CLV is the most reliable predictor of betting success. Understand how to calculate, track, and consistently beat the closing line across props and tennis markets.",
    minRead: 11,
    category: "Value Betting",
  },
  {
    href: "/resources/kelly-criterion-sports-betting",
    title: "The Kelly Criterion for Sports Betting",
    description:
      "Master the mathematics of optimal bet sizing. Learn how professional bettors use the Kelly Criterion to maximize bankroll growth while controlling risk. Covers fractional Kelly, player props, tennis, and practical implementation.",
    minRead: 13,
    category: "Bankroll Management",
  },
  {
    href: "/resources/roger",
    title: "Meet Roger",
    description:
      "Roger is our tennis stats chatbot. Ask about ATP head to head, tournament records, serve stats, and more. Use tennis data to enhance your betting.",
    minRead: 2,
    category: "Tools",
  },
];

export const RESOURCE_CATEGORIES: ResourceCategory[] = [
  "Bankroll Management",
  "Value Betting",
  "Advanced Concepts",
  "Psychology",
  "Tools",
];
