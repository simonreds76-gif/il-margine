import CalculatorClient from "./CalculatorClient";
import { fetchRecordMarketStats } from "@/lib/public-record";
import { summarizeCalculatorRecord } from "@/lib/calculator/record";

// Settlements invalidate this route. Avoid rendering simulations on every request.
export const revalidate = 86400;

export default async function CalculatorPage() {
  const stats = await fetchRecordMarketStats();
  return <CalculatorClient initialRecord={summarizeCalculatorRecord(stats)} />;
}
