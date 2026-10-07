import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {atlasResearchHref,readAtlasResearch} from '../../src/components/return-atlas/research-links.mjs';

const archive=name=>{
  const release=JSON.parse(fs.readFileSync(`src/data/${name}-release.json`,'utf8'));
  return JSON.parse(fs.readFileSync(`public${release.indexUrl}`,'utf8'));
};
test('every current Matchup identity opens the same named Atlas player, independent of index order',()=>{
  const matchup=archive('tennis-matchup'),atlas=archive('return-atlas');
  const reversed=[...atlas.players].reverse();
  for(const player of matchup.players){
    const companion=matchup.players.find(p=>p.id!==player.id);
    const url=new URL(atlasResearchHref(player.id,companion.id,'outdoor-hard'),'https://ilmargine.bet');
    const result=readAtlasResearch(url.search,reversed);
    assert.deepEqual(result,{ids:[player.id,companion.id],surface:'outdoor-hard',missing:false});
    assert.equal(reversed.find(p=>p.id===result.ids[0]).name,player.name);
  }
});
test('old, duplicate and hostile links cannot open the wrong identity or arbitrary resource',()=>{
  const players=[{id:'a'},{id:'b'}];
  assert.deepEqual(readAtlasResearch('?player=unknown&compare=b&surface=bogus',players),{ids:['b'],surface:'all',missing:true});
  assert.deepEqual(readAtlasResearch('?player=a&compare=a&surface=clay',players),{ids:['a'],surface:'clay',missing:false});
  assert.deepEqual(readAtlasResearch('?player=__proto__&compare=%3Cscript%3E',players),{ids:[],surface:'all',missing:true});
  assert.deepEqual(readAtlasResearch('',players),{ids:[],surface:'all',missing:false});
  const url=new URL(atlasResearchHref('a&surface=grass','b','clay'),'https://ilmargine.bet');
  assert.equal(url.searchParams.get('player'),'a&surface=grass');
  assert.equal(url.searchParams.get('surface'),'clay');
  assert.equal(url.pathname,'/return-atlas');
});
