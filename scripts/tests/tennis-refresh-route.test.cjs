const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function load(relative, dependencies) {
  const code = ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '../..', relative), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const compiled = { exports: {} };
  new Function('require', 'module', 'exports', code)((name) => {
    if (!(name in dependencies)) throw new Error(`Unexpected dependency: ${name}`);
    return dependencies[name];
  }, compiled, compiled.exports);
  return compiled.exports;
}
const helpers = load('src/lib/tennis-refresh-status.ts', {});
const command = {
  request_id: 'failed-request', state: 'failed', error: 'Private Monitor upload failed.',
  completed_at: '2026-11-03T21:21:24Z',
};
const metadata = {
  source: 'windows_local_tennis_pipeline', schema_version: 3, file_count: 34,
  payload_hash: 'a'.repeat(64), generated_at: '2026-11-04T10:31:22Z', updated_at: '2026-11-04T10:31:22Z',
};

function fixture({ authenticated = true, saved = command, snapshotError = false, snapshotThrows = false } = {}) {
  const reads = [];
  const client = { from(table) {
    assert.ok(['site_settings', 'goalscorer_live_snapshot'].includes(table));
    const read = { table }; reads.push(read);
    return {
      select(fields) { read.fields = fields; return this; },
      eq(key, value) { read.filter = [key, value]; return this; },
      abortSignal(signal) { assert.ok(signal instanceof AbortSignal); return this; },
      async maybeSingle() {
        if (table === 'site_settings') return { data: { value: JSON.stringify(saved) }, error: null };
        if (snapshotThrows) throw new Error('Read timeout');
        return snapshotError ? { data: null, error: { message: 'Unavailable' } } : { data: metadata, error: null };
      },
      // Deliberately no mutations: an accidental write fails these GET tests.
    };
  } };
  const route = load('src/app/api/admin/tennis-refresh/route.ts', {
    'node:crypto': require('node:crypto'),
    'next/server': { NextResponse: { json(body, options) { return { body, status: options?.status || 200 }; } } },
    '@/lib/admin-auth': { isAdminSession: async () => authenticated },
    '@/lib/supabase-server': { getSupabaseAdmin: () => client },
    '@/lib/tennis-refresh-status': helpers,
  });
  return { route, reads };
}

test('authenticated GET checks compact hosted metadata and preserves original failure', async () => {
  const { route, reads } = fixture();
  const result = await route.GET(new Request('https://ilmargine.bet/api/admin/tennis-refresh'));
  assert.equal(result.status, 200);
  assert.equal(result.body.command.state, 'failed');
  assert.equal(result.body.command.monitor_upload_recovered_at, metadata.generated_at);
  assert.equal(reads.length, 2);
  assert.deepEqual(reads[1].filter, ['snapshot_key', 'tennis_evidence_v1']);
  assert.ok(!reads[1].fields.split(',').includes('payload'));
});

test('authentication and request identity are checked before snapshot access', async () => {
  const denied = fixture({ authenticated: false });
  assert.equal((await denied.route.GET(new Request('https://ilmargine.bet/api/admin/tennis-refresh'))).status, 401);
  assert.equal(denied.reads.length, 0);
  const mismatch = fixture();
  assert.equal((await mismatch.route.GET(new Request('https://ilmargine.bet/api/admin/tennis-refresh?request_id=other'))).status, 404);
  assert.equal(mismatch.reads.length, 1);
});

test('metadata errors and timeouts retain the failure; normal requests need no extra read', async () => {
  for (const options of [{ snapshotError: true }, { snapshotThrows: true }, { saved: { ...command, state: 'started' } }]) {
    const { route, reads } = fixture(options);
    const result = await route.GET(new Request('https://ilmargine.bet/api/admin/tennis-refresh'));
    assert.deepEqual(result.body.command, options.saved || command);
    assert.equal(reads.length, options.saved ? 1 : 2);
  }
});
