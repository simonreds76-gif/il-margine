const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript');
const root = path.resolve(__dirname, '../..');
function load(file) {
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInThisContext('(function(require,module,exports){'+code+'\n})')((id) => load(path.resolve(path.dirname(file), id+'.ts')), module, module.exports);
  return module.exports;
}
const { classifyProp, buildPropPerformance } = load(path.join(root, 'src/lib/prop-performance.ts'));
const row = (id, selection, extra={}) => ({ id, event: 'Roma vs Como', player: 'Player', selection, status: 'won', stake: 1, profit_loss: 1, date: '2026-10-17', ...extra });

test('specific markets precede broad labels; team totals and combinations remain separate', () => {
  for (const [bet,key] of [
    [row(1,'Over 0.5 Shots on Target Outside the Box'),'sot'],
    [row(2,'Over 1.5 Fouls Won'),'foulsWon'],
    [row(3,'Over 1.5 Fous'),'fouls'],
    [row(4,'Over 1.5 Fouls Committed'),'fouls'],
    [row(5,'Over 2.5',{player:'Courtois Saves'}),'saves'],
    [row(6,'Vojvoda',{player:'Over 1.5 Tackles'}),'tackles'],
    [row(7,'Over 12.5 Shots',{player:'Roma'}),'team'],
    [row(8,'Over 22.5',{player:'Match Shots'}),'team'],
    [row(9,'Yes',{player:'Both Teams to Receive Cards'}),'team'],
    [row(10,'Over 0.5 Shots and Over 0.5 Fouls'),'other'],
    [row(11,'To Score 2 or More Goals'),'goals'],
    [row(12,'Over 2.5'),'other'],
  ]) assert.equal(classifyProp(bet),key);
});
test('ROI uses actual stakes and excludes void, pending, duplicate and malformed rows', () => {
  const bets = [row(1,'Over 1.5 Shots',{stake:2,profit_loss:3}),row(2,'Over 1.5 Shots',{stake:0.5,profit_loss:-0.5,status:'lost'}),row(3,'Over 1.5 Shots',{status:'void',profit_loss:0}),row(4,'Over 1.5 Shots',{status:'pending'}),row(5,'Over 1.5 Shots',{profit_loss:null})];
  const [g]=buildPropPerformance([...bets,bets[0]], [bets[0],bets[3],bets[3]]);
  assert.equal(g.rows.length,2);assert.equal(g.wins,1);assert.equal(g.losses,1);
  assert.equal(g.stake,2.5);assert.equal(g.profit,2.5);assert.equal(g.roi,100);assert.equal(g.pending.length,1);
});
test('new selections and later settlements update buckets without persisted totals', () => {
  const pending=row(20,'Over 3.5 Saves',{status:'pending',profit_loss:null});
  assert.equal(buildPropPerformance([], [pending])[0].roi,null);
  const settled={...pending,status:'won',profit_loss:1.4};
  const [g]=buildPropPerformance([settled], []);
  assert.equal(g.pending.length,0);assert.equal(g.rows.length,1);assert.equal(g.roi,140);
});
test('league filtered input and latest-first drilldown retain all eligible selections', () => {
  const rows=[row(1,'Over 1.5 Shots',{category:'pl',date:'2026-02-04'}),row(2,'Over 1.5 Shots',{category:'seriea'}),row(3,'Over 1.5 Shots',{category:'pl'})];
  const [g]=buildPropPerformance(rows.filter(r=>r.category==='pl'));
  assert.deepEqual(g.rows.map(r=>r.id),[3,1]);assert.equal(g.stake,2);
});
test('full history pagination continues beyond the database response cap and fails on errors', async () => {
  const { readRecordPages }=load(path.join(root,'src/lib/read-record-pages.ts'));
  const rows=Array.from({length:1201},(_,id)=>({id}));
  assert.equal((await readRecordPages(async(from,to)=>rows.slice(from,to+1))).length,1201);
  await assert.rejects(readRecordPages(async(from,to)=>{if(from>=500)throw new Error('unavailable');return rows.slice(from,to+1);}),/unavailable/);
  await assert.rejects(readRecordPages(async()=>rows.slice(0,500),500,2),/refusing a partial total/);
});
