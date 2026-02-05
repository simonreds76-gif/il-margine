"use client";

import { useEffect } from "react";

export default function StructuredData() {
  useEffect(() => {
    const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ilmargine.bet';
    
    // WebSite schema
    const websiteScript = document.createElement("script");
    websiteScript.type = "application/ld+json";
    websiteScript.id = "website-schema";
    websiteScript.textContent = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "WebSite",
      "name": "Il Margine",
      "url": siteUrl,
      "description": "Independent betting tips and analysis across tennis, player props and football markets, with a disciplined and data-driven approach.",
    });
    
    // Organization schema
    const organizationScript = document.createElement("script");
    organizationScript.type = "application/ld+json";
    organizationScript.id = "organization-schema";
    organizationScript.textContent = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Il Margine",
      "url": siteUrl,
      "logo": `${siteUrl}/logo.png`,
    });
    
    // Remove existing scripts if they exist (for hot reload)
    const existingWebsite = document.getElementById("website-schema");
    const existingOrg = document.getElementById("organization-schema");
    if (existingWebsite) existingWebsite.remove();
    if (existingOrg) existingOrg.remove();
    
    // Add to head
    document.head.appendChild(websiteScript);
    document.head.appendChild(organizationScript);
    
    // Cleanup on unmount
    return () => {
      if (websiteScript.parentNode) websiteScript.parentNode.removeChild(websiteScript);
      if (organizationScript.parentNode) organizationScript.parentNode.removeChild(organizationScript);
    };
  }, []);
  
  return null;
}
