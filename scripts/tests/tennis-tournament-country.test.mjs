import test from 'node:test';
import assert from 'node:assert/strict';
import { countryForTournament, lookupTournamentCountry } from '../../src/lib/tennis-tournament-country.mjs';
test('verified current tournament editions use venue country', () => {
 assert.equal(countryForTournament('Helsinki','Challenger','2026-11-15')?.code,'fi');
 assert.equal(countryForTournament('Helsinki Challenger','Challenger','2026-11-16')?.code,'fi');
 assert.equal(countryForTournament('Finals','ATP','2026-11-17')?.code,'it');
 assert.equal(countryForTournament('Lima 3 Challenger','Challenger','2026-11-14')?.code,'pe');
});
test('unknown editions, category mismatches and invalid dates stay unknown', () => {
 for (const args of [['Finals','ATP','2027-11-17'],['Metz','ATP','2026-11-15'],['Unknown','Challenger','2026-11-15'],['Finals','ATP','invalid'],['Finals','ATP','2026-11-99']]) assert.equal(countryForTournament(...args),null);
});
test('conflicting exact edition records never choose a flag arbitrarily', () => {
 const base={event:'Tour Finals',aliases:[],tour:'ATP',from:'2026-11-01',through:'2026-11-30'};
 assert.equal(lookupTournamentCountry('Tour Finals','ATP','2026-11-15',[{...base,code:'it',name:'Italy'},{...base,code:'gb',name:'United Kingdom'}]),null);
});
