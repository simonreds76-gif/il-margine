"""Dependency-free existing weekly report. No alert delivery."""
def weekly_text(report):
    if not report:return 'Match Shape: paper snapshot unavailable.'
    lines=['Match Shape | ATP BO3 incl. qualifying/indoor | PAPER ONLY | no alerts',
           f"{report['fixtures']} fixtures / {report['contracts']} contracts; {report['settled_fixtures']} independently settled fixtures."]
    for market,label in [('total_games','Total games'),('game_handicap','Handicaps')]:
        for a,name in [('current','Current'),('T1','Frozen T1')]:
            r=report['arms'][a][market];c=r['calibration'];roi=f"{r['roi_pct']:+.2f}% ROI" if r['roi_pct'] is not None else 'ROI pending'
            cal=f"Brier {c['brier']:.4f}, log loss {c['log_loss']:.4f}" if c['n'] else 'calibration pending'
            lines.append(f"{label} {name}: {r['wins']}W/{r['losses']}L/{r['pushes']}P; {r['profit']:+.2f}u/{r['stake']}u; {roi}; {r['pending']} pending ({r['overdue']} overdue), {r['excluded']} excluded, {r['quarantined']} quarantined. {cal}.")
    lines.append(f"Capture {report.get('capture',{}).get('state','unknown')}; 1u paper, zero real stake. Reviews at 50/100 settled fixtures. ML unchanged; raw/C0 controls in Monitor.")
    health=report.get('operational',{})
    if health.get('state')=='BLOCKED':
        lines.append('Operational review required: '+str(health.get('reason') or 'unverified registration')+'. Last validated results retained.')
    elif health.get('state')=='UNREADABLE' or report.get('capture',{}).get('state')=='UNREADABLE':
        lines.append('Match Shape health unreadable; last validated results retained. Review required.')
    elif health.get('state')=='REVIEW_REQUIRED':
        lines.append(f"Settlement review required: {health.get('conflicts',0)} evidence conflict(s); settled records retained.")
    return '\n'.join(lines)


