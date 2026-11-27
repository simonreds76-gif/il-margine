#!/usr/bin/env python3
"""Claim and notify newly registered GK signals; never resend an ambiguous attempt.

--prepare runs before the evidence commit. --send runs only after that commit
has been pushed. Claims survive failed sends and reruns (manual review required).
"""
import argparse
import csv
from datetime import datetime, timezone, timedelta
import html
import io
import json
import math
import os
from pathlib import Path
import requests
from goalkeeper_price_selection import alert_price_check, contract_key, number
from goalkeeper_quote_integrity import current_quote_issue
from goalkeeper_alert_prices import format_prices, load_sources, paired_prices
from goalkeeper_delivery import digest_keys, pick_keys, read_receipts, three_books, telegram_text_matches

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'data/goalkeeper-saves'
STATE = FOLDER / 'gk-saves-telegram-state.json'
LEDGER = FOLDER / 'gk-saves-v1-shadow-signals.csv'
REPORT = FOLDER / 'gk-saves-v1-shadow-report.json'
CANDIDATES = FOLDER / 'gk-saves-v1-candidates.csv'

def keeper_watch_rows(path, now):
    """Use the regenerated report's locked selections, never latest price candidates."""
    if not path.exists():
        return []
    report = json.loads(path.read_text(encoding='utf-8')).get('keeper_watch') or {}
    generated = stamp(report.get('generated_at'))
    start = stamp(report.get('start_at'))
    if (report.get('status') != 'TRACKING' or report.get('actual_stake') != 0
            or report.get('paper_stake') != .5 or report.get('auto_promote') is not False
            or not generated or not start or not timedelta(0) <= now-generated <= timedelta(hours=6)):
        return []
    rows = []
    for r in report.get('selections', []):
        captured, registered = stamp(r.get('captured_at')), stamp(r.get('registered_at'))
        if (r.get('model') != 'keeper_watch' or not r.get('match_id')
                or not r.get('player_id') or not r.get('team_id')
                or not captured or not registered or not start <= captured <= registered <= generated):
            continue
        rows.append({**r, 'alert_model':'keeper_watch_v1',
            'signal_id':f"keeper_watch_v1:{r['match_id']}",
            'created_at':r['registered_at'], 'odds_decimal':r.get('odds'),
            'home_team':r.get('home'), 'away_team':r.get('away'),
            'selection_policy':'keeper_watch_v1', 'paper_stake':.5, 'actual_stake':0})
    return rows

def stamp(value):
    try:
        d = datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
        return d if d.tzinfo else None
    except ValueError:
        return None

def eligible(row, now):
    if current_quote_issue(row):
        return False
    created, captured, kickoff = [stamp(row.get(k)) for k in ('created_at','captured_at','kickoff_at')]
    if not all((created,captured,kickoff)) or not (kickoff > now and timedelta(0) <= now-created <= timedelta(hours=6) and timedelta(0) <= now-captured <= timedelta(hours=6)):
        return False
    if str(row.get('status','')).lower() != 'pending' or row.get('duplicate_of') or row.get('quarantine_reason') or 'quarantin' in row.get('integrity_status',''):
        return False
    try:
        if row.get('alert_model') == 'keeper_watch_v1':
            return (str(row.get('signal_id','')).startswith('keeper_watch_v1:')
                and row.get('selection_policy') == 'keeper_watch_v1'
                and row.get('paper_stake') == .5 and row.get('actual_stake') == 0
                and contract_key(row) is not None
                and (str(row.get('bookmaker','')).casefold() == 'bet365'
                     or (str(row.get('bookmaker','')).casefold() == 'grosvenor'
                         and row.get('settlement_policy') == 'grosvenor_full90_scope_agreement_v1'
                         and row.get('contract_scope') in ('team_goalkeeper_home','team_goalkeeper_away')))
                and row.get('lineup_status') in ('predicted_starter','confirmed_starter')
                and row.get('side') in ('over','under')
                and all(math.isfinite(float(row[k])) for k in ('edge','odds_decimal','fair_odds','line'))
                and float(row['edge']) >= .05 and 1.7 <= float(row['odds_decimal']) <= 3
                and float(row['fair_odds']) > 1 and float(row['line']) >= 0)
        return bool(row.get('signal_id')) and contract_key(row) is not None and float(row['edge']) >= .05 and 1.7 <= float(row['odds_decimal']) <= 3 and row.get('selection_policy') == 'near_even_value_v2'
    except (ValueError, KeyError, TypeError):
        return False

