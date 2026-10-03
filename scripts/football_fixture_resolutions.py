"""Explicitly reviewed non-played fixtures, restricted to paper research ledgers."""
from datetime import datetime, timezone
from pathlib import Path
import json
from football_team_names import football_form_team_key


def apply_reviewed_voids(rows, root: Path, *, goalkeeper=False, now=None):
    path=root/'config/football-fixture-resolutions.json'
    if not path.exists():return 0
    resolutions=json.loads(path.read_text(encoding='utf-8'))
    now=now or datetime.now(timezone.utc)
    changed=0
    for row in rows:
        status=str(row.get('status' if goalkeeper else 'result') or '').lower()
        if status not in ('pending',''):continue
        key=(str(row.get('match_date') or '')[:10],str(row.get('league') or ''),football_form_team_key(row.get('home_team')),football_form_team_key(row.get('away_team')))
        matches=[r for r in resolutions if r.get('outcome')=='void'
                 and r.get('scope')=='paper_research_only_not_a_claim_about_customer_bet_settlement'
                 and r.get('source_url','').startswith('https://') and r.get('reason')
                 and (r['date'],r['league'],football_form_team_key(r['home']),football_form_team_key(r['away']))==key
                 and datetime.fromisoformat(r['reviewed_at'].replace('Z','+00:00'))<=now]
        if len(matches)!=1:continue
        r=matches[0]
        row.update(result='void',pnl_units='0',settled_at=now.isoformat(),
                   settlement_source='reviewed_nonplayed_fixture | '+r['source_url'])
        if goalkeeper:row.update(status='void',actual_saves='',close_odds='',clv='')
        else:row.update(actual_team_shots='',true_close=False,published_to_close_clv='')
        changed+=1
    return changed
