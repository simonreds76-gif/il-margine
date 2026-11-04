const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const cache = {};
function load(name) {
  if (cache[name]) return cache[name].exports;
  const module = cache[name] = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(`src/lib/${name}.ts`, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  new Function('module', 'exports', 'require', code)(module, module.exports, dep => load(dep.replace('./', '')));
  return module.exports;
}
const { profitHistory, reconciledHistory, profitWindow, compactHistory, reportSelectionHistory } = load('model-profit-history');
const row = (date, pnl, extra = {}) => ({ date, pnl, result: pnl < 0 ? 'loss' : 'win', settlement_status: 'settled', market: 'aces', ...extra });

test('sorts match dates and groups same-day settlements without mutating ledger', () => {
  const rows = [row('2026-10-03', -1), row('2026-10-01', 2), row('2026-10-01', -.5)];
  const r = profitHistory(rows, 'props-record', 'props');
  assert.deepEqual(r.days.map(d => [d.date, d.cumulative, d.settled]), [['2026-10-01', 1.5, 2], ['2026-10-03', .5, 1]]);
  assert.equal(rows[0].date, '2026-10-03');
});
test('pending, void, quarantined and other markets never affect props graph', () => {
  const r = profitHistory([row('2026-10-01', 2), row('2026-10-02', 99, { result: '', settlement_status: 'pending' }), row('2026-10-02', 10, { result: 'void' }), row('2026-10-02', 5, { quarantine_reason: 'duplicate' }), row('2026-10-02', 4, { market: 'breaks' })], 'props-record', 'props');
  assert.equal(r.profit, 2); assert.equal(r.settled, 1);
});
test('missing dates or profit and duplicate IDs fail closed, no guessed stakes', () => {
  const r = profitHistory([row('', -1), row('2026-02-30', 2), row('2026-10-01', '', { selected_odds: 2 }), row('2026-10-03', 1, { signal_id: 'same' }), row('2026-10-03', 1, { signal_id: 'same' })], 'props-record', 'props');
  assert.equal(r.omitted, 4); assert.equal(r.settled, 1);
});
test('match date takes precedence over later batch settlement time', () => {
  assert.equal(profitHistory([row('2026-10-04', 1, { match_date: '2026-10-05', settled_at_utc: '2026-11-02T22:00:00Z' })], 'props-record').days[0].date, '2026-10-05');
});
test('reconciles count and profit with the same snapshot, refuses partial/different cohort', () => {
  const csv = 'date,pnl,result,settlement_status,market\n2026-10-01,2,win,settled,aces\n2026-10-02,-1,loss,settled,double_faults\n';
  assert.equal(reconciledHistory(csv, 'props-record', { settled: 2, profit: 1 }).days.length, 2);
  assert.ok(reconciledHistory(csv, 'props-record', { settled: 3, profit: 1 }).message);
  assert.ok(reconciledHistory(csv, 'props-record', { settled: 2, profit: 2 }).message);
  assert.equal(reconciledHistory(csv, 'props-record', { settled: 1, profit: 2 }, 'aces').days.length, 1);
});
test('recent window retains opening balance and measures daily drawdown from it', () => {
  const r = profitHistory([row('2026-08-01', 4), row('2026-10-01', -1), row('2026-10-04', 2)], 'props-record');
  const window = profitWindow(r, 30);
  assert.equal(window.opening, 4); assert.equal(window.change, 1); assert.equal(window.drawdown, 1);
  assert.equal(window.days.at(-1).cumulative, 5);
});
test('empty and all losing histories preserve zero origin', () => {
  assert.equal(profitWindow(profitHistory([], 'props-record'), null).change, 0);
  const r = profitWindow(profitHistory([row('2026-10-01', -1), row('2026-10-02', -1)], 'props-record'), null);
  assert.equal(r.opening, 0); assert.equal(r.drawdown, 2);
});
test('unresolved status overrides stale outcome and profit fields', () => {
  assert.equal(profitHistory([row('2026-10-01', 50, { settlement_status: 'pending' }), row('2026-10-01', 20, { settlement_status: 'void' })], 'props-record').settled, 0);
});

test('compact histories require valid ordered dates, exact counts and running balances', () => {
  const h={days:[{date:'2026-10-01',profit:2,cumulative:2,settled:1},{date:'2026-10-02',profit:-1,cumulative:1,settled:2}],profit:1,settled:3,omitted:0,note:'Reconstructed'};
  assert.equal(compactHistory(h,{settled:3,profit:1}).message,undefined);
  assert.equal(compactHistory(h,{settled:3,profit:1}).note,'Reconstructed');
  for(const broken of [{...h,profit:undefined},{...h,profit:NaN},{...h,settled:2},{...h,days:[h.days[1],h.days[0]]},{...h,days:[{...h.days[0],cumulative:10},h.days[1]]},{...h,days:[{...h.days[0],date:'2026-02-30'},h.days[1]]}]) assert.ok(compactHistory(broken,{settled:3,profit:1}).message);
});

test('report histories use recorded P/L, never pending values or regrade forecasts', () => {
  const records=[{id:'a',start:'2026-10-01T12:00:00Z',status:'won',profit:.9},{id:'b',start:'2026-10-02T12:00:00Z',status:'pending',profit:99}];
  assert.equal(reportSelectionHistory(records,{settled:1,profit:.9}).profit,.9);
  assert.ok(reportSelectionHistory([...records,records[0]],{settled:2,profit:1.8}).message);
});

test('all new chart cohorts reconcile with saved source fixtures', {skip:!process.env.MONITOR_CHART_FIXTURES}, () => {
  const path=process.env.MONITOR_CHART_FIXTURES;
  const d=JSON.parse(fs.readFileSync(process.env.MONITOR_SNAPSHOT_TEST,'utf8'));
  const histories=JSON.parse(fs.readFileSync(path+'/compact-histories.json','utf8'));
  for(const [key,h] of Object.entries(histories)) {
    const expected=key==='astra'?d.sections.tennis_context_forward.candidate:d.sections.tennis_model_evidence.lanes[key];
    assert.equal(compactHistory(h,{settled:expected.settled,profit:expected.pnl_units}).message,undefined,key);
  }
  const sisal=d.sections.tennis_sisal_5050;
  for(const [name,r] of [['Sisal full',sisal],...Object.entries(sisal.event_comparison.versions)]) {
    const a=r.arms.blend50; assert.equal(reportSelectionHistory(r.selections,{settled:a.settled,profit:a.pnl_units}).message,undefined,name);
  }
  const shape=d.sections.tennis_match_shape;
  for(const a of ['current','T1']) for(const market of ['total_games','game_handicap']) {
    const s=shape.arms[a][market], rows=shape.records.filter(r=>r.market===market&&r.arms[a].selected).map(r=>({...r,profit:r.arms[a].profit}));
    assert.equal(reportSelectionHistory(rows,{settled:s.settled,profit:s.profit}).message,undefined,`${a} ${market}`);
  }
  const bp=d.sections.tennis_breakpoint_c;
  assert.equal(reportSelectionHistory(bp.records.filter(r=>r.selected).map(r=>({...r,status:r.status==='COMPLETED_RESEARCH_OUTCOME'?'settled':r.status})),{settled:bp.wins+bp.losses,profit:bp.profit}).message,undefined,'Break Point C');
  const raw=JSON.parse(fs.readFileSync(path+'/football-canonical-files.json','utf8'));
  const football=JSON.parse(fs.readFileSync(path+'/football-chart-source.json','utf8')).snapshots.find(s=>s.snapshot_key==='corners_state');
  const weekly=JSON.parse(football.f0.content);
  const evidence=JSON.parse(raw['data/goalkeeper-saves/gk-saves-v1-shadow-report.json']).evidence;
  assert.equal(reconciledHistory(raw['data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv'],'gk',{settled:evidence.settled,profit:evidence.pnl_units}).message,undefined,'GK');
  const {signalCsv}=load('admin-signal-format');
  for(const [id,csv] of [['team_shots_v4',raw['data/football-form/team-shots-v4-shadow-clv.csv']],['corners_v3',football.f2.content]]) {
    const rows=signalCsv(csv).filter(v=>!String(v.blocked_reason||'').trim()&&!['true','1','yes'].includes(String(v.confidence_guard_applied).toLowerCase())&&v.signal_status!=='warmup_tracking');
    const s=weekly.football_counts_vnext[id].prospective;
    assert.equal(reconciledHistory(rows,id,{settled:s.settled,profit:s.pnl_units}).message,undefined,id);
  }
});
test('saved current private props ledger reconciles without modifying it', { skip: !process.env.MONITOR_SNAPSHOT_TEST }, () => {
  const d = JSON.parse(fs.readFileSync(process.env.MONITOR_SNAPSHOT_TEST, 'utf8'));
  const s = d.sections.tennis_props_shadow_decision;
  const r = reconciledHistory(d.admin_files['props-record'], 'props-record', { settled: s.settled, profit: s.pnl_units });
  assert.equal(r.message, undefined); assert.equal(r.settled, s.settled);
  for (const market of s.by_market) {
    assert.equal(reconciledHistory(d.admin_files['props-record'], 'props-record', { settled: market.settled, profit: market.pnl_units }, market.market).message, undefined);
  }
  for (const key of ['tennis_hardcourt_scout', 'tennis_astrissimo', 'tennis_indoor_paper']) {
    const section = d.sections[key];
    assert.equal(reconciledHistory(section.selections, key, { settled: section.settled, profit: section.pnl_units }).message, undefined, key);
  }
  console.log(JSON.stringify({ settled: r.settled, profit: r.profit, latest: r.days.at(-1), recent30: profitWindow(r, 30).change }));
});
