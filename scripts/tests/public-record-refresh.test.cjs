const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const files = ['src/app/HomepageClient.tsx', 'src/app/player-props/PlayerPropsClient.tsx', 'src/app/tennis-tips/TennisTipsClient.tsx'];

// Execute the actual component refresh callback with deferred network responses.
// The UI setters remain observable without mocking or rewriting its refresh logic.
function harness(file, initialLoading = false) {
  const source = ts.createSourceFile(file, fs.readFileSync(path.join(__dirname, '../..', file), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let callback;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'fetchData') callback = node.initializer.arguments[0].getText(source);
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(callback);
  const state = {loading:initialLoading, pending:['existing pick'], recent:['existing result']};
  let now = 10000;
  const requests = [];
  const context = {
    refreshInFlight:{current:false}, lastRefreshStarted:{current:0}, Date:{now:()=>now},
    console:{error:()=>{}},
    fetch: (url) => new Promise((resolve,reject)=>requests.push({url,resolve,reject})),
    setLoading:v=>state.loading=v, setPendingBets:v=>state.pending=v, setRecentBets:v=>state.recent=v,
    setStats:()=>{}, setProgressionRows:()=>{}, calculateCombinedStats:()=>{}, setRecordStatus:()=>{},
    setLast7Error:()=>{}, setLast7DaysProfit:()=>{}, setLast7DaysCount:()=>{},
  };
  const code=ts.transpileModule('const refresh = '+callback+'; refresh;', {compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
  return {refresh:vm.runInNewContext(code,context),state,requests,advance:()=>now+=1100};
}
for (const file of files) {
  test(file+': tab events share one request, preserve displayed picks, and later refresh succeeds',async()=>{
    const h=harness(file);
    const first=h.refresh(); await h.refresh();
    assert.equal(h.requests.length,1);
    assert.equal(h.state.loading,false);
    assert.deepEqual(h.state.pending,['existing pick']);
    h.requests[0].resolve({ok:true,json:async()=>({pending:['fresh pick'],recent:['fresh result']})});
    await first;
    assert.deepEqual(h.state.pending,['fresh pick']);
    await h.refresh(); assert.equal(h.requests.length,1,'fast response must still coalesce adjacent tab events');
    h.advance(); const next=h.refresh(); assert.equal(h.requests.length,2);
    h.requests[1].resolve({ok:true,json:async()=>({pending:['newer pick'],recent:[]})});
    await next; assert.deepEqual(h.state.pending,['newer pick']);
  });
  test(file+': failed refresh retains picks and releases the request guard',async()=>{
    const h=harness(file);
    const first=h.refresh(); h.requests[0].reject(new Error('offline')); await first;
    assert.deepEqual(h.state.pending,['existing pick']); assert.equal(h.state.loading,false);
    h.advance(); const retry=h.refresh(); assert.equal(h.requests.length,2);
    h.requests[1].resolve({ok:false,json:async()=>({error:'unavailable'})}); await retry;
    assert.deepEqual(h.state.recent,['existing result']);
  });
  if(!file.includes('Homepage')) test(file+': initial unseeded loading still finishes',async()=>{
    const h=harness(file,true); const first=h.refresh(); assert.equal(h.state.loading,true);
    h.requests[0].resolve({ok:true,json:async()=>({pending:[],recent:[]})}); await first;
    assert.equal(h.state.loading,false);
  });
}