def recommendation_key(row):
    if row.get('alert_model') == 'keeper_watch_v1':
        return ('keeper_watch_v1', row.get('signal_id'))
    key = contract_key(row)
    # Current policy is one primary per fixture, not one per bookmaker.
    return ('gk_saves_v1', key[0]) if key else None


def prior_claim(row, entries, own_key=None):
    key = recommendation_key(row)
    if key is None:
        return False
    own = entries.get(own_key, {})
    for signal_id, item in entries.items():
        previous = item.get('signal', {})
        if signal_id == own_key or (recommendation_key(previous) != key and not pick_keys(row) & pick_keys(previous)):
            continue
        if item.get('status') in ('sent', 'delivery_unconfirmed'):
            return True
        if item.get('status') == 'claimed' and (own_key is None or (item.get('claimed_at',''), signal_id) < (own.get('claimed_at',''), own_key)):
            return True
    return False


def checked_alert_prices(row, offers, now, sources):
    reason, comparison = alert_price_check(row, offers, now)
    if sources is None or reason not in (None, 'better_bookmaker_price_available'):
        return reason, comparison, []
    display = paired_prices(row, offers, now, sources)
    if not display:
        return reason or 'awaiting_fresh_bet365_grosvenor_pair', comparison, []
    # The locked paper price is still offered. A better current quote leads
    # the comparison without changing that record or issuing a second pick.
    return None, comparison, display


def claim(rows, state, token, now, offers=None, sources=None, digest_sent=frozenset()):
    entries = state.setdefault('signals', {})
    added = 0
    rejected = {}
    for row in sorted(rows, key=lambda r: -(number(r.get('odds_decimal')) or 0)):
        key = row.get('signal_id','')
        if (key in entries and not entries[key].get('retryable_before_http')) or not eligible(row, now) or added >= 10:
            continue
        reason = 'fixture_already_notified_or_claimed' if prior_claim(row, entries) or pick_keys(row) & digest_sent else None
        comparison = []
        display = []
        if not reason and offers is not None:
            reason, comparison, display = checked_alert_prices(row, offers, now, sources)
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        signal = dict(row)
        if display:
            signal['display_prices'] = display
            if prior_claim(signal, entries) or pick_keys(signal) & digest_sent:
                rejected['fixture_already_notified_or_claimed'] = rejected.get('fixture_already_notified_or_claimed', 0) + 1
                continue
        if comparison:
            signal.update(price_comparison=comparison, price_checked_at=now.isoformat())
        entries[key] = {'status':'claimed','run_token':token,'claimed_at':now.isoformat(), 'signal':signal}
        added += 1
    if rows:
        state.setdefault('preparation_checks', {})['keeper_watch' if rows[0].get('alert_model') == 'keeper_watch_v1' else 'current'] = dict(checked_at=now.isoformat(), added=added, suppressed=rejected)
    return added

def comparison_note(row, coverage, now):
    if row.get('display_prices'):
        return format_prices(row)
    comparison = row.get('price_comparison') or []
    books = {q['bookmaker'].casefold() for q in comparison}
    prices = ' | '.join(f"{html.escape(q['bookmaker'])} {q['odds']:.2f}" for q in comparison)
    label = 'Verified prices' if len(books) > 1 else 'Only verified price'
    parts = [f'{label}: {prices}'] if prices else []
    if 'bet365' not in (books or {str(row.get('bookmaker') or '').casefold()}):
        reason = 'no verified price for this keeper and line'
        checked = stamp(coverage.get('generated_at'))
        event = str(row.get('event_id') or '')
        kickoff = stamp(row.get('kickoff_at'))
        fixture_matches = event and kickoff and any(str(f.get('id')) == event and stamp(f.get('kickoff_at')) == kickoff
                              for f in coverage.get('selected_events', []))
        if fixture_matches and checked and timedelta(0) <= now-checked <= timedelta(minutes=10):
            matches = [f for f in (coverage.get('moviodds_source') or {}).get('goalkeeper_fixture_coverage', [])
                       if str(f.get('event_id')) == event]
            if len(matches) == 1:
                reason = {
                    'INDEPENDENT_CHECK_UNAVAILABLE': 'market found; price could not be independently verified',
                    'FIXTURE_NOT_FOUND': 'fixture could not be matched',
                    'AMBIGUOUS_FIXTURE': 'fixture match was ambiguous',
                    'STALE_OR_MISSING_GK_POLL': 'no fresh saves quote',
                    'NO_GK_MARKET_IN_FEED': 'no saves market returned for this fixture',
                }.get(matches[0].get('status'), reason)
        parts.append(f'Bet365: {reason}.')
    return ''.join(part+'\n' for part in parts)


