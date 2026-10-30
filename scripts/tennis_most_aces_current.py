"""Current Most Aces comparison; frozen models, source-specific paper records.

No historical settlement on the manual-refresh path. Never label a rebuild as a
forecast made at an earlier quote time. Every price and model timestamp survives.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tennis_paper_prices import latest_snapshot_rows

ROOT = Path(__file__).resolve().parents[1]
COUNT_MODEL = 'v3_aces_gaussian_copula_nb2_evidence_tiers_v3'

def load_shadow():
    spec = importlib.util.spec_from_file_location('most_aces_shadow_current', ROOT/'scripts/tennis-most-aces-shadow.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def record(rows, model):
    selected = [r for r in rows if r.get('model') == model and r.get('bet_eligible') == 'yes']
    settled = [r for r in selected if r.get('settlement_status') == 'settled']
    profit = sum(float(r['pnl']) for r in settled)
    return dict(model=model, settled=len(settled), wins=sum(r.get('result') == 'win' for r in settled),
                losses=sum(r.get('result') == 'loss' for r in settled), stake=len(settled), profit=profit,
                roi=100*profit/len(settled) if settled else None,
                pending=sum(r.get('settlement_status') == 'pending' for r in selected))

def alert_rows(report, now):
    """One frozen count-model outcome per fixture, best current verified book.

    No model promotion: Direct remains a separate, non-alerting research arm.
    Never use an old report to revive a started or stale quote.
    """
    shadow=load_shadow()
    generated=shadow.parse_datetime(report.get('generated_at'))
    if not generated or not 0 <= (now-generated).total_seconds() <= 1800:
        return []
    chosen={}
    for match in report.get('matches',[]):
        if match.get('model') != COUNT_MODEL:continue
        for price in match.get('prices',[]):
            row=price.get('candidate')
            if not row or row.get('bet_eligible') != 'yes':continue
            start,stamp=shadow.parse_datetime(row.get('match_start_utc')),shadow.parse_datetime(row.get('price_captured_at'))
            if not stamp or not start or not stamp <= now < start or (now-stamp).total_seconds()>1800:continue
            pair=shadow.pair_key(row['player1'],row['player2'])
            fixture=(row['date'],shadow.norm_name(row['tournament']),*pair)
            outcome={'P1':'player1','P2':'player2','DRAW':'draw'}[row['recommended_side']]
            ev=float(row[f'value_{outcome}_pct'])
            if fixture not in chosen or ev > chosen[fixture][0]:chosen[fixture]=(ev,row)
    return [item[1] for item in chosen.values()]

def tournament_players(board, projections, shadow):
    """Attach the existing edition log only by the exact fixture and player pair."""
    players = []
    for side, name in enumerate([board.get('player1'), board.get('player2')], 1):
        found = [r for r in projections if
                 all(shadow.norm_name(r.get(k)) == shadow.norm_name(board.get(k))
                     for k in ['date', 'tour', 'tournament', 'surface'])
                 and shadow.norm_name(r.get('player')) == shadow.norm_name(name)
                 # Direct model player IDs are Sackmann IDs; the saved log uses OnCourt IDs.
                 # Only compare an explicitly namespaced ID, never those two namespaces.
                 and (not board.get(f'player{side}_oncourt_id') or r.get('player_id') == board[f'player{side}_oncourt_id'])
                 and (not board.get('tour_id') or r.get('tour_id') == board['tour_id'])
                 and shadow.pair_key(r.get('player'), r.get('opponent')) ==
                     shadow.pair_key(board.get('player1'), board.get('player2'))]
        if len(found) == 1:
            players.append({k: found[0].get(k, '') for k in
                ['player', 'opponent', 'player_id', 'opponent_id', 'tour_id', 'date', 'tournament', 'same_tournament_matches', 'tournament_round_log']})
    return players

def compare(boards, captures, ledger, now, shadow, projections=()):
    captures = latest_snapshot_rows(captures, now)
    matches = []
    for board in boards:
        prices = []
        for capture in captures:
            if (board.get('date') != capture.get('date')
                or shadow.pair_key(board.get('player1'),board.get('player2')) != shadow.pair_key(capture.get('player1'),capture.get('player2'))
                or shadow.norm_name(board.get('tournament')) != shadow.norm_name(capture.get('tournament'))):
                continue
            stamp, start = shadow.parse_datetime(capture.get('capture_ts')), shadow.parse_datetime(capture.get('match_start_utc'))
            if not stamp or not start or not stamp <= now < start or (now-stamp).total_seconds() > 1800:
                continue
            # Orient all bookmaker prices to the displayed model's player order.
            oriented = dict(capture)
            if shadow.norm_name(capture['player1']) != shadow.norm_name(board['player1']):
                for a,b in [('player1','player2'),('player1_odds','player2_odds')]:
                    oriented[a],oriented[b] = capture[b],capture[a]
            candidate = shadow.registration_row(board, oriented)
            prices.append(dict(bookmaker=capture['bookmaker'], player1_odds=oriented['player1_odds'],
                draw_odds=oriented['draw_odds'], player2_odds=oriented['player2_odds'],
                captured_at=capture['capture_ts'], start=capture['match_start_utc'],
                candidate=candidate))
        matches.append({**board,'prices':prices,
                        'tournament_players':tournament_players(board, projections, shadow)})
    return dict(generated_at=now.isoformat(), matches=matches,
                records=[record(ledger,m) for m in sorted({r.get('model','') for r in ledger if r.get('model')})],
                note='Paper research. Versions and bookmaker observations are separate; no profitability claim.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of',default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument('--out',type=Path,default=ROOT/'data/tennis-props/shadow/most-aces-current.json')
    args=parser.parse_args(); shadow=load_shadow(); props=ROOT/'data/tennis-props'
    boards=[]
    for filename in ['most-aces-1x2-board.csv','most-aces-direct-1x2-board.csv']:
        boards.extend(shadow.read_csv(props/'shadow'/filename))
    captures=[]
    for prefix in ['betmgm','bet365']:
        captures.extend(shadow.read_csv(props/'inbox'/f'{prefix}-most-aces-1x2-{args.as_of}.csv'))
    captures = latest_snapshot_rows(captures)
    ledger=shadow.read_csv(shadow.DEFAULT_LEDGER)
    added=0 if shadow.most_aces_suspended() else shadow.register(boards,captures,ledger)
    # Existing observations are never repriced, settled or modified here.
    if added: shadow.write_csv(shadow.DEFAULT_LEDGER,ledger)
    projections=shadow.read_csv(props/'player-props-board.csv')
    report=compare(boards,captures,ledger,datetime.now(timezone.utc),shadow,projections)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.out.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');temporary.replace(args.out)
    print(f'Most Aces current: {len(boards)} model rows; {sum(len(m["prices"]) for m in report["matches"])} current comparisons; {added} new observations')
    return 0

if __name__=='__main__':raise SystemExit(main())

