"use client";

import { useSyncExternalStore } from "react";

const emptySubscribe = () => () => {};

export function ClientOnly({
  children,
  fallback = null,
}: {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const mounted = useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  );

  return mounted ? <>{children}</> : <>{fallback}</>;
}
