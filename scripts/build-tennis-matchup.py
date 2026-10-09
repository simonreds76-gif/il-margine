"""Build a LOCAL research panel. Never writes into public/ or changes model weights."""
import argparse
import csv
import hashlib
import importlib.util
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

REGIONS = {
    'Asia': 'CHN JPN KOR IND KAZ QAT UAE KSA ISR HKG TPE THA MAS SGP UZB',
    'Europe': 'AUT BEL BIH BUL CRO CZE DEN ESP EST FIN FRA GBR GER GRE HUN IRL ITA LAT LTU LUX MON NED NOR POL POR ROU RUS SRB SUI SVK SLO SWE TUR UKR',
    'North America': 'CAN USA MEX',
    'South America': 'ARG BRA CHI COL ECU PER URU',
    'Oceania': 'AUS NZL',
    'Africa': 'MAR RSA EGY TUN',
}
COUNTRY_NAMES = dict(CHN='China', JPN='Japan', KOR='South Korea', IND='India', KAZ='Kazakhstan',
 QAT='Qatar', UAE='United Arab Emirates', KSA='Saudi Arabia', ISR='Israel', AUS='Australia', NZL='New Zealand',
 ARG='Argentina', BRA='Brazil', CHI='Chile', CAN='Canada', USA='United States', MEX='Mexico', MAR='Morocco',
 AUT='Austria', BEL='Belgium', BIH='Bosnia and Herzegovina', BUL='Bulgaria', CRO='Croatia', ESP='Spain',
 FRA='France', GBR='United Kingdom', GER='Germany', GRE='Greece', ITA='Italy', MON='Monaco', NED='Netherlands',
 POR='Portugal', ROU='Romania', SRB='Serbia', SUI='Switzerland', SWE='Sweden')
REGION_OF = {country: region for region, countries in REGIONS.items() for country in countries.split()}
SURFACES = {'1': 'outdoor-hard', '2': 'clay', '3': 'indoor-hard', '5': 'grass'}

def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.replace('ø', 'o')).lower() if c.isalnum())

def scores(value):
    return re.findall(r'(\d+)-(\d+)', value)

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        yield from csv.DictReader(handle)

def ratio(row, numerator, denominator):
    try:
        a, b = int(row[numerator]), int(row[denominator])
        return [a, b] if b > 0 and 0 <= a <= b else None
    except (ValueError, TypeError, KeyError):
        return None

def point_stats(row, side):
    one = ratio(row, side+'_w1s', side+'_w1sof')
    two = ratio(row, side+'_w2s', side+'_w2sof')
    serve = None
    if one and two:
        serve = [one[0]+two[0], one[1]+two[1]]
        try:
            if serve[1] != int(row[side+'_svpt']): serve = None
        except (ValueError, KeyError): serve = None
    return {'serve': serve, 'first': one, 'second': two,
            'return': ratio(row, side+'_rpw', side+'_rpwof'),
            'aces': ratio(row, side+'_ace', side+'_svpt'),
            'doubleFaults': ratio(row, side+'_df', side+'_svpt')}

def key(row):
    return tuple(row[k] for k in ['winner_id', 'loser_id', 'tour_id', 'round_id'])

def completed(score):
    """Completed conventional singles only, including old best-of-five formats."""
    text = re.sub(r'\(\d+\)', '', score).strip()
    if not re.fullmatch(r'\d+-\d+(?:\s+\d+-\d+)*', text): return False
    sets = [tuple(map(int, part.split('-'))) for part in text.split()]
    wins = [0, 0]
    needed = 3 if len(sets) > 3 or sum(a > b for a,b in sets) == 3 else 2
    for a,b in sets:
        hi,lo = max(a,b),min(a,b)
        if max(wins) >= needed or not ((hi==6 and lo<=4) or (hi==7 and lo in (5,6)) or (hi>7 and hi-lo==2)):
            return False
        wins[a<b] += 1
    return wins[0] == needed and wins[1] < needed

