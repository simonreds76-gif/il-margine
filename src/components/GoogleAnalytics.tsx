import GoogleAnalyticsRouteTracker from "./GoogleAnalyticsRouteTracker";

interface Props {
  measurementId: string;
}

export default function GoogleAnalytics({ measurementId }: Props) {
  return <GoogleAnalyticsRouteTracker measurementId={measurementId} />;
}
