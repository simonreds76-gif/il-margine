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
        allow: '/',
        disallow: ['/admin', '/api', '/api/*'],
      },
    ],
    sitemap: `${BASE_URL}/sitemap.xml`,
  };
}
