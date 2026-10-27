const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = path.resolve(__dirname, '../..');
const source = require('../../src/data/penalty-news.json');
function load(file, imports = {}) {
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  vm.runInNewContext(code, { module, exports: module.exports, Request, Response, URL, Intl, Date, console, require: name => Object.hasOwn(imports, name) ? imports[name] : require(name) });
  return module.exports;
}
const helpers = load('src/lib/penalty-news.ts');
const { penaltyNews } = load('src/lib/penalty-news-data.ts', { 'server-only': {}, '@/data/penalty-news.json': source, './penalty-news': helpers });
const Link = ({ children, prefetch, ...props }) => React.createElement('a', props, children);
const Image = ({ unoptimized, ...props }) => React.createElement('img', props);
const shared = { 'next/link': Link, 'next/image': Image, '@/lib/penalty-news': helpers, '@/lib/penalty-news-data': { penaltyNews }, './PenaltyNews.module.css': {}, '@/components/PenaltyNews.module.css': {}, '@/components/ToolEmblem': () => null, '@/components/Footer': () => null, '@/components/PageHeading': () => null };
const feed = load('src/components/PenaltyNewsFeed.tsx', shared);

test('presentation preserves all source records, dates and incident evidence', () => {
  assert.equal(penaltyNews.articles.length, source.articles.length);
  for (const a of penaltyNews.articles) {
    const original = source.articles.find(r => r.id === a.id);
    const { title, sourceUrl, sourceHash, incident, ...rest } = original;
    const { title: shown, ...actual } = a;
    assert.equal(JSON.stringify(actual), JSON.stringify(rest));
    assert.equal(a.title, helpers.distinctNewsTitle(original, source.articles));
  }
});

test('repeated Fullkrug penalties have distinct verified-minute headlines without new URLs', () => {
  const reports = penaltyNews.articles.filter(a => a.matchId === '5881202' && a.player.includes('llkrug'));
  assert.equal(reports.length, 2);
  assert.equal(new Set(reports.map(a => a.title)).size, 2);
  for (const a of reports) assert.ok(a.title.includes(`${a.minute}′`));
  const extra = { ...source.articles[0], id: 'test-second', eventId: '9999999999', minute: '90+3' };
  const future = [...source.articles, extra];
  assert.ok(helpers.distinctNewsTitle(extra, future).includes('90+3′'));
});

test('all reports are server rendered exactly once across archive pages with real navigation', () => {
  const seen = new Map();
  const pages = Math.ceil(penaltyNews.articles.length / helpers.NEWS_PAGE_SIZE);
  for (let page = 1; page <= pages; page++) {
    const html = renderToStaticMarkup(React.createElement(feed.default, { articles: penaltyNews.articles, page }));
    for (const a of penaltyNews.articles) if (html.includes(`href="/penalty-news/${a.slug}"`)) seen.set(a.id, (seen.get(a.id) || 0) + 1);
    assert.ok(html.includes(`aria-current="page"`));
    if (page < pages) assert.ok(html.includes(`href="${helpers.newsPagePath(page + 1)}#reports"`));
  }
  assert.equal(seen.size, penaltyNews.articles.length);
  assert.ok([...seen.values()].every(n => n === 1));
});

test('club block matches historical club URL and omits clubs with no reports', () => {
  const ClubReports = load('src/components/ClubPenaltyReports.tsx', shared).default;
  const html = renderToStaticMarkup(React.createElement(ClubReports, { clubUrl: '/penalty-takers/la-liga/rayo-vallecano', club: 'Rayo Vallecano' }));
  const ciss = penaltyNews.articles.find(a => a.club === 'Rayo Vallecano');
  assert.ok(ciss && html.includes(ciss.slug));
  assert.ok(!html.includes(penaltyNews.articles.find(a => a.club === 'Elche').slug));
  assert.equal(renderToStaticMarkup(React.createElement(ClubReports, { clubUrl: '/not-a-club', club: 'Missing' })), '');
});

test('archive metadata is self-canonical, page 1 redirects and invalid pages fail', async () => {
  const route = load('src/app/penalty-news/page/[pageNumber]/page.tsx', { ...shared, '@/components/PenaltyNewsFeed': feed.default, 'next/navigation': { notFound: () => { throw Error('404'); }, permanentRedirect: url => { throw Error(`308 ${url}`); } } });
  const params = pageNumber => ({ params: Promise.resolve({ pageNumber }) });
  assert.equal((await route.generateMetadata(params('2'))).alternates.canonical, 'https://ilmargine.bet/penalty-news/page/2');
  await assert.rejects(() => route.default(params('1')), /308 \/penalty-news/);
  for (const n of ['0', '999', '-1', '02', '1.5']) await assert.rejects(() => route.default(params(n)), /404/);
});

test('article metadata uses the same distinct headline and the matching share image', async () => {
  const route = load('src/app/penalty-news/[slug]/page.tsx', { ...shared, '@/components/PenaltyNewsFeed': feed, 'next/navigation': { notFound: () => { throw Error('404'); } } });
  for (const a of penaltyNews.articles) {
    const meta = await route.generateMetadata({ params: Promise.resolve({ slug: a.slug }) });
    assert.equal(meta.openGraph.title, a.title);
    assert.equal(meta.openGraph.images[0].url, helpers.newsImageUrl(a.slug));
    assert.equal(meta.openGraph.publishedTime, a.publishedAt);
    assert.equal(meta.alternates.canonical, `https://ilmargine.bet/penalty-news/${a.slug}`);
  }
});
