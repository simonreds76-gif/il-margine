"""Reject positively verified split player histories; never merge fuzzy identities."""
from collections import defaultdict
import csv
from tennis_props_names import norm_name

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))

def verify_identity_buckets(root, baseline):
    verified=[];unverified=[]
    for tour in ('atp','wta'):
        native={r['id']:r for r in read(root/f'data/oncourt/players_{tour}.csv')}
        archive=read(root/f'data/sackmann/{tour}_players.csv');index=defaultdict(list)
        active={str(r['player_id']) for r in baseline if r['tour']==tour.upper()}
        for player in archive:
            tokens=norm_name(player['name_first']+' '+player['name_last']).split()
            if len(tokens)>=2 and player['player_id'] in active:index[(tokens[0],tokens[-1])].append(player)
        singles={(r['player_id'][3:],r['player_name']) for r in baseline if r['tour']==tour.upper() and r['player_id'].startswith('oc:') and '/' not in r['player_name'] and '&' not in r['player_name']}
        for oid,name in sorted(singles):
            tokens=norm_name(name).split()
            if len(tokens)<2:continue
            candidates=index.get((tokens[0],tokens[-1]),[]);person=native.get(oid,{})
            if not candidates:continue
            same=[p for p in candidates if person.get('birthdate') and person['birthdate'].replace('-','')==p.get('dob') and person.get('country') and person['country']==p.get('ioc')]
            entry=dict(tour=tour.upper(),native_id=oid,name=name,archive_ids=[p['player_id'] for p in same or candidates])
            (verified if same else unverified).append(entry)
    if verified:raise ValueError('verified_split_player_histories:'+str(verified))
    return dict(state='NO_VERIFIED_SPLITS',verified_splits=0,unverified_name_candidates=unverified,rule='Explicit aliases only; name candidates require matching birthdate and country before a split is rejected. No inferred merge.')
