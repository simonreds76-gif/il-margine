"""Dependency-free rendering of the existing private weekly review."""
def weekly_text(r):
    if not r:return 'BREAK POINT C | paper tracker unavailable; live unchanged.'
    roi=f"{r['roi_pct']:+.2f}%" if r.get('roi_pct') is not None else 'not yet available'
    c=r.get('calibration',{});accuracy=f" | LL C {c['C']['log_loss']:.4f} / market {c['market']['log_loss']:.4f}" if c else ''
    return f"BREAK POINT C | {r.get('settled_fixtures',0)} settled fixtures | {r.get('wins',0)}W/{r.get('losses',0)}L | {r.get('stake',0):g}u paper | {r.get('profit',0):+.2f}u | ROI {roi} | {r.get('pending_bets',0)} pending bets{accuracy}. No alerts; completed-result research, bookmaker grading unverified."
