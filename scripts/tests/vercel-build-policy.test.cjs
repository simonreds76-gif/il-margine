/* eslint-disable @typescript-eslint/no-require-imports */
const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vercel-build-policy-'));
const script = path.resolve(__dirname, '../vercel-should-build.cjs');
const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
git('init');
git('config', 'user.name', 'Build policy test');
git('config', 'user.email', 'test@example.invalid');
git('commit', '--allow-empty', '-m', 'baseline');
const baseline = git('rev-parse', 'HEAD');
after(() => {
  // Only remove this test's newly created directory inside the OS temp folder.
  assert.equal(path.dirname(root), fs.realpathSync(os.tmpdir()));
  assert.ok(path.basename(root).startsWith('vercel-build-policy-'));
  fs.rmSync(root, { recursive: true, force: true });
});
function commit(files, message = 'fix: model maintenance') {
  const previous = git('rev-parse', 'HEAD');
  for (const file of files) {
    const full = path.join(root, file);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.appendFileSync(full, '\nupdate');
  }
  git('add', '.');
  git('commit', '-m', message);
  return { previous, current: git('rev-parse', 'HEAD'), message };
}
function decision(c, overrides = {}) {
  return spawnSync(process.execPath, [script], { cwd: root, encoding: 'utf8', env: {
    ...process.env, VERCEL: '', VERCEL_GIT_PREVIOUS_SHA: c.previous,
    VERCEL_GIT_COMMIT_SHA: c.current, VERCEL_GIT_COMMIT_MESSAGE: c.message,
    VERCEL_GIT_COMMIT_REF: '', VERCEL_GIT_COMMIT_REF_NAME: '', ...overrides,
  } });
}
function expect(c, expected, overrides) {
  const result = decision(c, overrides);
  assert.equal(result.status, expected, result.stdout + result.stderr);
}

test('offline GK/shot work, Python unit tests and review metadata skip', () => {
  expect(commit(['scripts/goalkeeper-saves-shadow.py', 'scripts/goalkeeper_forecast_evidence.py',
    'scripts/team_shots_probability.py', 'scripts/team-shots-fit-calibration.py',
    'scripts/tests/test_goalkeeper_forecast_evidence.py', 'config/model-review-watchlist.json']), 0);
});
test('existing live captures still skip', () => {
  expect(commit(['data/tennis-props/inbox/latest.csv', 'data/team-shots/match-shots-odds-history.csv',
    'data/goalscorer/epl-penalty-duty-live-review.json', 'data/goalscorer/penalty-baseline-evidence.json',
    'data/assist-value/research/gates.json', 'public/fair-odds-lab/signals.json']), 0);
});
test('website inputs, published data, build scripts and unknown files build', () => {
  for (const file of ['src/app/page.tsx', 'public/return-atlas/data/version/index.json',
    'data/goalscorer/ligue-1-penalty-takers.json', 'data/goalscorer/club-penalty-season.json',
    'config/tennis-props-rate-trend-prospective-v1.json', 'scripts/audit-vercel-isr-policy.py',
    'scripts/build-site-brand-assets.mjs', 'scripts/oncourt-compute-fair-odds.py',
    'scripts/goalscorer-model.py', 'scripts/new-unknown-job.py', 'next.config.ts', 'package.json',
    'vercel.json', 'scripts/vercel-should-build.cjs', 'data/new-unknown.json']) {
    expect(commit([file]), 1);
  }
});
test('mixed multi-commit push retains earlier website changes', () => {
  const page = commit(['src/app/page.tsx']);
  const last = commit(['scripts/goalkeeper-saves-shadow.py']);
  expect(last, 0);
  expect(last, 1, { VERCEL_GIT_PREVIOUS_SHA: page.previous });
  expect(commit(['src/app/page.tsx', 'scripts/goalkeeper-saves-shadow.py']), 1);
});
test('first preview compares the whole branch, not the last commit', () => {
  const branchBase = git('rev-parse', 'HEAD');
  git('update-ref', 'refs/remotes/origin/golden-with-speed-insights', branchBase);
  git('update-ref', 'refs/remotes/origin/codex/fair-odds-daily-pitch-20260908', baseline);
  let last = commit(['scripts/goalkeeper-saves-shadow.py']);
  expect(last, 0, { VERCEL_GIT_PREVIOUS_SHA: '' });
  commit(['src/app/page.tsx']);
  last = commit(['scripts/goalkeeper_forecast_evidence.py']);
  expect(last, 1, { VERCEL_GIT_PREVIOUS_SHA: '' });
});
test('missing history and empty diffs build; force build always wins', () => {
  const c = commit(['scripts/goalkeeper-saves-shadow.py']);
  expect(c, 1, { VERCEL_GIT_PREVIOUS_SHA: 'badbadbad' });
  expect(c, 1, { VERCEL_GIT_PREVIOUS_SHA: c.current });
  expect(c, 1, { VERCEL_GIT_COMMIT_MESSAGE: 'fix: model [force build]' });
  git('update-ref', '-d', 'refs/remotes/origin/golden-with-speed-insights');
  git('update-ref', '-d', 'refs/remotes/origin/codex/fair-odds-daily-pitch-20260908');
  expect(c, 1, { VERCEL_GIT_PREVIOUS_SHA: '' });
});
test('moving a website file to an offline model path must build', () => {
  const previous = git('rev-parse', 'HEAD');
  git('mv', 'src/app/page.tsx', 'scripts/goalkeeper-moved.py');
  git('commit', '-m', 'move file');
  expect({ previous, current: git('rev-parse', 'HEAD'), message: 'move file' }, 1);
});

test("Aerial cloud data skips but its interface still builds", () => {
  expect(commit(["data/aerial/history.json.gz", "data/aerial/health.json", "public/fair-odds-lab/aerial.json", "scripts/aerial_data.py"]), 0);
  expect(commit(["src/components/aerial/AerialBoard.tsx", "data/aerial/health.json"]), 1);
});

