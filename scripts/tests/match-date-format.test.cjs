const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync('src/lib/format.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
function previous(value) {
  if(!value)return '-'; const d=new Date(value+'T12:00:00');
  return isNaN(d.getTime())?'-':d.toLocaleDateString('en-GB',{day:'numeric',month:'short'});
}
test('shared formatter preserves every day across leap years, DST and several time zones',()=>{
  const originalTZ=process.env.TZ;
  try {
    for(const timezone of ['UTC','Europe/London','America/Los_Angeles','Pacific/Kiritimati','Pacific/Pago_Pago']) {
      process.env.TZ=timezone; const scope={exports:{},Intl,Date}; vm.runInNewContext(code,scope);
      for(let stamp=Date.UTC(2000,0,1);stamp<Date.UTC(2036,0,1);stamp+=86400000) {
        const date=new Date(stamp).toISOString().slice(0,10);
        assert.equal(scope.exports.formatMatchDate(date),previous(date),timezone+' '+date);
      }
      for(const value of [null,undefined,'','invalid','2026-99-01','2026-01-01T12:00:00Z']) assert.equal(scope.exports.formatMatchDate(value),previous(value));
    }
  } finally { if(originalTZ===undefined)delete process.env.TZ;else process.env.TZ=originalTZ; }
});
