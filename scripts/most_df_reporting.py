"""Read-only formatting for the existing weekly review."""
def weekly_text(r):
    if not r:return 'Most DF: no paper evidence snapshot.'
    roi=f"{r['roi_pct']:+.2f}%" if r.get('roi_pct') is not None else 'not available'
    return f"Most DF | PAPER OBSERVATION ONLY | {r.get('wins',0)}W/{r.get('losses',0)}L | {r.get('pnl_units',0):+.2f}u on {r.get('stake_units',0):g}u | ROI {roi} | {r.get('pending',0)} pending ({r.get('overdue',0)} overdue). {r.get('settled_fixtures',0)}/150 independent settled fixtures. Capture: {r.get('capture',{}).get('state','UNKNOWN')}. No betting alerts; unvalidated independent-count benchmark."
