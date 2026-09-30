import "server-only";
import { cache } from "react";

// One timestamp for freshness checks during this server request.
export const monitorRequestTime = cache(async (): Promise<number> => Date.now());
