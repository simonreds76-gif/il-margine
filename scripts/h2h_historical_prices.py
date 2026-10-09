"""Match already downloaded historical prices to independently recorded results."""
import csv
import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.replace('ø', 'o')).lower() if c.isalnum())


def score(value):
    return re.findall(r'(\d+)-(\d+)', value)


def compatible_score(recorded, source):
    # Odds archives sometimes stop updating the live score. The independently
    # completed result remains authoritative; reject contradictory score lines.
    if re.search(r'ret|walk|w/o|abn|def', source, re.I): return False
    final, partial = score(recorded), score(source)
    if not source.strip(): return True
    if not partial or len(partial)>len(final): return False
    for i, (a,b) in enumerate(partial):
        if (a,b)==final[i]: continue
        x,y=int(a),int(b);fx,fy=map(int,final[i])
        ended = (max(x,y)>=6 and abs(x-y)>=2) or (max(x,y)==7 and min(x,y)==6)
        if i!=len(partial)-1 or ended or x>fx or y>fy: return False
    return True


def paired_prices(row):
    # Fixed snapshot priority, never the biggest price or the winning selection.
    for snapshot in ('cloture', 'ouverture'):
        try:
            pair = [float(row['cote1_'+snapshot]), float(row['cote2_'+snapshot])]
        except (KeyError, TypeError, ValueError):
            continue
        if all(math.isfinite(p) and 1 < p < 1001 for p in pair):
            return pair, snapshot
    return None, None


def fill_prices(results, players, paths):
    by_pair = defaultdict(list)
    for result in results:
        if result['o1'] is None and result['o2'] is None:
            pair = tuple(sorted(players[result[k]]['id'] for k in ('p1', 'p2')))
            by_pair[pair].append(result)
    candidates = defaultdict(dict)
    counts = Counter()
    hashes = {}
    surfaces = {'dur':'outdoor-hard', 'terre battue':'clay', 'gazon':'grass', 'dur intérieur':'indoor-hard', 'dur int\ufffdrieur':'indoor-hard'}
    for path in paths:
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(encoding='utf-8-sig', newline='') as handle:
            header = handle.readline(); handle.seek(0)
            for row in csv.DictReader(handle, delimiter=';' if ';' in header else ','):
                if row['genre'] != 'atp': continue
                ids = ['vbt-'+row['joueur1_id'], 'vbt-'+row['joueur2_id']]
                possible = by_pair.get(tuple(sorted(ids)), [])
                if not possible: continue
                counts['source_pair_rows'] += 1
                prices, snapshot = paired_prices(row)
                if prices is None:
                    counts['missing_source_prices'] += 1; continue
                if row['vainqueur_id'] not in (row['joueur1_id'],row['joueur2_id']): continue
                win = int(row['vainqueur_id'] == row['joueur2_id'])
                oriented = score(row['score'])
                if row['score'].strip() and not oriented: continue
                if win: oriented = [(b,a) for a,b in oriented]
                matches = []
                for result in possible:
                    if abs((date.fromisoformat(result['date'])-date.fromisoformat(row['date'][:10])).days)>1: continue
                    if norm(result['event']) != norm(row['tournoi']): continue
                    if result['id'].split('-')[-1] != row['tour']: continue
                    if result['surface'] != surfaces.get(row['surface']): continue
                    source_score = ' '.join(a+'-'+b for a,b in oriented) if win else row['score']
                    if re.search(r'ret|walk|w/o|abn|def',row['score'],re.I): continue
                    if players[result['p1']]['id'] != ids[win] or not compatible_score(result['score'],source_score): continue
                    if any(norm(players[result[k]]['name']) != norm(row['joueur'+str(ids.index(players[result[k]]['id'])+1)]) for k in ('p1','p2')): continue
                    matches.append(result)
                if len(matches) != 1:
                    counts['unmatched_or_ambiguous'] += 1; continue
                result = matches[0]
                source = f"https://www.valuebetennis.com/datasets/valuebetennis-matchs-{row['date'][:4]}.csv"
                basis = 'Pinnacle historical '+('opening' if snapshot=='ouverture' else 'last recorded pre-match')+' odds via Valuebetennis.'
                quote = dict(o1=prices[win], o2=prices[1-win], priceSource=source, priceBasis=basis)
                candidates[result['id']][(row['match_id'],prices[win],prices[1-win],snapshot)] = quote
    for result in results:
        quotes = candidates.get(result['id'], {})
        if len(quotes) == 1:
            result.update(next(iter(quotes.values())))
            counts['filled'] += 1
            counts['opening' if 'opening' in result['priceBasis'] else 'last_recorded'] += 1
        elif quotes:
            counts['conflicting_source_quotes'] += 1
    return {'counts':dict(counts), 'sourceHashes':hashes}
