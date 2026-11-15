import test from 'node:test';
import assert from 'node:assert/strict';
import {tournamentOf,readBrowseState,browseQuery,isQualifying,displayDay} from '../../src/lib/tennis-matchday-browse.mjs';
const fixture={tour:'ATP',event:'Finals - Groups',start:'2026-11-16T12:00:00Z',qualifying:false};
test('Finals remains the tournament name; groups and qualifying are rounds',()=>{
 assert.equal(tournamentOf(fixture).label,'Finals'); assert.equal(tournamentOf(fixture).round,'Groups');
 const q={...fixture,tour:'Challenger',event:'Metz - Qualifiers'};
 assert.equal(tournamentOf(q).label,'Metz');assert.equal(isQualifying(q),true);assert.equal(tournamentOf(q).surface,'indoor-hard');
 assert.equal(tournamentOf({...fixture,event:'Unknown - Semi-final'}).label,'Unknown');
});
test('surface needs the exact tour, label and edition window',()=>{
 assert.equal(tournamentOf(fixture).surface,'indoor-hard');
 for(const change of [{start:'2027-11-16T12:00:00Z'},{tour:'Challenger'},{event:'Finals 2 - Groups'},{start:'2026-12-01T12:00:00Z'}]) assert.equal(tournamentOf({...fixture,...change}).surface,'unknown');
 assert.equal(tournamentOf({...fixture,tour:'Challenger',event:'Sydney - Qualifiers'}).surface,'outdoor-hard');
 assert.equal(tournamentOf({...fixture,tour:'Challenger',event:'Montevideo - Qualifiers'}).surface,'clay');
});
test('view state round-trips through URLs; unrelated parameters survive',()=>{
 const s={view:'upcoming',resultDay:'latest',filter:'tomorrow',tour:'Challenger',tournament:'["Challenger","Metz","metz-2026-11-16"]',search:'Jean & Paul',qualifying:false,order:'time'};
 assert.deepEqual(readBrowseState(browseQuery(s,'campaign=one')),s);
 assert.equal(new URLSearchParams(browseQuery(s,'campaign=one')).get('campaign'),'one');
 assert.equal(readBrowseState('?day=bogus&tour=WTA&qualifying=anything').filter,'auto');
 assert.equal(readBrowseState('').qualifying,true);
});

test('default landing advances when today is empty but an explicit date stays selected',()=>{
 const fixtures=[{start:'2026-11-16T12:00:00Z'}],now=new Date('2026-11-15T23:00:00Z');
 assert.equal(displayDay('auto',fixtures,now),'tomorrow');
 assert.equal(displayDay('today',fixtures,now),'today');
 assert.equal(tournamentOf({...fixture,start:'2026-11-23T00:30:00Z'}).surface,'indoor-hard');
});

test('Results filters persist without mutating upcoming date',()=>{const s={...readBrowseState(''),view:'results',resultDay:'all',tour:'Challenger'};assert.deepEqual(readBrowseState(browseQuery(s)),s)});

test('ATP defaults preserve explicit All and Challenger URLs',()=>{
 assert.equal(readBrowseState('').tour,'ATP');
 for(const tour of ['ATP','all','Challenger']) assert.equal(readBrowseState(browseQuery({...readBrowseState(''),tour})).tour,tour);
 assert.equal(new URLSearchParams(browseQuery({...readBrowseState(''),tour:'all'})).get('tour'),'all');
});
