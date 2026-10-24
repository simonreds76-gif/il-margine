"""Compact Ace Compass report; no forecast imports or file writes."""
def weekly_text(report):
    if not report:return 'Ace Compass [PAPER ONLY]: report unavailable'
    a=report.get('arms',{}).get('candidate',{});roi=a.get('roi_pct');bias=next((b for b in report.get('bias',[]) if b['group']=='All'),{})
    bp=bias.get('candidate',{}).get('bias_pct')
    return ('Ace Compass v1 [PAPER ONLY]\n'+f"{a.get('wins',0)}W/{a.get('losses',0)}L | {a.get('pnl_units',0):+.2f}u on {a.get('stake_units',0)}u | "+(f'ROI {roi:+.2f}%' if roi is not None else 'No settled bets yet')+f" | {a.get('pending',0)} pending, {a.get('void',0)} void, {a.get('overdue',0)} overdue.\n"+(f"Predicted ace total bias {bp:+.1f}% across {bias.get('player_matches',0)} player matches (negative = underprediction). " if bp is not None else 'Prediction bias awaits completed matches. ')+f"Capture: {report.get('capture',{}).get('state','unknown')}. Historical +10.79%/19 bets stays separate."+(' Manual review milestone reached.' if report.get('review_due') else ''))