def build(atlas, oncourt, output, as_of, data_only=False, historical_prices=(), retained_prices=None):
    # Prevent accidental export into deployable site assets or overwriting source data.
    output = output.resolve()
    if 'public' in output.parts or output == oncourt.resolve() or output == atlas.resolve():
        raise ValueError('Output must be a separate local research directory, never public/')
    index = json.loads((atlas/'index.json').read_text(encoding='utf-8'))
    people = {r['id']: r for r in read(oncourt/'players_atp.csv')}
    tours = {r['id']: r for r in read(oncourt/'tours_atp.csv')}
    identities = defaultdict(list)
    for pid, person in people.items():
        if '/' not in person['name']: identities[norm(person['name'])].append(pid)
    player_map = {}
    for i, p in enumerate(index['players']):
        ids = identities[norm(p['name'])]
        if len(ids) == 1: player_map[ids[0]] = i
    games = defaultdict(list)
    for r in read(oncourt/'games_atp.csv'):
        if r['winner_id'] not in player_map or r['loser_id'] not in player_map: continue
        if r['winner_id'] not in people or r['loser_id'] not in people: continue
        pair = tuple(sorted([norm(people[r['winner_id']]['name']), norm(people[r['loser_id']]['name'])]))
        games[pair].append(r)
    stats = defaultdict(list)
    for r in read(oncourt/'stat_atp.csv'): stats[key(r)].append(r)
    details = {}
    for file in (atlas/'players').glob('*.json'):
        detail = json.loads(file.read_text(encoding='utf-8'))
        if detail['version'] != atlas.name:
            raise ValueError('Mixed release versions')
        for mid, event, score in detail['matches']:
            if mid in details and details[mid] != (event, score): raise ValueError('Conflicting match details')
            details[mid] = (event, score)
    audit, matches, exclusions = Counter(), [], []
    priced_keys = set()
    for row in index['matches']:
        mid, day, ai, bi, oa, ob, winner, surface, source = row
        a, b = index['players'][ai], index['players'][bi]
        event, score = details.get(mid, ('', ''))
        winner_name = norm([a,b][winner]['name'])
        pair = tuple(sorted([norm(a['name']), norm(b['name'])]))
        candidates = []
        for g in games.get(pair, []):
            t = tours.get(g['tour_id'], {})
            if abs((date.fromisoformat(g['date'])-date.fromisoformat(day)).days) > 1: continue
            if norm(t.get('name','')) != norm(event) or scores(g['result']) != scores(score): continue
            if norm(people[g['winner_id']]['name']) != winner_name: continue
            if SURFACES.get(t.get('court_id')) != index['surfaces'][surface]: continue
            if t.get('rank') not in ['2','3','4'] or int(g['round_id']) < 4: continue
            candidates.append(g)
        record = dict(id=mid, date=day, p1=ai, p2=bi, o1=oa, o2=ob, winner=winner,
                      surface=index['surfaces'][surface], event=event, score=score, source=index['sources'][source],
                      country=None, region=None, eventKey=None, stats1=None, stats2=None)
        if len(candidates) != 1:
            if day >= as_of:
                audit['on_or_after_cutoff'] += 1
                continue
            reason = 'unmatched_context' if not candidates else 'ambiguous_context'
            audit[reason] += 1
            exclusions.append({'id': mid, 'reason': reason})
        else:
            g = candidates[0]; t = tours[g['tour_id']]
            priced_keys.add(key(g))
            if g['date'] >= as_of:
                audit['on_or_after_cutoff'] += 1
                continue
            # Use the reconciled match date; retain source date only in private audit when different.
            if day != g['date']: audit['reconciled_date_difference'] += 1
            record['date'] = g['date']
            record.update(country=t['country'], region=REGION_OF.get(t['country']), eventKey=g['tour_id'])
            if record['region'] is None: audit['unknown_region'] += 1
            audit['matched_context'] += 1
            ss = stats.get(key(g), [])
            if len(ss) == 1:
                win_stats, loss_stats = point_stats(ss[0], 'w'), point_stats(ss[0], 'l')
                # Point conservation independently checks the winner/loser orientation.
                for serving, receiving in [(win_stats, loss_stats), (loss_stats, win_stats)]:
                    sv, ret = serving['serve'], receiving['return']
                    if sv and ret and (sv[1] != ret[1] or sv[0]+ret[0] != sv[1]):
                        serving['serve'] = None; receiving['return'] = None
                        audit['invalid_point_conservation'] += 1
                record['stats1'], record['stats2'] = (win_stats,loss_stats) if winner==0 else (loss_stats,win_stats)
                if any(v for v in win_stats.values()) or any(v for v in loss_stats.values()): audit['matches_with_some_stats'] += 1
            else:
                audit['missing_stats' if not ss else 'ambiguous_stats'] += 1
        matches.append(record)
    # Additional completed competitive meetings are H2H-only. Never expand the
    # priced ATP profile cohort or infer odds from outcomes.
    supplemental = []
    price_file = Path(__file__).resolve().parents[1]/'config/tennis-h2h-verified-prices.json'
    verified = json.loads(price_file.read_text(encoding='utf-8')) if price_file.exists() else []
    prices = {tuple(p['key']):p for p in verified}
    if len(prices) != len(verified): raise ValueError('Duplicate historical price evidence')
    all_games = [g for group in games.values() for g in group]
    counts = Counter(key(g) for g in all_games)
    priced_pairs = defaultdict(list)
    for m in matches: priced_pairs[tuple(sorted((m['p1'],m['p2'])))].append(m)
    for g in all_games:
        k = key(g); t = tours.get(g['tour_id'], {})
        if k in priced_keys or not ('1990-01-01' <= g['date'] < as_of): continue
        if counts[k] != 1 or t.get('rank') not in ('0','1','2','3','4','5'): continue
        if re.search(r'junior|exhibition|next.?gen|laver|hopman|diriyah', t.get('name',''), re.I): continue
        if not completed(g['result']): continue
        ai, bi = player_map[g['winner_id']], player_map[g['loser_id']]
        # Quarantine possible duplicates when the priced context could not be
        # reconciled uniquely. A missing join must never create a second meeting.
        if any({m['p1'],m['p2']} == {ai,bi} and abs((date.fromisoformat(m['date'])-date.fromisoformat(g['date'])).days)<=1
               and (norm(m['event'])==norm(t.get('name','')) or scores(m['score'])==scores(g['result'])) for m in priced_pairs[tuple(sorted((ai,bi)))]):
            audit['supplemental_possible_duplicate'] += 1
            continue
        competition = 'Qualifying' if int(g['round_id'])<4 else {'0':'ITF','1':'Challenger','5':'Team competition'}.get(t['rank'],'ATP main draw')
        row = dict(id='oc-'+ '-'.join(k),date=g['date'],p1=ai,p2=bi,winner=0,o1=None,o2=None,
            surface=SURFACES.get(t.get('court_id'),'unknown'),event=t['name'],score=g['result'],
            country=t.get('country'),region=REGION_OF.get(t.get('country')),eventKey=g['tour_id'],
            stats1=None,stats2=None,competition=competition)
        evidence = prices.get(k)
        if evidence:
            if evidence['date']!=g['date'] or evidence['score']!=g['result']:
                raise ValueError('Historical price evidence no longer matches result')
            row.update(o1=evidence['winnerOdds'],o2=evidence['loserOdds'],priceSource=evidence['source'],priceBasis=evidence['basis'])
        ss = stats.get(k, [])
        if len(ss)==1:
            row['stats1'],row['stats2']=point_stats(ss[0],'w'),point_stats(ss[0],'l')
            for serving,receiving in [(row['stats1'],row['stats2']),(row['stats2'],row['stats1'])]:
                sv,ret=serving['serve'],receiving['return']
                if sv and ret and (sv[1]!=ret[1] or sv[0]+ret[0]!=sv[1]):
                    serving['serve']=None;receiving['return']=None
        supplemental.append(row)
    if {k for k in prices if k[0] in player_map and k[1] in player_map} - {tuple(m['id'][3:].split('-')) for m in supplemental if m['o1'] is not None}:
        raise ValueError('Verified historical price evidence was not applied; review required')
    # Retain previously published paired prices even when a source later changes.
    for row in supplemental:
        before = (retained_prices or {}).get(row['id'])
        if before and row['o1'] is None:
            a,b = (index['players'][row[k]]['id'] for k in ('p1','p2'))
            if (row['date'],row['score'],a,b) != (before['date'],before['score'],before['p1'],before['p2']):
                raise ValueError('Retained historical price identity changed')
            row.update({k:before[k] for k in ('o1','o2','priceSource','priceBasis') if k in before})
    historical_audit = {}
    if historical_prices:
        spec = importlib.util.spec_from_file_location('h2h_prices', Path(__file__).with_name('h2h_historical_prices.py'))
        historical = importlib.util.module_from_spec(spec); spec.loader.exec_module(historical)
        historical_audit = historical.fill_prices(supplemental,index['players'],historical_prices)
    audit['supplemental_meetings'] = len(supplemental)
    audit['supplemental_priced'] = sum(m['o1'] is not None for m in supplemental)
    if len({m['id'] for m in matches}) != len(matches): raise ValueError('Duplicate output match')
    countries = sorted({m['country'] for m in matches+supplemental if m['region']})
    payload = {'schema':1, 'asOf':as_of, 'through':max(m['date'] for m in matches),
        'players':index['players'], 'portraits':index.get('portraits',{}), 'matches': matches,
        'results':supplemental, 'historyFrom':min(m['date'] for m in matches+supplemental),
        'countries':[{'code':c,'name':COUNTRY_NAMES.get(c,c),'region':REGION_OF[c]} for c in countries],
        'audit': dict(audit), 'atlasVersion':atlas.name,
        'priceBasis':'Recorded Pinnacle prices; mixed pre-match archive snapshots, not uniform closing odds.'}
    output.mkdir(parents=True, exist_ok=True)
    (output/'data.json').write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
    manifest = {'asOf':as_of,'audit':dict(audit),'matches':len(matches),'excludedContext':exclusions,
        'sourceHashes':{name:hashlib.sha256((oncourt/name).read_bytes()).hexdigest() for name in
         ['players_atp.csv','games_atp.csv','tours_atp.csv','stat_atp.csv']},
        'historicalPriceImport':historical_audit,
        'verifiedPriceHash':hashlib.sha256(price_file.read_bytes()).hexdigest() if price_file.exists() else None,
        'atlasIndexHash':hashlib.sha256((atlas/'index.json').read_bytes()).hexdigest(),
        'dataHash':hashlib.sha256((output/'data.json').read_bytes()).hexdigest()}
    (output/'audit.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if data_only:
        return manifest
    ui = Path(__file__).resolve().parents[1]/'research/tennis-matchup'
    for name in ['index.html','panel.css','panel.mjs','core.mjs','identity.mjs']:
        shutil.copyfile(ui/name, output/name)
    (output/'assets').mkdir(exist_ok=True)
    shutil.copyfile(ui/'assets/matchup-court-v1.png', output/'assets/matchup-court-v1.png')
    # Only local approved public image assets, no network or new image generation.
    public = Path(__file__).resolve().parents[1]/'public'
    for portrait in payload['portraits'].values():
        rel = portrait.get('url','').lstrip('/')
        src = (public/rel).resolve()
        if public.resolve() in src.parents and src.is_file():
            target=output/rel; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,target)
    print(json.dumps({'matches':len(matches),'audit':dict(audit),'dataBytes':(output/'data.json').stat().st_size,'output':str(output)},indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--atlas',type=Path,required=True)
    parser.add_argument('--oncourt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--as-of',type=date.fromisoformat,required=True)
    parser.add_argument('--data-only',action='store_true')
    args=parser.parse_args()
    build(args.atlas,args.oncourt,args.output,args.as_of.isoformat(),args.data_only)
