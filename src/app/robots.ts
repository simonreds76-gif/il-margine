import { MetadataRoute } from 'next';
import { BASE_URL } from '@/lib/config';

export default function robots(): MetadataRoute.Robots {
  return {
    host: BASE_URL,
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/admin', '/api', '/api/*'],
      },
      {
        userAgent: ['OAI-SearchBot', 'ChatGPT-User', 'PerplexityBot'],
        allow: '/',
        disallow: ['/admin', '/api', '/api/*'],
      },
      {
        userAgent: 'GPTBot',
        allow: '/',
        disallow: ['/admin', '/api', '/api/*'],
      },
    ],
    sitemap: `${BASE_URL}/sitemap.xml`,
  };
}
