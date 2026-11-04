"""Bounded, read-only identity evidence. No credentials in output or live writes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
from football_identity import read, write
from keeper_feed_comparison import digest, instant

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('collector', ROOT / 'scripts/compare-keeper-feeds.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

def run(output):
    config = read(ROOT / 'config/keeper-feed-comparison.json')
    history = read(ROOT / 'data/aerial/keeper-history.json.gz')['fixtures']
    ids = ['5749717', '5795488', '5795491', '5868101', '5881199', '5881202', '5881205']
    client = collector.Client(os.environ.get('GOAL_API_KEY', '').strip(), 4, 6, seconds=220)
    evidence = []
    for mid in ids:
        ref = history[mid][-1]
        league = config['leagues'][str(ref['league_id'])]
        calendar = client.get('goal', '/fixtures', {'from':'2026-10-23', 'to':'2026-10-25', 'leagueId':league['goal'], 'status':'FINISHED', 'limit':100, 'offset':0})
        rows = calendar.get('data')
        assert isinstance(rows, list) and len(rows)<100, 'incomplete_calendar'
        assert all(str(row['leagueId']) == league['goal'] for row in rows), 'wrong_league'
        same_time = [row for row in rows if instant(row['kickoffUtc']) == instant(ref['kickoff'])]
        espn = client.get('espn', '/'+league['espn']+'/scoreboard', {'dates':instant(ref['kickoff']).strftime('%Y%m%d')})
        # These are candidates for review, never automatic identity matches.
        evidence.append({'reference':{k:ref.get(k) for k in ('match_id','league_id','kickoff','home','away','score')},
                         'goal_same_time_candidates':same_time,
                         'espn_events':espn.get('events', []),
                         'goal_calendar_sha256':digest(calendar), 'espn_sha256':digest(espn)})
    write(output, {'fixtures':evidence, 'requests':dict(client.used), 'receipts':client.receipts})
    print(json.dumps({'fixtures':len(evidence), 'requests':dict(client.used)}))

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
