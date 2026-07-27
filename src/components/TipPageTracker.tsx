"use client";

import { useEffect } from "react";
import { track } from "@/lib/analytics";

type TipPageTrackerProps = {
  betId: number;
  market: string;
  category: string;
  status: string;
};

export default function TipPageTracker({ betId, market, category, status }: TipPageTrackerProps) {
  useEffect(() => {
    track("pick_page_view", {
      bet_id: betId,
      market,
      category,
      status,
    });
  }, [betId, market, category, status]);

  return null;
}
