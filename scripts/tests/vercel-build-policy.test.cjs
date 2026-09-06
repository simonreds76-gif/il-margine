/* eslint-disable @typescript-eslint/no-require-imports */
const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vercel-build-policy-'));
const script = path.resolve(__dirname, '../vercel-should-build.cjs');
const git = (...args) => execFileSync('git', args, {cwd:root, encoding:'utf8', stdio:['ignore','pipe','pipe']}).trim();
git('init');
git('config', 'user.name', 'Build policy test');
git('config', 'user.email', 'test@example.invalid');
git('commit', '--allow-empty', '-m', 'baseline');
after(() => fs.rmSync(root, {recursive:true, force:true}));
function commit(files, message='chore: capture data') {
  const previous = git('rev-parse', 'HEAD');
  for (const file of files) {
    const full = path.join(root, file);
    fs.mkdirSync(path.dirname(full), {recursive:true});
    fs.appendFileSync(full, '\nupdate');
  }
  git('add', '.'); git('commit', '-m', message);
  return {previous, current:git('rev-parse', 'HEAD'), message};
}
function decision(c, overrides={}) {
  return spawnSync(process.execPath, [script], {cwd:root, encoding:'utf8', env:{...process.env,
    VERCEL_GIT_PREVIOUS_SHA:c.previous, VERCEL_GIT_COMMIT_SHA:c.current,
    VERCEL_GIT_COMMIT_MESSAGE:c.message, VERCEL_GIT_COMMIT_REF:'',
    VERCEL_GIT_COMMIT_REF_NAME:'', ...overrides}});
}
test('scheduled captures skip; published penalty data and mixed changes build', () => {
  const captures = commit([
    'data/tennis-props/inbox/bet365-lines-2026-09-06.csv',
    'data/team-shots/match-shots-odds-history.csv',
    'data/team-shots/team-shots-scrape-last-run.json',
    'data/goalscorer/epl-penalty-duty-live-review.json',
    'data/goalscorer/penalty-baseline-evidence.json',
    'data/assist-value/research/assist-value-gates.json',
    'public/fair-odds-lab/signals.json'
  ]);
  assert.equal(decision(captures).status, 0);
  assert.equal(decision(captures, {VERCEL_GIT_PREVIOUS_SHA:''}).status, 0);
  assert.equal(decision(captures, {VERCEL_GIT_COMMIT_MESSAGE:'chore: capture [force build]'}).status, 1);
  const page = commit(['data/goalscorer/ligue-1-penalty-takers.json'], 'fix: update hierarchy');
  assert.equal(decision(page).status, 1);
  const later = commit(['data/tennis-props/inbox/latest.csv']);
  assert.equal(decision(later, {VERCEL_GIT_PREVIOUS_SHA:page.previous}).status, 1, 'full push range must include public data changes');
  const mixed = commit(['src/app/page.tsx', 'data/tennis-props/inbox/latest.csv']);
  assert.equal(decision(mixed).status, 1);
  assert.equal(decision(commit(['config/tennis-props-rate-trend-prospective-v1.json'])).status, 1);
  assert.equal(decision(commit(['data/goalscorer/club-penalty-season.json'])).status, 1);
  assert.equal(decision(commit(['data/new-unknown-file.json'])).status, 1);
});
