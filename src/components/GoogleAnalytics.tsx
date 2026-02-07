import { GA_MEASUREMENT_ID } from "@/lib/config";
import GoogleAnalyticsRouteTracker from "./GoogleAnalyticsRouteTracker";

export default function GoogleAnalytics() {
  if (!GA_MEASUREMENT_ID) return null;
  return <GoogleAnalyticsRouteTracker measurementId={GA_MEASUREMENT_ID} />;
}