def message(row, coverage=None, now=None):
    e = lambda k: html.escape(str(row.get(k) or ''))
    price_note = comparison_note(row, coverage if isinstance(coverage, dict) else {}, now or datetime.now(timezone.utc))
    if row.get('display_prices'):
        watch = row.get('alert_model') == 'keeper_watch_v1'
        title = 'Keeper Watch v1 | PAPER selection' if watch else 'GK saves | New tracked signal'
        scope = str(row.get('contract_scope') or '')
        side = scope.removeprefix('team_goalkeeper_')
        subject = e(side+'_team')+' keeper' if side in ('home','away') and not watch else e('goalkeeper')
        monitor = ('\n<a href="https://ilmargine.bet/model-monitor/gk-saves#keeper-watch">Keeper Watch results and ROI (Admin login)</a>'
                   if watch else '')
        return (f"<b>{title}</b>\n\n<b>{e('home_team')} vs {e('away_team')}</b>\n"
                f"{subject} · {e('side').title()} {e('line')} saves\n"
                f"Fair odds at capture: {float(row['fair_odds']):.2f}\n\n"
                f"{price_note}\nBet365 lists the likely starters. Each named price applies to that player.\n"
                f"Kickoff: {e('kickoff_at')}\n"
                f"Paper record: 0.5u at {float(row['odds_decimal']):.2f} {e('bookmaker')}.{monitor}")
    if row.get('alert_model') == 'keeper_watch_v1':
        scope = str(row.get('contract_scope') or '')
        note = ('Team goalkeeper contract; model uses the named predicted starter. Check the official XI.\n'
                if scope.startswith('team_goalkeeper_') else '')
        return ('<b>Keeper Watch v1 | PAPER selection</b>\n'
            'Separate experiment from the current GK saves model.\n\n'
            f"<b>{e('home_team')} vs {e('away_team')}</b>\n"
            f"{e('goalkeeper')} | {e('side').title()} {e('line')} saves\n"
            f"{html.escape(str(row.get('bookmaker') or 'Bet365'))} recorded odds: <b>{float(row['odds_decimal']):.2f}</b>\n"
            f"{price_note}"
            f"{note}"
            f"Keeper Watch fair odds: {float(row['fair_odds']):.2f} | Estimated EV: {float(row['edge'])*100:+.1f}%\n"
            f"Kickoff: {e('kickoff_at')}\nCaptured: {e('captured_at')}\n"
            f"Lineup: {e('lineup_status').replace('_',' ')}\n\n"
            'Tracking stake: 0.5u paper. Real stake: 0u.\n'
            'Original price and forecast locked. Estimated edge is unproven.\n'
            '<a href="https://ilmargine.bet/model-monitor/gk-saves#keeper-watch">Keeper Watch results and ROI (Admin login)</a>')
    scope = str(row.get('contract_scope') or '')
    team_contract = scope in {'team_goalkeeper_home', 'team_goalkeeper_away'}
    display_keeper = scope.removeprefix('team_goalkeeper_').title() + ' goalkeeper' if team_contract else e('goalkeeper')
    contract_note = 'Grosvenor covers the team keeper. Bet365 prices apply to the named player.\n' if team_contract else ''
    return ('<b>GK saves | New tracked signal</b>\n\n'
        f"<b>{e('home_team')} vs {e('away_team')}</b>\n"
        f"{display_keeper} - {e('side').title()} {e('line')} saves\n"
        f"{html.escape(str(row.get('bookmaker') or 'Bet365'))} recorded odds: <b>{float(row['odds_decimal']):.2f}</b>\n"
        f"{price_note}"
        f"Fair odds at capture: {float(row['fair_odds']):.2f} | Estimated EV: +{float(row['edge'])*100:.1f}%\n"
        f"Kickoff: {e('kickoff_at')}\nCaptured: {e('captured_at')}\n"
        f"Lineup: {e('lineup_status').replace('_',' ')}\n"
        f"{contract_note}\n"
        'These odds and this forecast are locked for tracking. Later updates may show a revised forecast and price. Check the current bookmaker price before betting.\n'
        'Research model; 0.5u paper tracking, not a proven edge.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--send',action='store_true');p.add_argument('--state',type=Path,default=STATE);p.add_argument('--ledger',type=Path,default=LEDGER);p.add_argument('--report',type=Path,default=REPORT);p.add_argument('--candidates',type=Path,default=CANDIDATES);a=p.parse_args()
    if a.prepare == a.send: p.error('Choose exactly one of --prepare or --send')
    token = os.environ.get('GITHUB_RUN_ID','') + ':' + os.environ.get('GITHUB_RUN_ATTEMPT','')
    bot=os.environ.get('OPS_ALERT_TELEGRAM_BOT_TOKEN','').strip();chat=os.environ.get('OPS_ALERT_TELEGRAM_CHAT_ID','').strip()
    if not bot or not chat or token==':': raise SystemExit('GK alerts require the configured ops Telegram destination and a workflow run token')
    state=json.loads(a.state.read_text(encoding='utf-8')) if a.state.exists() else {'signals':{}}
    with a.candidates.open(encoding='utf-8-sig',newline='') if a.candidates.exists() else io.StringIO('') as f:
        offers=list(csv.DictReader(f))
    sources = load_sources(a.candidates.parent)
    digest_sent = digest_keys(read_receipts(a.state.parent.parent / 'football-form' / 'football-daily-signal-digest-state.json','sent'))
    def save():
        a.state.parent.mkdir(parents=True,exist_ok=True);tmp=a.state.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(a.state)
    if a.prepare:
        with a.ledger.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        now=datetime.now(timezone.utc)
        count=claim(rows,state,token,now,offers,sources,digest_sent)
        watch_count=claim(keeper_watch_rows(a.report,now),state,token,now,offers,sources,digest_sent)
        save();print(f'GK alert claims prepared: current {count}; Keeper Watch paper {watch_count}');return
    try:
        coverage = json.loads((a.candidates.parent/'gk-saves-capture-status.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        coverage = {}
    failed=0;sent=0
    for key, item in list(state['signals'].items()):
        if item.get('status')!='claimed' or item.get('run_token')!=token: continue
        if not eligible(item['signal'],datetime.now(timezone.utc)):
            item['status']='expired_before_send';save();continue
        reason = 'fixture_already_notified_or_claimed' if prior_claim(item['signal'], state['signals'], key) or pick_keys(item['signal']) & digest_sent else None
        if not reason:
            now = datetime.now(timezone.utc)
            reason, comparison, display = checked_alert_prices(item['signal'], offers, now, sources)
            if not reason:
                item['signal'].update(display_prices=display, price_comparison=comparison, price_checked_at=now.isoformat())
                if prior_claim(item['signal'], state['signals'], key) or pick_keys(item['signal']) & digest_sent:
                    reason = 'fixture_already_notified_or_claimed'
        if reason in ('awaiting_fresh_bet365_grosvenor_pair','current_quote_unavailable'):
            # Nothing was sent. A later capture may safely retry the locked selection.
            state['last_deferred_before_send'] = dict(signal_id=key, reason=reason, checked_at=now.isoformat())
            del state['signals'][key]
            save()
            continue
        if reason:
            if reason == 'better_bookmaker_price_available':
                item['retryable_before_http'] = True
            item.update(status='suppressed_before_send',suppression_reason=reason);save();continue
        # Persist uncertainty before HTTP. A replay cannot assume Telegram rejected it.
        item['status']='delivery_unconfirmed';save()
        try:
            body = message(item['signal'],coverage)
            r=requests.post(f'https://api.telegram.org/bot{bot}/sendMessage',json={'chat_id':chat,'text':body,'parse_mode':'HTML','disable_web_page_preview':True},timeout=20)
            payload=r.json()
            # A structured rejection confirms that this attempt was not accepted.
            # Never persist the response text or exception URL: either can expose credentials.
            if payload.get('ok') is False:
                item.update(status='delivery_rejected',error_kind='telegram_rejected',http_status=r.status_code)
                failed+=1;save();print(f'GK alert rejected: HTTP {r.status_code}; review required');continue
            if not r.ok or payload.get('ok') is not True: raise ValueError('Invalid Telegram response')
            item.update(status='sent',message_id=payload['result']['message_id'],sent_at=datetime.now(timezone.utc).isoformat());sent+=1
            if three_books(item['signal'].get('display_prices', [])):
                item['three_book_text_verified'] = telegram_text_matches(payload['result'], body, rich=True)
        except Exception as exc:
            kind = ('timeout' if isinstance(exc, requests.exceptions.Timeout) else
                    'connection_error' if isinstance(exc, requests.exceptions.ConnectionError) else
                    'invalid_response' if isinstance(exc, (ValueError, KeyError, TypeError)) else 'delivery_error')
            item['error_kind']=kind
            failed+=1
            print(f'GK alert delivery unconfirmed: {kind}; review required')
        save()
    print(f'GK alerts: {sent} sent; {failed} failed or unconfirmed; no automatic resend of ambiguous deliveries')
    if failed: raise SystemExit(1)

if __name__=='__main__':main()
