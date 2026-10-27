"""Dependency-free weekly summary. Never sends a notification."""
def weekly_text(report):
    if not report:
        return 'Sisal 50/50 [PAPER ONLY]: report unavailable'
    a=report['arms']['blend50'];roi=a['roi_pct'];bias=next((b for b in report.get('bias',[]) if b['group']=='All'),None)
    lines=['Sisal 50/50 [PAPER ONLY; 1u hypothetical / 0 real stake]',
           f"{a['wins']}W/{a['losses']}L | {a['pnl_units']:+.2f}u / {a['stake_units']}u | "+(f"ROI {roi:+.2f}%" if roi is not None else 'ROI awaiting settlements')+
           f" | {a['pending']} pending, {a['void']} void, {a['overdue']} overdue; {a.get('retirement_settled',0)} retirement-determined bets.",
           f"{report['quotes']} frozen paired prices; {report['completed_contracts']} completed player contracts / {report['independent_fixtures']} independent fixtures."]
    if bias:
        lines.append(f"Ace-count bias {bias['bias_aces']:+.2f} per player-match (negative = underprediction).")
    for key,label in [('model','Model'),('market','Market'),('blend50','50/50')]:
        b=report['arms'][key]
        if b['brier'] is not None:lines.append(f"{label}: Brier {b['brier']:.4f}; log loss {b['log_loss']:.4f} on identical completed contracts.")
    for key,a in report.get('format_results',{}).items():
        if a['settled']:lines.append(f"BO{key}: {a['settled']} settled, {a['profit']:+.2f}u, ROI {a['roi_pct']:+.2f}%.")
    lines.append('Capture: '+report.get('capture',{}).get('state','unknown')+'. No individual alerts; live models unchanged. Historical replay excluded.')
    comparison=report.get('event_comparison') or {}
    versions=comparison.get('versions') or {}
    if versions:
        lines.append(f"Event correction comparison: {comparison.get('paired_contracts',0)} identical forward contracts; {comparison.get('without_event_results',0)} without earlier main-draw evidence.")
        for name,label in [('original','Original 50/50'),('event_adjusted','Event-adjusted 50/50')]:
            a=versions[name]['arms']['blend50'];roi=a['roi_pct']
            lines.append(label+f": {a['wins']}W/{a['losses']}L | {a['pnl_units']:+.2f}u/{a['stake_units']}u | "+(f"ROI {roi:+.2f}%" if roi is not None else 'ROI awaiting settlements')+f" | {a['pending']} pending, {a['void']} void, {a['overdue']} overdue.")
        lines.append('Comparison uses the same prices and fixed rules. Earlier full record remains separate; no new alerts or live changes.')
        if comparison.get('unavailable'):lines.append('Comparison exclusions: '+', '.join(f'{k}: {v}' for k,v in comparison['unavailable'].items()))
    if comparison.get('error'):lines.append('Event comparison check: '+str(comparison['error']))
    if report.get('ledger_head'):lines.append('Ledger checkpoint: '+report['ledger_head'][:16])
    if report.get('review_due'):lines.append('Manual evidence review milestone reached; no automatic promotion.')
    return '\n'.join(lines)
