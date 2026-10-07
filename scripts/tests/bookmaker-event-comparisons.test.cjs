const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const Module=require('node:module');
function load(path){const mod=new Module(path,module);mod.filename=path;mod.paths=module.paths;mod._compile(ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,path);return mod.exports;}
const {tennisEventComparisons,loadTennisEventComparisons}=load('src/lib/bookmakers/event-comparisons.ts');
const {devig,bookSum}=load('src/lib/calculator/math.ts');
const snapshot=JSON.parse(fs.readFileSync('data/bookmakers/margin-index.json'));
test('verified raw capture restores all complete tennis quotes without weakening aggregate gate',()=>{
  const events=loadTennisEventComparisons(snapshot.generated_at,snapshot.capture.raw_capture_sha256);
  assert.equal(events.length,2);assert.equal(events[0].segment.operators.length,21);assert.equal(events[1].segment.operators.length,4);
  assert.equal(snapshot.segments.find(s=>s.sport==='Tennis').operators.length,4);
  assert.ok(events[0].segment.operators.some(r=>r.name==='Bet365'));
});
test('unverified capture cannot be loaded',()=>assert.deepEqual(loadTennisEventComparisons(snapshot.generated_at,'wrong'),[]));
test('incomplete and duplicated quotes and exchanges cannot enter a match comparison',()=>{
  const prices=[{code:'B3',bookmaker:'bet365',fractional:'1/1'},{code:'FR',bookmaker:'Betfred',fractional:'1/1'},{code:'BF',bookmaker:'Exchange',fractional:'1/1'}];
  const page={sport:'tennis',home:'A',away:'B',url:'source',captured_at:'date',grids:[{market:'Win Market',selections:[{label:'A',prices},{label:'B',prices}]}]};
  assert.equal(tennisEventComparisons([page])[0].segment.operators.length,2);
  page.grids[0].selections[1].prices=[prices[0],prices[0],prices[2]];
  assert.deepEqual(tennisEventComparisons([page]),[]);
});
test('all removal methods return a balanced 100 percent book and expected fair prices',()=>{
  for(const method of ['proportional','shin','oddsRatio']){const r=devig([1.9,1.9],method);assert.ok(Math.abs(r.fairOdds[0]-2)<1e-6);assert.ok(Math.abs(r.probabilities.reduce((a,b)=>a+b,0)-1)<1e-6);}
  const r=devig([2.1,3.4,3.6],'proportional');assert.ok(bookSum(r.fairOdds)-1<1e-8);
});
