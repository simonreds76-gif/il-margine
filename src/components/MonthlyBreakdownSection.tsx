"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import MonthlyBreakdown, { type MonthlyBreakdownScope } from "./MonthlyBreakdown";

const SETTING_BY_SCOPE: Record<MonthlyBreakdownScope, string> = {
  combined: "monthly_breakdown_combined_public",
  props: "monthly_breakdown_props_public",
  tennis: "monthly_breakdown_tennis_public",
};

interface MonthlyBreakdownSectionProps {
  scope: MonthlyBreakdownScope;
}

export default function MonthlyBreakdownSection({ scope }: MonthlyBreakdownSectionProps) {
  const [show, setShow] = useState<boolean | null>(null);

  useEffect(() => {
    async function fetch_() {
      const { data } = await supabase
        .from("site_settings")
        .select("value")
        .eq("key", SETTING_BY_SCOPE[scope])
        .single();
      setShow(data?.value === true);
    }
    fetch_();
  }, [scope]);

  if (show !== true) return null;

  return (
    <section className="py-12 md:py-16 border-b border-slate-800/50 bg-slate-900/20">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <MonthlyBreakdown scope={scope} />
      </div>
    </section>
  );
}
