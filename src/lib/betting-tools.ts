import type { EditorialIconName } from "@/components/EditorialIcon";

export const BETTING_TOOL_GROUPS: Array<{
  id: string; title: string; question: string;
  tools: Array<{ href: string; title: string; description: string; action: string; icon: EditorialIconName; badge: string }>;
}> = [
  { id: "price", title: "Understand the price", question: "What do these odds really offer?", tools: [
    { href: "/calculator?tool=margin", title: "Fair odds & value", description: "Remove the margin, compare three methods and test the odds you can actually take.", action: "Check a price", icon: "markets", badge: "Calculator" },
    { href: "/calculator/football", title: "Double chance & draw no bet", description: "Turn a complete 1X2 market into fair prices, with the draw treated correctly.", action: "Price a football market", icon: "football", badge: "Calculator" },
    { href: "/bookmakers", title: "Mind the Margin", description: "Compare measured bookmaker margins within the same market and see the sample behind each figure.", action: "Compare bookmakers", icon: "compare", badge: "Market comparison" },
  ] },
  { id: "research", title: "Research the selection", question: "What does the evidence say?", tools: [
    { href: "/return-atlas", title: "Return Atlas · Tennis", description: "Explore player returns by season, surface, odds range and favourite or underdog status.", action: "Explore player records", icon: "analysis", badge: "Historical research" },
    { href: "/football-atlas", title: "Return Atlas · Football", description: "Compare club returns across five domestic leagues. Filter seasons, venue, role and prices.", action: "Explore club records", icon: "football", badge: "Historical research" },
    { href: "/fair-odds-lab", title: "Fair Odds Lab", description: "Inspect estimated goalscorer probabilities, lineup assumptions and the available price comparisons.", action: "Open the lab", icon: "method", badge: "Model research · beta" },
    { href: "/penalty-takers", title: "Penalty taker intelligence", description: "Find first choices, deputies and the dated evidence behind each club’s hierarchy.", action: "Check a hierarchy", icon: "guide", badge: "Evidence directory" },
  ] },
  { id: "stake", title: "Understand the risk", question: "What could the stake cost me?", tools: [
    { href: "/calculator?tool=kelly", title: "Kelly staking", description: "Compare stake fractions and see how an overestimated probability changes growth and drawdown.", action: "Test a stake", icon: "bankroll", badge: "Calculator" },
    { href: "/calculator?tool=returns", title: "Returns & drawdown", description: "Simulate a range of outcomes using assumptions drawn from our settled record and your chosen stake.", action: "Explore the range", icon: "analysis", badge: "Simulation" },
  ] },
];

export const BETTING_STEPS = [
  { title: "Read the odds", detail: "Convert a price into its break-even probability.", href: "/resources/odds-value-stakes#probability", icon: "markets" as const },
  { title: "Remove the margin", detail: "Compare all outcomes from the same market.", href: "/resources/odds-value-stakes#margin", icon: "compare" as const },
  { title: "Assess the value", detail: "Test the available price against an estimate.", href: "/resources/odds-value-stakes#value", icon: "method" as const },
  { title: "Choose the stake", detail: "Allow for uncertainty and potential losses.", href: "/resources/odds-value-stakes#stake", icon: "bankroll" as const },
];
