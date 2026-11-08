import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveTennisPortrait as portrait } from '../../src/lib/tennis-portrait.mjs';
import { buildTennisMatchday } from '../../src/lib/tennis-matchday.mjs';

test('initials identify brothers, with punctuation, spacing and accents', () => {
  for (const name of ['S. Tsitsipas','S Tsitsipas','Stefanos Tsitsipas','Tsitsipas S.','Tsitsipas S']) assert.equal(portrait(name)?.name,'Stefanos Tsitsipas');
  for (const name of ['F. Cerundolo','F Cerúndolo','Francisco Cerundolo','Cerundolo F.','Cerúndolo F']) assert.equal(portrait(name)?.name,'Francisco Cerundolo');
  for (const name of ['J.M. Cerundolo','J. M. Cerundolo','JM Cerundolo','Cerundolo J.M.','Cerundolo J. M.']) assert.equal(portrait(name)?.name,'Juan Manuel Cerundolo');
  assert.equal(portrait('P. Tsitsipas')?.name,'Petros Tsitsipas');
  assert.equal(portrait('P. Tsitsipas')?.src,null);
  for (const name of ['Tsitsipas','Cerundolo','X. Tsitsipas','S. Tsitsipas / P. Tsitsipas']) assert.equal(portrait(name),null);
});
test('ambiguous initials cannot borrow the only available photo', () => {
  assert.equal(portrait('J. Doe',[{name:'John Doe',src:'john.png'},{name:'Jane Doe',src:null}]),null);
});
test('verified Kouame artwork reaches Matchday/home H2H despite an older archive portrait', () => {
  const history={players:[{id:'kouame',name:'Moise Kouame',portrait:null},{id:'tsitsipas',name:'Stefanos Tsitsipas',portrait:null}],matches:[],asOf:'2026-11-03',through:'2026-11-02'};
  const fixture={captured_at:'2026-11-03T10:00:00Z',kickoff_iso:'2026-11-03T13:00:00Z',league:'ATP',league_name:'ATP Paris',player1_name:'Moise Kouame',player2_name:'Stefanos Tsitsipas'};
  const f=buildTennisMatchday([fixture],history,new Date('2026-11-03T11:00:00Z')).fixtures[0];
  assert.equal(f.players[0].portrait,'/players/tennis/moise-kouame.png');
  assert.equal(f.players[1].portrait,portrait('S. Tsitsipas').src);
  assert.deepEqual(f.wins,[0,0]);assert.equal(f.meetings,0);
  assert.equal(history.players[0].portrait,null,'Do not mutate historical records');
});

test('Challenger recovery is shared and does not borrow sibling portraits', () => {
  assert.equal(portrait('Kosuke Ogura')?.src, '/players/tennis/kosuke-ogura.jpg');
  assert.equal(portrait('Hikaru Shiraishi')?.src, '/players/tennis/hikaru-shiraishi.jpg');
  assert.equal(portrait('K. Ogura')?.name, 'Kosuke Ogura');
  assert.equal(portrait('Ewan Ogura'), null);
  assert.ok(portrait('Shunsuke Mitsui')?.src);
  assert.ok(portrait('Felipe Meligeni Rodrigues Alves')?.src);
});
