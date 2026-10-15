import { MetadataRoute } from 'next';
import { BASE_URL } from '@/lib/config';

export default function robots(): MetadataRoute.Robots {
  return {
    host: BASE_URL,
    rules: [
      {
        userAgent: '*',
        // Public image redirects must be crawlable so their X-Robots-Tag can be read.
        allow: ['/', '/api/tip-portrait/'],
        disallow: ['/admin', '/api', '/api/*'],
      },
      {
        userAgent: [
          'OAI-SearchBot',
          'ChatGPT-User',
          'GPTBot',
          'PerplexityBot',
          'Perplexity-User',
          'ClaudeBot',
          'Claude-SearchBot',
          'Claude-User',
          'Googlebot',
          'Google-Extended',
          'bingbot',
        ],
        allow: ['/', '/api/tip-portrait/'],
        disallow: ['/admin', '/api', '/api/*'],
      },
    ],
    sitemap: `${BASE_URL}/sitemap.xml`,
  };
}
