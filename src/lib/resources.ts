/**
 * Resource articles config. Add new articles here.
 * Categories: Lab Notes | Bankroll Management | Value Betting | Advanced Concepts | Psychology | Tools
 */
export type ResourceCategory =
  | "Lab Notes"
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
  tag?: "tennis" | "props" | "goalscorer" | "method" | "tools";
  datePublished?: string;
  excerpt?: string;
  surface?: "lab-note" | "guide" | "tool";
  homepageFeature?: boolean;
}

export const RESOURCES: Resource[] = [
  {
    href: "/resources/clay-season-tennis-model-caveats",
    title: "Why our ATP model is conservative on clay",
    description:
      "A lab note on clay volatility, player fitness, calibration risk, and why the model treats clay-court betting edges more carefully than hard courts.",
    excerpt:
      "Clay creates more physical and tactical noise than most markets admit, so our model widens thresholds, watches calibration harder, and keeps marginal clay angles out of production.",
    minRead: 5,
    category: "Lab Notes",
    tag: "tennis",
    datePublished: "2026-05-13",
    surface: "lab-note",
    homepageFeature: true,
  },
  {
    href: "/resources/fair-odds-lab-explained",
    title: "What the Fair Odds Lab shows, and what it does not",
    description:
      "How to read Il Margine fair prices, reference odds, price gaps, and model flags without confusing research signals for guaranteed betting picks.",
    excerpt:
      "The Lab is a pricing surface, not a brag wall. It shows where our numbers disagree with a reference market, and it keeps the caveats visible.",
    minRead: 4,
    category: "Lab Notes",
    tag: "method",
    datePublished: "2026-05-13",
    surface: "lab-note",
    homepageFeature: true,
  },
  {
    href: "/resources/how-to-read-a-tipster-track-record",
    title: "How to read a betting track record properly",
    description:
      "A practical guide to ROI, sample size, closing-line value, drawdowns, and the warning signs that make a betting record less useful than it looks.",
    excerpt:
      "A good record is not just a big ROI number. You need timestamps, losses, sample size, CLV, and enough ugly weeks to know the history is real.",
    minRead: 5,
    category: "Lab Notes",
    tag: "method",
    datePublished: "2026-05-13",
    surface: "lab-note",
    homepageFeature: true,
  },
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
    category: "Tools",
  },
  {
    href: "/calculator",
    title: "ROI & Kelly Calculator",
    description:
      "Bankroll calculator using our verified track record. Kelly Criterion calculator for optimal stake sizing. One-tenth Kelly for props, quarter Kelly for tennis.",
    minRead: 2,
    category: "Tools",
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
  "Lab Notes",
  "Bankroll Management",
  "Value Betting",
  "Advanced Concepts",
  "Psychology",
  "Tools",
];

export const CURRENTLY_WATCHING =
  "ATP clay remains the awkward bit of the board: fitness, surface tolerance, and late market moves matter more here, so marginal tennis edges stay in research until the calibration earns trust.";

export const HOMEPAGE_LAB_NOTES = RESOURCES.filter(
  (resource) => resource.surface === "lab-note" && resource.homepageFeature,
)
  .sort((a, b) => (b.datePublished ?? "").localeCompare(a.datePublished ?? ""))
  .slice(0, 3);
