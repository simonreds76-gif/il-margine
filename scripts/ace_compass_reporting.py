"""Compact Ace Compass report; no forecast imports or file writes."""
def _original(report):
    if not report:return 'Ace Compass [PAPER ONLY]: report unavailable'
    a=report.get('arms',{}).get('candidate',{});roi=a.get('roi_pct');bias=next((b for b in report.get('bias',[]) if b['group']=='All'),{})
    bp=bias.get('candidate',{}).get('bias_pct')
    return ('Ace Compass v1 [PAPER ONLY]\n'+f"{a.get('wins',0)}W/{a.get('losses',0)}L | {a.get('pnl_units',0):+.2f}u on {a.get('stake_units',0)}u | "+(f'ROI {roi:+.2f}%' if roi is not None else 'No settled bets yet')+f" | {a.get('pending',0)} pending, {a.get('void',0)} void, {a.get('overdue',0)} overdue.\n"+(f"Predicted ace total bias {bp:+.1f}% across {bias.get('player_matches',0)} player matches (negative = underprediction). " if bp is not None else 'Prediction bias awaits completed matches. ')+f"Capture: {report.get('capture',{}).get('state','unknown')}. Historical +10.79%/19 bets stays separate."+(' Manual review milestone reached.' if report.get('review_due') else ''))


def weekly_text(report):
    lines = [_original(report)]
    paired = (report or {}).get('dispersion')
    if not paired:
        return lines[0]
    def fmt(value, digits, suffix=''):
        return '—' if value is None else f'{value:.{digits}f}'+suffix
    for scope, label in [('all','all verified prices'),('primary','Bet365 10+ milestones')]:
        sample = paired.get(scope)
        if not sample:
            continue
        lines.append(f"Ace Compass · {label} | {sample['quotes']} offers, {sample['fixtures']} fixtures, {sample['graded']} graded")
        for key, name in [('adjusted','Frozen'),('candidate','Compass'),('control','Control')]:
            arm = sample['arms'][key]
            lines.append(f"{name} {arm['wins']}W/{arm['losses']}L, {arm['pnl_units']:+.2f}u/{arm['stake_units']}u, "
                         f"ROI {fmt(arm['roi_pct'],1,'%')}, Brier {fmt(arm['brier'],3)}, log loss {fmt(arm['log_loss'],3)}; "
                         f"{arm['pending']} pending, {arm['passes']} passes, {arm['void']} void.")
    if paired.get('capture',{}).get('state')=='BLOCKED':
        lines.append('Ace Compass dispersion capture requires review.')
    return '\n'.join(lines)
