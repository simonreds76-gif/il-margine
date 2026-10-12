const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const sharp=require('sharp');
const vm=require('node:vm');
const ts=require('typescript');
const root=path.resolve(__dirname,'../..');
const manifest=require('../../src/lib/team-logo-thumbnails.json');
const moduleScope={exports:{}};
const code=ts.transpileModule(fs.readFileSync(path.join(root,'src/lib/small-team-logo.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
vm.runInNewContext(code,{exports:moduleScope.exports,require:()=>manifest});
const {smallTeamLogo}=moduleScope.exports;
test('only known local crests are substituted; unknown and external logos are preserved',()=>{
  const original='/team-logos/serie-a/torino.png';
  assert.equal(smallTeamLogo(original),manifest[original]);
  assert.equal(smallTeamLogo('https://ilmargine.bet'+original),manifest[original]);
  assert.equal(smallTeamLogo('/team-logos/new-club.png'),'/team-logos/new-club.png');
  assert.equal(smallTeamLogo('https://example.com'+original),'https://example.com'+original);
  assert.equal(smallTeamLogo(null),null);
});
test('every mapped thumbnail exists, preserves proportions and fits high-density tip icons',async()=>{
  for(const [original,thumb] of Object.entries(manifest)) {
    const a=await sharp(path.join(root,'public',original)).metadata();
    const b=await sharp(path.join(root,'public',thumb)).metadata();
    assert.equal(b.format,'webp'); assert.ok(b.width<=144 && b.height<=144);
    assert.ok(Math.abs(a.width/a.height-b.width/b.height)<0.025,original);
    if (a.hasAlpha && !b.hasAlpha) { const stats=await sharp(path.join(root,"public",original)).stats(); assert.equal(stats.isOpaque,true,original); }
  }
});
