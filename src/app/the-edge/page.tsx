"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function TheEdgeRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/#the-edge");
  }, [router]);
  return (
    <div className="min-h-screen bg-[#0f1117] flex items-center justify-center text-slate-400">
      Redirecting…
    </div>
  );
}
