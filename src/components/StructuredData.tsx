import { BASE_URL } from '@/lib/config';

export default function StructuredData() {
  
  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Il Margine",
    "url": BASE_URL,
    "description": "Football and tennis betting research tools, statistical models and independent analysis. Explore fair odds, player and manager matchups, historical returns, bookmaker margins and a public record of published selections.",
  };
  
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Il Margine",
    "url": BASE_URL,
    "logo": `${BASE_URL}/brand/20260913/logo.png`,
  };
  
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(websiteSchema),
        }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(organizationSchema),
        }}
      />
    </>
  );
}
