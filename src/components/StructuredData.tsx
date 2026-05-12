import { BASE_URL } from '@/lib/config';

export default function StructuredData() {
  
  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Il Margine",
    "url": BASE_URL,
    "description": "Independent betting tips and analysis across tennis, player props and football markets, with a disciplined and data-driven approach.",
    "potentialAction": {
      "@type": "SearchAction",
      "target": `${BASE_URL}/?q={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  };
  
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Il Margine",
    "url": BASE_URL,
    "logo": `${BASE_URL}/logo.png`,
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
